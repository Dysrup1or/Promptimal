"""
Usage tracking service for Promptly.
Handles per-user, per-month usage tracking with tier-based limits.
"""

from datetime import datetime
from typing import Optional

from .database import get_db_connection, init_database
from .models import Usage
from .logger import log_usage_event

# Import limits from config
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from consensus_prompt_optimizer.config import (
    FREE_TIER_MONTHLY_LIMIT,
    PRO_TIER_MONTHLY_LIMIT,
    ENTERPRISE_TIER_LIMIT,
)


class UsageService:
    """Service for usage tracking operations."""
    
    # Tier limits mapping
    TIER_LIMITS = {
        "free": FREE_TIER_MONTHLY_LIMIT,      # 100
        "pro": PRO_TIER_MONTHLY_LIMIT,         # 500
        "enterprise": ENTERPRISE_TIER_LIMIT,   # None (unlimited)
    }
    
    def __init__(self):
        """Initialize usage service and ensure database exists."""
        init_database()
    
    def get_limit_for_tier(self, tier: str) -> Optional[int]:
        """Get the monthly limit for a tier. None means unlimited."""
        return self.TIER_LIMITS.get(tier, FREE_TIER_MONTHLY_LIMIT)
    
    def get_usage(self, user_id: int, month: int = None, year: int = None) -> Usage:
        """
        Get usage for a user for a specific month.
        Creates a record if it doesn't exist.
        
        Args:
            user_id: The user's ID
            month: Month number (1-12). Defaults to current month.
            year: Year number. Defaults to current year.
        
        Returns:
            Usage object with current count
        """
        if month is None:
            month = datetime.now().month
        if year is None:
            year = datetime.now().year
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Try to get existing usage
            cursor.execute("""
                SELECT * FROM usage
                WHERE user_id = ? AND month = ? AND year = ?
            """, (user_id, month, year))
            
            row = cursor.fetchone()
            if row:
                return Usage.from_row(row)
            
            # Create new usage record
            cursor.execute("""
                INSERT INTO usage (user_id, month, year, count)
                VALUES (?, ?, ?, 0)
            """, (user_id, month, year))
            conn.commit()
            
            # Return the created record
            cursor.execute("""
                SELECT * FROM usage
                WHERE user_id = ? AND month = ? AND year = ?
            """, (user_id, month, year))
            
            row = cursor.fetchone()
            return Usage.from_row(row)
    
    def increment_usage(self, user_id: int, month: int = None, year: int = None) -> Usage:
        """
        Increment usage count for a user.
        
        Args:
            user_id: The user's ID
            month: Month number (1-12). Defaults to current month.
            year: Year number. Defaults to current year.
        
        Returns:
            Updated Usage object
        """
        if month is None:
            month = datetime.now().month
        if year is None:
            year = datetime.now().year
        
        # Ensure record exists
        self.get_usage(user_id, month, year)
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE usage
                SET count = count + 1, updated_at = ?
                WHERE user_id = ? AND month = ? AND year = ?
            """, (datetime.now().isoformat(), user_id, month, year))
            conn.commit()
        
        # Return updated usage
        updated_usage = self.get_usage(user_id, month, year)
        log_usage_event(user_id, "increment", count=updated_usage.count, month=month, year=year)
        return updated_usage
    
    def check_limit(self, user_id: int, tier: str, month: int = None, year: int = None) -> tuple[bool, int, Optional[int]]:
        """
        Check if user is within their usage limit.
        
        Args:
            user_id: The user's ID
            tier: User's subscription tier
            month: Month number. Defaults to current month.
            year: Year number. Defaults to current year.
        
        Returns:
            Tuple of (is_within_limit, current_count, limit)
            - limit is None for unlimited tiers
        """
        usage = self.get_usage(user_id, month, year)
        limit = self.get_limit_for_tier(tier)
        
        if limit is None:
            # Unlimited
            return True, usage.count, None
        
        return usage.count < limit, usage.count, limit
    
    def get_remaining(self, user_id: int, tier: str, month: int = None, year: int = None) -> Optional[int]:
        """
        Get remaining requests for the month.
        
        Returns:
            Number of remaining requests, or None if unlimited.
        """
        usage = self.get_usage(user_id, month, year)
        limit = self.get_limit_for_tier(tier)
        
        if limit is None:
            return None
        
        return max(0, limit - usage.count)
    
    def get_usage_percentage(self, user_id: int, tier: str, month: int = None, year: int = None) -> float:
        """
        Get usage as a percentage of limit.
        
        Returns:
            Float from 0.0 to 1.0+ (can exceed 1.0 if over limit).
            Returns 0.0 for unlimited tiers.
        """
        usage = self.get_usage(user_id, month, year)
        limit = self.get_limit_for_tier(tier)
        
        if limit is None or limit == 0:
            return 0.0
        
        return usage.count / limit
    
    def reset_usage(self, user_id: int, month: int = None, year: int = None) -> None:
        """Reset usage count for a user (admin function)."""
        if month is None:
            month = datetime.now().month
        if year is None:
            year = datetime.now().year
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE usage
                SET count = 0, updated_at = ?
                WHERE user_id = ? AND month = ? AND year = ?
            """, (datetime.now().isoformat(), user_id, month, year))
            conn.commit()
