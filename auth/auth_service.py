"""
Authentication service for Promptly.
Handles user registration, login, logout, and session validation.
"""

import re
import uuid
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple

import bcrypt

from .database import get_db_connection, init_database
from .models import User, Session
from .logger import logger, log_auth_event
from .email_service import get_email_service


class AuthService:
    """Service for authentication operations."""
    
    # Session duration
    SESSION_DURATION_DAYS = 30
    
    # Token durations
    PASSWORD_RESET_DURATION_HOURS = 1
    EMAIL_VERIFICATION_DURATION_HOURS = 24
    
    # Validation constants
    MIN_PASSWORD_LENGTH = 8
    MAX_NAME_LENGTH = 50
    EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    
    def __init__(self):
        """Initialize auth service and ensure database exists."""
        init_database()
    
    # =========================================================================
    # VALIDATION METHODS
    # =========================================================================
    
    def validate_email(self, email: str) -> Tuple[bool, str]:
        """Validate email format."""
        email = email.strip().lower()
        if not email:
            return False, "Email is required."
        if not self.EMAIL_REGEX.match(email):
            return False, "Please enter a valid email address."
        return True, ""
    
    def validate_password(self, password: str) -> Tuple[bool, str]:
        """Validate password requirements."""
        if not password:
            return False, "Password is required."
        if len(password) < self.MIN_PASSWORD_LENGTH:
            return False, f"Password must be at least {self.MIN_PASSWORD_LENGTH} characters."
        return True, ""
    
    def validate_name(self, name: str, field: str = "Name") -> Tuple[bool, str]:
        """Validate name field."""
        name = name.strip()
        if not name:
            return False, f"{field} is required."
        if len(name) > self.MAX_NAME_LENGTH:
            return False, f"{field} must be less than {self.MAX_NAME_LENGTH} characters."
        return True, ""
    
    # =========================================================================
    # PASSWORD HASHING
    # =========================================================================
    
    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt."""
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash."""
        try:
            return bcrypt.checkpw(
                password.encode('utf-8'),
                password_hash.encode('utf-8')
            )
        except Exception:
            return False
    
    # =========================================================================
    # SESSION MANAGEMENT
    # =========================================================================
    
    def generate_session_token(self) -> str:
        """Generate a unique session token."""
        return str(uuid.uuid4())
    
    def hash_token(self, token: str) -> str:
        """Hash session token for storage."""
        return hashlib.sha256(token.encode()).hexdigest()
    
    def create_session(self, user_id: int) -> str:
        """Create a new session for user. Returns the raw token."""
        token = self.generate_session_token()
        hashed_token = self.hash_token(token)
        expires_at = datetime.now() + timedelta(days=self.SESSION_DURATION_DAYS)
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sessions (user_id, session_token, expires_at)
                VALUES (?, ?, ?)
            """, (user_id, hashed_token, expires_at.isoformat()))
            conn.commit()
        
        return token  # Return raw token for client storage
    
    def validate_session(self, token: str) -> Optional[User]:
        """Validate session token and return user if valid."""
        if not token:
            return None
        
        hashed_token = self.hash_token(token)
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Get session with user data
            cursor.execute("""
                SELECT s.*, u.*
                FROM sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.session_token = ?
            """, (hashed_token,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            # Check expiration
            session = Session.from_row(row)
            if session.is_expired:
                self.delete_session(token)
                return None
            
            # Return user using from_row for proper handling
            return User.from_row(row)
    
    def delete_session(self, token: str) -> None:
        """Delete a session (logout)."""
        hashed_token = self.hash_token(token)
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM sessions WHERE session_token = ?",
                (hashed_token,)
            )
            conn.commit()
    
    def delete_all_user_sessions(self, user_id: int) -> None:
        """Delete all sessions for a user."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM sessions WHERE user_id = ?",
                (user_id,)
            )
            conn.commit()
    
    # =========================================================================
    # USER MANAGEMENT
    # =========================================================================
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email address."""
        email = email.strip().lower()
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM users WHERE email = ?",
                (email,)
            )
            row = cursor.fetchone()
            if row:
                return User.from_row(row)
        return None
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM users WHERE id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            if row:
                return User.from_row(row)
        return None
    
    def email_exists(self, email: str) -> bool:
        """Check if email is already registered."""
        return self.get_user_by_email(email) is not None
    
    # =========================================================================
    # REGISTRATION & LOGIN
    # =========================================================================
    
    def register(
        self,
        email: str,
        first_name: str,
        last_name: str,
        password: str,
        confirm_password: str
    ) -> Tuple[Optional[User], Optional[str], Optional[str]]:
        """
        Register a new user.
        
        Returns:
            Tuple of (User, session_token, error_message)
            - On success: (User, token, None)
            - On failure: (None, None, error_message)
        """
        # Normalize inputs
        email = email.strip().lower()
        first_name = first_name.strip()
        last_name = last_name.strip()
        
        # Validate email
        valid, error = self.validate_email(email)
        if not valid:
            return None, None, error
        
        # Validate names
        valid, error = self.validate_name(first_name, "First name")
        if not valid:
            return None, None, error
        
        valid, error = self.validate_name(last_name, "Last name")
        if not valid:
            return None, None, error
        
        # Validate password
        valid, error = self.validate_password(password)
        if not valid:
            return None, None, error
        
        # Check passwords match
        if password != confirm_password:
            return None, None, "Passwords do not match."
        
        # Check email not taken
        if self.email_exists(email):
            return None, None, "An account with this email already exists. Try logging in."
        
        # Create user
        password_hash = self.hash_password(password)
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO users (email, first_name, last_name, password_hash)
                    VALUES (?, ?, ?, ?)
                """, (email, first_name, last_name, password_hash))
                conn.commit()
                user_id = cursor.lastrowid
            
            # Get the created user
            user = self.get_user_by_id(user_id)
            
            # Create session (auto-login)
            token = self.create_session(user_id)
            
            # Send verification email
            verification_token = self.create_verification_token(user_id)
            if verification_token:
                email_service = get_email_service()
                email_service.send_verification_email(
                    to_email=email,
                    token=verification_token,
                    first_name=first_name
                )
            
            log_auth_event("register", email=email, user_id=user_id, success=True)
            return user, token, None
            
        except Exception as e:
            log_auth_event("register", email=email, success=False, error=str(e))
            return None, None, f"Registration failed: {str(e)}"
    
    def login(self, email: str, password: str) -> Tuple[Optional[User], Optional[str], Optional[str]]:
        """
        Log in a user.
        
        Returns:
            Tuple of (User, session_token, error_message)
            - On success: (User, token, None)
            - On failure: (None, None, error_message)
        """
        email = email.strip().lower()
        
        # Validate inputs
        if not email or not password:
            return None, None, "Email and password are required."
        
        # Get user
        user = self.get_user_by_email(email)
        if not user:
            log_auth_event("login", email=email, success=False, reason="user_not_found")
            return None, None, "Invalid email or password."
        
        # Verify password
        if not self.verify_password(password, user.password_hash):
            log_auth_event("login", email=email, user_id=user.id, success=False, reason="invalid_password")
            return None, None, "Invalid email or password."
        
        # Check email verification (admin users bypass this check)
        if not user.email_verified and user.tier != "admin":
            log_auth_event("login", email=email, user_id=user.id, success=False, reason="email_not_verified")
            return None, None, "Please verify your email before logging in. Check your inbox for the verification link."
        
        # Create session
        token = self.create_session(user.id)
        
        log_auth_event("login", email=email, user_id=user.id, success=True)
        return user, token, None
    
    def logout(self, token: str) -> None:
        """Log out user by deleting session."""
        self.delete_session(token)
        logger.debug("User logged out")
    
    # =========================================================================
    # WAITLIST
    # =========================================================================
    
    def add_to_waitlist(self, email: str) -> Tuple[bool, str]:
        """Add email to upgrade waitlist."""
        email = email.strip().lower()
        
        valid, error = self.validate_email(email)
        if not valid:
            return False, error
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR IGNORE INTO waitlist (email) VALUES (?)",
                    (email,)
                )
                conn.commit()
                if cursor.rowcount > 0:
                    return True, "You've been added to the waitlist! We'll notify you when Pro is available."
                else:
                    return True, "You're already on the waitlist. We'll notify you soon!"
        except Exception as e:
            return False, f"Failed to join waitlist: {str(e)}"
    
    # =========================================================================
    # PASSWORD RESET
    # =========================================================================
    
    def generate_secure_token(self) -> str:
        """Generate a cryptographically secure token."""
        return secrets.token_urlsafe(32)
    
    def request_password_reset(self, email: str) -> Tuple[bool, str, Optional[str]]:
        """
        Request a password reset for an email.
        
        Returns:
            Tuple of (success, message, token)
            - token is returned only for development/testing
            - In production, send email instead
        """
        email = email.strip().lower()
        
        # Always return success message to prevent email enumeration
        success_msg = "If an account exists with this email, you'll receive a password reset link."
        
        # Validate email format
        valid, error = self.validate_email(email)
        if not valid:
            return False, error, None
        
        # Get user
        user = self.get_user_by_email(email)
        if not user:
            # Don't reveal that email doesn't exist
            return True, success_msg, None
        
        # Generate token
        token = self.generate_secure_token()
        hashed_token = self.hash_token(token)
        expires_at = datetime.now() + timedelta(hours=self.PASSWORD_RESET_DURATION_HOURS)
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Invalidate any existing tokens for this user
                cursor.execute(
                    "UPDATE password_reset_tokens SET used = 1 WHERE user_id = ?",
                    (user.id,)
                )
                
                # Create new token
                cursor.execute("""
                    INSERT INTO password_reset_tokens (user_id, token, expires_at)
                    VALUES (?, ?, ?)
                """, (user.id, hashed_token, expires_at.isoformat()))
                conn.commit()
            
            # Send password reset email
            email_service = get_email_service()
            email_sent = email_service.send_password_reset_email(
                to_email=email,
                token=token,
                first_name=user.first_name
            )
            
            log_auth_event("password_reset_request", email=email, user_id=user.id, success=True)
            # Return token for development if email not configured
            return True, success_msg, token if not email_sent else None
            
        except Exception as e:
            log_auth_event("password_reset_request", email=email, success=False, error=str(e))
            return False, f"Failed to create reset token: {str(e)}", None
    
    def reset_password(self, token: str, new_password: str, confirm_password: str) -> Tuple[bool, str]:
        """
        Reset password using a valid token.
        
        Returns:
            Tuple of (success, message)
        """
        if not token:
            return False, "Invalid reset link."
        
        # Validate passwords
        valid, error = self.validate_password(new_password)
        if not valid:
            return False, error
        
        if new_password != confirm_password:
            return False, "Passwords do not match."
        
        hashed_token = self.hash_token(token)
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Find valid token
                cursor.execute("""
                    SELECT prt.*, u.id as uid
                    FROM password_reset_tokens prt
                    JOIN users u ON prt.user_id = u.id
                    WHERE prt.token = ? AND prt.used = 0
                """, (hashed_token,))
                
                row = cursor.fetchone()
                if not row:
                    return False, "Invalid or expired reset link."
                
                # Check expiration
                expires_at = row["expires_at"]
                if isinstance(expires_at, str):
                    expires_at = datetime.fromisoformat(expires_at)
                
                if datetime.now() > expires_at:
                    return False, "This reset link has expired. Please request a new one."
                
                user_id = row["user_id"]
                
                # Hash new password
                password_hash = self.hash_password(new_password)
                
                # Update password
                cursor.execute("""
                    UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (password_hash, user_id))
                
                # Mark token as used
                cursor.execute(
                    "UPDATE password_reset_tokens SET used = 1 WHERE token = ?",
                    (hashed_token,)
                )
                
                # Invalidate all sessions (security measure)
                cursor.execute(
                    "DELETE FROM sessions WHERE user_id = ?",
                    (user_id,)
                )
                
                conn.commit()
            
            log_auth_event("password_reset", user_id=user_id, success=True)
            return True, "Password reset successfully! You can now log in with your new password."
            
        except Exception as e:
            log_auth_event("password_reset", success=False, error=str(e))
            return False, f"Failed to reset password: {str(e)}"
    
    # =========================================================================
    # EMAIL VERIFICATION
    # =========================================================================
    
    def create_verification_token(self, user_id: int) -> Optional[str]:
        """
        Create an email verification token for a user.
        
        Returns:
            The raw token (for sending in email) or None on failure
        """
        token = self.generate_secure_token()
        hashed_token = self.hash_token(token)
        expires_at = datetime.now() + timedelta(hours=self.EMAIL_VERIFICATION_DURATION_HOURS)
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Invalidate any existing tokens
                cursor.execute(
                    "UPDATE email_verification_tokens SET used = 1 WHERE user_id = ?",
                    (user_id,)
                )
                
                # Create new token
                cursor.execute("""
                    INSERT INTO email_verification_tokens (user_id, token, expires_at)
                    VALUES (?, ?, ?)
                """, (user_id, hashed_token, expires_at.isoformat()))
                conn.commit()
            
            return token
            
        except Exception:
            return None
    
    def verify_email(self, token: str) -> Tuple[bool, str]:
        """
        Verify a user's email using the verification token.
        
        Returns:
            Tuple of (success, message)
        """
        if not token:
            return False, "Invalid verification link."
        
        hashed_token = self.hash_token(token)
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Find valid token
                cursor.execute("""
                    SELECT evt.*, u.id as uid, u.email_verified
                    FROM email_verification_tokens evt
                    JOIN users u ON evt.user_id = u.id
                    WHERE evt.token = ? AND evt.used = 0
                """, (hashed_token,))
                
                row = cursor.fetchone()
                if not row:
                    return False, "Invalid or expired verification link."
                
                # Check if already verified
                if row["email_verified"]:
                    return True, "Your email is already verified!"
                
                # Check expiration
                expires_at = row["expires_at"]
                if isinstance(expires_at, str):
                    expires_at = datetime.fromisoformat(expires_at)
                
                if datetime.now() > expires_at:
                    return False, "This verification link has expired. Please request a new one."
                
                user_id = row["user_id"]
                
                # Mark email as verified
                cursor.execute("""
                    UPDATE users SET email_verified = 1, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (user_id,))
                
                # Mark token as used
                cursor.execute(
                    "UPDATE email_verification_tokens SET used = 1 WHERE token = ?",
                    (hashed_token,)
                )
                
                conn.commit()
            
            # Send welcome email after verification
            user = self.get_user_by_id(user_id)
            if user:
                email_service = get_email_service()
                email_service.send_welcome_email(
                    to_email=user.email,
                    first_name=user.first_name
                )
            
            log_auth_event("email_verified", user_id=user_id, success=True)
            return True, "Email verified successfully!"
            
        except Exception as e:
            log_auth_event("email_verified", success=False, error=str(e))
            return False, f"Verification failed: {str(e)}"
    
    def resend_verification_email(self, user_id: int) -> Tuple[bool, str, Optional[str]]:
        """
        Resend verification email for a user.
        
        Returns:
            Tuple of (success, message, token)
            - token is returned for development/testing
        """
        user = self.get_user_by_id(user_id)
        if not user:
            return False, "User not found.", None
        
        if user.email_verified:
            return True, "Your email is already verified!", None
        
        token = self.create_verification_token(user_id)
        if not token:
            return False, "Failed to create verification token.", None
        
        # Send verification email
        email_service = get_email_service()
        email_sent = email_service.send_verification_email(
            to_email=user.email,
            token=token,
            first_name=user.first_name
        )
        
        # Return token for development if email not configured
        return True, "Verification email sent! Please check your inbox.", token if not email_sent else None
    
    def is_email_verified(self, user_id: int) -> bool:
        """Check if a user's email is verified."""
        user = self.get_user_by_id(user_id)
        return user.email_verified if user else False
