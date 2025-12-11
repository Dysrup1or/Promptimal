"""
Stripe integration service for Catalyze.
Handles subscription checkout, webhooks, and customer management.
"""

import os
from datetime import datetime
from typing import Optional, Tuple, Dict, Any

from .database import get_db_connection, init_database
from .logger import logger

# Load Stripe configuration from environment
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRO_PRICE_ID = os.getenv("STRIPE_PRO_PRICE_ID", "")

# Stripe is optional - only import if keys are configured
stripe = None
if STRIPE_SECRET_KEY:
    try:
        import stripe as stripe_lib
        stripe = stripe_lib
        stripe.api_key = STRIPE_SECRET_KEY
    except ImportError:
        logger.warning("Stripe package not installed. Run: pip install stripe")


class StripeService:
    """Service for Stripe subscription management."""
    
    def __init__(self):
        """Initialize Stripe service."""
        init_database()
        self._stripe_available = stripe is not None and bool(STRIPE_SECRET_KEY)
    
    @property
    def is_configured(self) -> bool:
        """Check if Stripe is properly configured."""
        return self._stripe_available and bool(STRIPE_PRO_PRICE_ID)
    
    @property
    def publishable_key(self) -> str:
        """Get Stripe publishable key for client-side."""
        return STRIPE_PUBLISHABLE_KEY
    
    # =========================================================================
    # CUSTOMER MANAGEMENT
    # =========================================================================
    
    def get_stripe_customer_id(self, user_id: int) -> Optional[str]:
        """Get Stripe customer ID for a user if it exists."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT stripe_customer_id FROM stripe_customers
                WHERE user_id = ?
            """, (user_id,))
            row = cursor.fetchone()
            return row["stripe_customer_id"] if row else None
    
    def get_or_create_customer(self, user_id: int, email: str, name: str = "") -> Tuple[str, bool]:
        """
        Get or create a Stripe customer for a user.
        
        Returns:
            Tuple of (customer_id, was_created)
        """
        # Check if customer already exists
        existing_id = self.get_stripe_customer_id(user_id)
        if existing_id:
            return existing_id, False
        
        if not self._stripe_available:
            raise ValueError("Stripe is not configured")
        
        # Create customer in Stripe
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name if name else None,
                metadata={"promptly_user_id": str(user_id)}
            )
            
            # Store in database
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO stripe_customers (user_id, stripe_customer_id)
                    VALUES (?, ?)
                """, (user_id, customer.id))
                conn.commit()
            
            logger.info(f"Created Stripe customer {customer.id} for user {user_id}")
            return customer.id, True
            
        except Exception as e:
            logger.error(f"Failed to create Stripe customer for user {user_id}: {e}")
            raise
    
    # =========================================================================
    # CHECKOUT SESSION
    # =========================================================================
    
    def create_checkout_session(
        self,
        user_id: int,
        email: str,
        name: str,
        success_url: str,
        cancel_url: str,
        price_id: str = None
    ) -> str:
        """
        Create a Stripe Checkout session for subscription.
        
        Returns:
            Checkout session URL to redirect user to
        """
        if not self._stripe_available:
            raise ValueError("Stripe is not configured")
        
        price_id = price_id or STRIPE_PRO_PRICE_ID
        if not price_id:
            raise ValueError("No Stripe price ID configured")
        
        # Get or create customer
        customer_id, _ = self.get_or_create_customer(user_id, email, name)
        
        try:
            session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=["card"],
                line_items=[{
                    "price": price_id,
                    "quantity": 1,
                }],
                mode="subscription",
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={"promptly_user_id": str(user_id)},
                subscription_data={
                    "metadata": {"promptly_user_id": str(user_id)}
                },
                allow_promotion_codes=True,
            )
            
            logger.info(f"Created checkout session {session.id} for user {user_id}")
            return session.url
            
        except Exception as e:
            logger.error(f"Failed to create checkout session for user {user_id}: {e}")
            raise
    
    def create_customer_portal_session(
        self,
        user_id: int,
        return_url: str
    ) -> str:
        """
        Create a Stripe Customer Portal session for managing subscription.
        
        Returns:
            Portal session URL to redirect user to
        """
        if not self._stripe_available:
            raise ValueError("Stripe is not configured")
        
        customer_id = self.get_stripe_customer_id(user_id)
        if not customer_id:
            raise ValueError("No Stripe customer found for user")
        
        try:
            session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url,
            )
            
            logger.info(f"Created portal session for user {user_id}")
            return session.url
            
        except Exception as e:
            logger.error(f"Failed to create portal session for user {user_id}: {e}")
            raise
    
    # =========================================================================
    # SUBSCRIPTION MANAGEMENT
    # =========================================================================
    
    def get_active_subscription(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user's active subscription if exists."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM subscriptions
                WHERE user_id = ? AND status IN ('active', 'trialing')
                ORDER BY created_at DESC
                LIMIT 1
            """, (user_id,))
            row = cursor.fetchone()
            if row:
                return {
                    "id": row["id"],
                    "stripe_subscription_id": row["stripe_subscription_id"],
                    "status": row["status"],
                    "plan": row["plan"],
                    "current_period_end": row["current_period_end"],
                    "cancel_at_period_end": bool(row["cancel_at_period_end"]),
                }
            return None
    
    def upsert_subscription(
        self,
        user_id: int,
        stripe_subscription_id: str,
        status: str,
        plan: str = "pro",
        current_period_start: datetime = None,
        current_period_end: datetime = None,
        cancel_at_period_end: bool = False
    ) -> None:
        """Insert or update a subscription record."""
        now = datetime.now().isoformat()
        period_start = current_period_start.isoformat() if current_period_start else None
        period_end = current_period_end.isoformat() if current_period_end else None
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check if subscription exists
            cursor.execute("""
                SELECT id FROM subscriptions WHERE stripe_subscription_id = ?
            """, (stripe_subscription_id,))
            existing = cursor.fetchone()
            
            if existing:
                cursor.execute("""
                    UPDATE subscriptions SET
                        status = ?,
                        plan = ?,
                        current_period_start = ?,
                        current_period_end = ?,
                        cancel_at_period_end = ?,
                        updated_at = ?
                    WHERE stripe_subscription_id = ?
                """, (status, plan, period_start, period_end, 
                      1 if cancel_at_period_end else 0, now, stripe_subscription_id))
            else:
                cursor.execute("""
                    INSERT INTO subscriptions 
                    (user_id, stripe_subscription_id, status, plan, 
                     current_period_start, current_period_end, cancel_at_period_end,
                     created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (user_id, stripe_subscription_id, status, plan,
                      period_start, period_end, 1 if cancel_at_period_end else 0,
                      now, now))
            
            conn.commit()
        
        logger.info(f"Upserted subscription {stripe_subscription_id} for user {user_id}: {status}")
    
    def delete_subscription(self, stripe_subscription_id: str) -> None:
        """Delete a subscription record."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM subscriptions WHERE stripe_subscription_id = ?
            """, (stripe_subscription_id,))
            conn.commit()
        
        logger.info(f"Deleted subscription {stripe_subscription_id}")
    
    # =========================================================================
    # TIER MANAGEMENT
    # =========================================================================
    
    def update_user_tier(self, user_id: int, tier: str) -> None:
        """Update user's tier in the database."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users SET tier = ?, updated_at = ?
                WHERE id = ?
            """, (tier, datetime.now().isoformat(), user_id))
            conn.commit()
        
        logger.info(f"Updated user {user_id} tier to {tier}")
    
    def sync_user_tier_from_subscription(self, user_id: int) -> str:
        """
        Sync user's tier based on their subscription status.
        
        Returns:
            The updated tier
        """
        subscription = self.get_active_subscription(user_id)
        
        if subscription and subscription["status"] in ("active", "trialing"):
            new_tier = subscription["plan"]  # 'pro' or 'enterprise'
        else:
            new_tier = "free"
        
        self.update_user_tier(user_id, new_tier)
        return new_tier
    
    def get_user_id_from_customer(self, stripe_customer_id: str) -> Optional[int]:
        """Get user ID from Stripe customer ID."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id FROM stripe_customers
                WHERE stripe_customer_id = ?
            """, (stripe_customer_id,))
            row = cursor.fetchone()
            return row["user_id"] if row else None
    
    # =========================================================================
    # WEBHOOK HANDLING
    # =========================================================================
    
    def construct_webhook_event(self, payload: bytes, signature: str) -> Any:
        """
        Construct and verify a Stripe webhook event.
        
        Raises:
            ValueError if signature verification fails
        """
        if not self._stripe_available:
            raise ValueError("Stripe is not configured")
        
        if not STRIPE_WEBHOOK_SECRET:
            raise ValueError("Stripe webhook secret not configured")
        
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, STRIPE_WEBHOOK_SECRET
            )
            return event
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Webhook signature verification failed: {e}")
            raise ValueError("Invalid webhook signature")
    
    def handle_webhook_event(self, event: Any) -> Tuple[bool, str]:
        """
        Handle a Stripe webhook event.
        
        Returns:
            Tuple of (success, message)
        """
        event_type = event.get("type", "")
        data = event.get("data", {}).get("object", {})
        
        logger.info(f"Processing webhook event: {event_type}")
        
        try:
            if event_type == "checkout.session.completed":
                return self._handle_checkout_completed(data)
            
            elif event_type == "customer.subscription.created":
                return self._handle_subscription_created(data)
            
            elif event_type == "customer.subscription.updated":
                return self._handle_subscription_updated(data)
            
            elif event_type == "customer.subscription.deleted":
                return self._handle_subscription_deleted(data)
            
            elif event_type == "invoice.payment_succeeded":
                return self._handle_invoice_paid(data)
            
            elif event_type == "invoice.payment_failed":
                return self._handle_invoice_failed(data)
            
            else:
                logger.info(f"Unhandled webhook event type: {event_type}")
                return True, f"Unhandled event type: {event_type}"
                
        except Exception as e:
            logger.error(f"Error handling webhook {event_type}: {e}")
            return False, str(e)
    
    def _handle_checkout_completed(self, session: Dict) -> Tuple[bool, str]:
        """Handle successful checkout - upgrade user to pro."""
        customer_id = session.get("customer")
        subscription_id = session.get("subscription")
        
        user_id = self.get_user_id_from_customer(customer_id)
        if not user_id:
            # Try metadata
            user_id = session.get("metadata", {}).get("promptly_user_id")
            if user_id:
                user_id = int(user_id)
        
        if not user_id:
            return False, f"No user found for customer {customer_id}"
        
        # Update subscription record if subscription exists
        if subscription_id:
            self.upsert_subscription(user_id, subscription_id, "active", "pro")
        
        # Upgrade user tier
        self.update_user_tier(user_id, "pro")
        
        return True, f"Upgraded user {user_id} to pro"
    
    def _handle_subscription_created(self, subscription: Dict) -> Tuple[bool, str]:
        """Handle new subscription creation."""
        return self._sync_subscription(subscription, "created")
    
    def _handle_subscription_updated(self, subscription: Dict) -> Tuple[bool, str]:
        """Handle subscription updates (status changes, plan changes)."""
        return self._sync_subscription(subscription, "updated")
    
    def _handle_subscription_deleted(self, subscription: Dict) -> Tuple[bool, str]:
        """Handle subscription cancellation - downgrade user."""
        customer_id = subscription.get("customer")
        subscription_id = subscription.get("id")
        
        user_id = self.get_user_id_from_customer(customer_id)
        if not user_id:
            user_id = subscription.get("metadata", {}).get("promptly_user_id")
            if user_id:
                user_id = int(user_id)
        
        if not user_id:
            return False, f"No user found for subscription {subscription_id}"
        
        # Update subscription as canceled
        self.upsert_subscription(user_id, subscription_id, "canceled")
        
        # Downgrade user to free
        self.update_user_tier(user_id, "free")
        
        return True, f"Downgraded user {user_id} to free"
    
    def _sync_subscription(self, subscription: Dict, action: str) -> Tuple[bool, str]:
        """Sync subscription data from Stripe."""
        customer_id = subscription.get("customer")
        subscription_id = subscription.get("id")
        status = subscription.get("status")
        cancel_at_period_end = subscription.get("cancel_at_period_end", False)
        
        user_id = self.get_user_id_from_customer(customer_id)
        if not user_id:
            user_id = subscription.get("metadata", {}).get("promptly_user_id")
            if user_id:
                user_id = int(user_id)
        
        if not user_id:
            return False, f"No user found for subscription {subscription_id}"
        
        # Extract period dates
        period_start = None
        period_end = None
        if subscription.get("current_period_start"):
            period_start = datetime.fromtimestamp(subscription["current_period_start"])
        if subscription.get("current_period_end"):
            period_end = datetime.fromtimestamp(subscription["current_period_end"])
        
        # Determine plan from price
        plan = "pro"  # Default
        items = subscription.get("items", {}).get("data", [])
        if items:
            price_id = items[0].get("price", {}).get("id", "")
            # Could map price IDs to plans here if needed
        
        # Update subscription record
        self.upsert_subscription(
            user_id, subscription_id, status, plan,
            period_start, period_end, cancel_at_period_end
        )
        
        # Sync tier based on status
        if status in ("active", "trialing"):
            self.update_user_tier(user_id, plan)
        elif status in ("canceled", "unpaid", "incomplete_expired"):
            self.update_user_tier(user_id, "free")
        
        return True, f"Subscription {action} for user {user_id}: {status}"
    
    def _handle_invoice_paid(self, invoice: Dict) -> Tuple[bool, str]:
        """Handle successful payment."""
        subscription_id = invoice.get("subscription")
        if not subscription_id:
            return True, "No subscription on invoice"
        
        customer_id = invoice.get("customer")
        user_id = self.get_user_id_from_customer(customer_id)
        
        if user_id:
            # Ensure user is pro
            self.update_user_tier(user_id, "pro")
            return True, f"Payment successful for user {user_id}"
        
        return True, "Invoice paid (no user found)"
    
    def _handle_invoice_failed(self, invoice: Dict) -> Tuple[bool, str]:
        """Handle failed payment."""
        subscription_id = invoice.get("subscription")
        customer_id = invoice.get("customer")
        
        user_id = self.get_user_id_from_customer(customer_id)
        if user_id:
            logger.warning(f"Payment failed for user {user_id}")
            # Don't immediately downgrade - Stripe will retry
            # Could send notification here
        
        return True, f"Invoice payment failed (customer {customer_id})"


# Global service instance
_stripe_service = None


def get_stripe_service() -> StripeService:
    """Get or create the global Stripe service instance."""
    global _stripe_service
    if _stripe_service is None:
        _stripe_service = StripeService()
    return _stripe_service
