"""
Data models for Promptly authentication.
Uses dataclasses for clean, type-safe data structures.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class User:
    """User account model."""
    id: int
    email: str
    first_name: str
    last_name: str
    password_hash: str
    tier: str = "free"  # 'free', 'pro', 'enterprise', 'admin'
    email_verified: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @property
    def full_name(self) -> str:
        """Return user's full name."""
        return f"{self.first_name} {self.last_name}"
    
    @property
    def is_pro(self) -> bool:
        """Check if user has pro tier or above."""
        return self.tier in ("pro", "enterprise", "admin")
    
    @property
    def is_enterprise(self) -> bool:
        """Check if user has enterprise tier."""
        return self.tier == "enterprise"
    
    @property
    def is_admin(self) -> bool:
        """Check if user has admin tier (unlimited access)."""
        return self.tier == "admin"
    
    @classmethod
    def from_row(cls, row) -> "User":
        """Create User from database row."""
        # Handle email_verified column (may not exist in older databases)
        email_verified = False
        try:
            email_verified = bool(row["email_verified"])
        except (KeyError, TypeError):
            pass
        
        return cls(
            id=row["id"],
            email=row["email"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            password_hash=row["password_hash"],
            tier=row["tier"],
            email_verified=email_verified,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass
class Session:
    """User session model."""
    id: int
    user_id: int
    session_token: str
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    
    @property
    def is_expired(self) -> bool:
        """Check if session has expired."""
        if self.expires_at is None:
            return True
        # Handle string dates from SQLite
        if isinstance(self.expires_at, str):
            expires = datetime.fromisoformat(self.expires_at)
        else:
            expires = self.expires_at
        return datetime.now() > expires
    
    @classmethod
    def from_row(cls, row) -> "Session":
        """Create Session from database row."""
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            session_token=row["session_token"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
        )


@dataclass
class Usage:
    """Monthly usage tracking model."""
    id: int
    user_id: int
    month: int
    year: int
    count: int = 0
    updated_at: Optional[datetime] = None
    
    @classmethod
    def from_row(cls, row) -> "Usage":
        """Create Usage from database row."""
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            month=row["month"],
            year=row["year"],
            count=row["count"],
            updated_at=row["updated_at"],
        )
