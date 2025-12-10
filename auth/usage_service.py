"""
Usage tracking service for Promptly.
Handles per-user, per-month usage tracking with tier-based limits.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Iterable

from .database import get_db_connection, init_database
from .models import Usage
from .logger import log_usage_event

# Import limits from config
import sys
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
        """Initialize usage service and ensure database exists, then attempt snapshot restore."""
        init_database()
        self._maybe_restore_from_snapshot()

    @property
    def snapshot_path(self) -> Path:
        """Return snapshot path, overridable via PROMPTLY_USAGE_SNAPSHOT for stability."""
        env_path = os.getenv("PROMPTLY_USAGE_SNAPSHOT", "").strip()
        if env_path:
            return Path(env_path)
        return Path(__file__).parent.parent / "data" / "usage_snapshot.json"

    # ------------------------------------------------------------------
    # Snapshot helpers (for persistence across deploys/code updates)
    # ------------------------------------------------------------------
    def _load_snapshot(self) -> list[dict]:
        path = self.snapshot_path
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text())
        except Exception:
            return []

    def _write_snapshot(self, rows: Iterable[dict]) -> None:
        path = self.snapshot_path
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(list(rows), indent=2))
        except Exception:
            # Snapshot failures should not block runtime usage
            pass

    def _snapshot_all_usage(self) -> None:
        """Persist all usage rows to snapshot for recovery after code/data migrations."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, month, year, count FROM usage")
            rows = cursor.fetchall() or []
            payload = [
                {
                    "user_id": r["user_id"],
                    "month": r["month"],
                    "year": r["year"],
                    "count": r["count"],
                }
                for r in rows
            ]
        self._write_snapshot(payload)

    def _maybe_restore_from_snapshot(self) -> None:
        """If usage table is empty, restore counts from snapshot to protect against resets."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(1) as c FROM usage")
            row = cursor.fetchone()
            has_data = row and (row["c"] or row[0])

        if has_data:
            return

        snapshot = self._load_snapshot()
        if not snapshot:
            return

        with get_db_connection() as conn:
            cursor = conn.cursor()
            for rec in snapshot:
                cursor.execute(
                    """
                    INSERT INTO usage (user_id, month, year, count, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(user_id, month, year) DO UPDATE SET
                        count=excluded.count,
                        updated_at=excluded.updated_at
                    """,
                    (
                        rec.get("user_id"),
                        rec.get("month"),
                        rec.get("year"),
                        rec.get("count", 0),
                        datetime.now().isoformat(),
                    ),
                )
            conn.commit()
    
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
        self._snapshot_all_usage()
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
        self._snapshot_all_usage()
