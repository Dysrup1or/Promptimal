#!/usr/bin/env python3
"""
Admin CLI for Catalyze.
Provides administrative commands for user management and system monitoring.

Usage:
    python admin_cli.py <command> [options]

Commands:
    list-users      List all registered users
    user-info       Get detailed info for a specific user
    change-tier     Change a user's subscription tier
    verify-user     Manually verify a user's email
    delete-user     Delete a user account
    usage-stats     Show usage statistics
    reset-password  Generate a password reset link for a user
    
Examples:
    python admin_cli.py list-users
    python admin_cli.py change-tier user@example.com pro
    python admin_cli.py verify-user user@example.com
    python admin_cli.py usage-stats --month 1 --year 2025
"""

import argparse
import sys
from datetime import datetime
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(__file__).rsplit('\\', 1)[0])

from auth.database import init_database, get_db_connection
from auth.auth_service import AuthService
from auth.logger import logger


def setup_database():
    """Ensure database is initialized."""
    init_database()


def list_users(args):
    """List all registered users."""
    setup_database()
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Build query
        query = """
            SELECT 
                u.id, u.email, u.first_name, u.last_name, 
                u.tier, u.email_verified, u.created_at
            FROM users u
            ORDER BY u.created_at DESC
        """
        
        if args.tier:
            query = query.replace("ORDER BY", f"WHERE u.tier = '{args.tier}' ORDER BY")
        
        if args.limit:
            query += f" LIMIT {args.limit}"
        
        cursor.execute(query)
        rows = cursor.fetchall()
    
    if not rows:
        print("No users found.")
        return
    
    # Print header
    print(f"\n{'ID':<6} {'Email':<35} {'Name':<25} {'Tier':<12} {'Verified':<10} {'Created':<20}")
    print("=" * 120)
    
    for row in rows:
        verified = "✓" if row["email_verified"] else "✗"
        created = str(row["created_at"])[:19] if row["created_at"] else "N/A"
        full_name = f"{row['first_name']} {row['last_name']}"[:24]
        
        print(f"{row['id']:<6} {row['email']:<35} {full_name:<25} {row['tier']:<12} {verified:<10} {created:<20}")
    
    print(f"\nTotal: {len(rows)} users")


def user_info(args):
    """Get detailed info for a specific user."""
    setup_database()
    auth = AuthService()
    
    user = auth.get_user_by_email(args.email)
    if not user:
        print(f"User not found: {args.email}")
        return
    
    # Get usage stats
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Current month usage
        now = datetime.now()
        cursor.execute("""
            SELECT count FROM usage 
            WHERE user_id = ? AND month = ? AND year = ?
        """, (user.id, now.month, now.year))
        row = cursor.fetchone()
        current_usage = row["count"] if row else 0
        
        # Total usage
        cursor.execute("""
            SELECT SUM(count) as total FROM usage WHERE user_id = ?
        """, (user.id,))
        row = cursor.fetchone()
        total_usage = row["total"] if row and row["total"] else 0
        
        # Active sessions
        cursor.execute("""
            SELECT COUNT(*) as count FROM sessions 
            WHERE user_id = ? AND expires_at > ?
        """, (user.id, datetime.now().isoformat()))
        row = cursor.fetchone()
        active_sessions = row["count"] if row else 0
    
    print(f"\n{'='*50}")
    print(f"User Information: {user.email}")
    print(f"{'='*50}")
    print(f"ID:              {user.id}")
    print(f"Name:            {user.full_name}")
    print(f"Email:           {user.email}")
    print(f"Tier:            {user.tier.upper()}")
    print(f"Email Verified:  {'Yes ✓' if user.email_verified else 'No ✗'}")
    print(f"Created:         {user.created_at}")
    print(f"Updated:         {user.updated_at}")
    print(f"")
    print(f"--- Usage ---")
    print(f"This Month:      {current_usage}")
    print(f"All Time:        {total_usage}")
    print(f"Active Sessions: {active_sessions}")
    print(f"{'='*50}\n")


def change_tier(args):
    """Change a user's subscription tier."""
    setup_database()
    auth = AuthService()
    
    valid_tiers = ['free', 'pro', 'enterprise']
    if args.tier not in valid_tiers:
        print(f"Invalid tier: {args.tier}")
        print(f"Valid tiers: {', '.join(valid_tiers)}")
        return
    
    user = auth.get_user_by_email(args.email)
    if not user:
        print(f"User not found: {args.email}")
        return
    
    old_tier = user.tier
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users SET tier = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (args.tier, user.id))
        conn.commit()
    
    logger.info(f"ADMIN | Changed tier for {args.email}: {old_tier} -> {args.tier}")
    print(f"✓ Changed tier for {args.email}: {old_tier.upper()} -> {args.tier.upper()}")


def verify_user(args):
    """Manually verify a user's email."""
    setup_database()
    auth = AuthService()
    
    user = auth.get_user_by_email(args.email)
    if not user:
        print(f"User not found: {args.email}")
        return
    
    if user.email_verified:
        print(f"User {args.email} is already verified.")
        return
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users SET email_verified = 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (user.id,))
        conn.commit()
    
    logger.info(f"ADMIN | Manually verified email for {args.email}")
    print(f"✓ Email verified for {args.email}")


def delete_user(args):
    """Delete a user account."""
    setup_database()
    auth = AuthService()
    
    user = auth.get_user_by_email(args.email)
    if not user:
        print(f"User not found: {args.email}")
        return
    
    if not args.force:
        confirm = input(f"Are you sure you want to delete {args.email}? (type 'yes' to confirm): ")
        if confirm.lower() != 'yes':
            print("Cancelled.")
            return
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Delete in order (foreign key constraints)
        cursor.execute("DELETE FROM email_verification_tokens WHERE user_id = ?", (user.id,))
        cursor.execute("DELETE FROM password_reset_tokens WHERE user_id = ?", (user.id,))
        cursor.execute("DELETE FROM sessions WHERE user_id = ?", (user.id,))
        cursor.execute("DELETE FROM usage WHERE user_id = ?", (user.id,))
        cursor.execute("DELETE FROM users WHERE id = ?", (user.id,))
        conn.commit()
    
    logger.info(f"ADMIN | Deleted user {args.email}")
    print(f"✓ Deleted user {args.email}")


def usage_stats(args):
    """Show usage statistics."""
    setup_database()
    
    now = datetime.now()
    month = args.month or now.month
    year = args.year or now.year
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Overall stats
        cursor.execute("SELECT COUNT(*) as count FROM users")
        total_users = cursor.fetchone()["count"]
        
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE email_verified = 1")
        verified_users = cursor.fetchone()["count"]
        
        cursor.execute("SELECT tier, COUNT(*) as count FROM users GROUP BY tier")
        tier_counts = {row["tier"]: row["count"] for row in cursor.fetchall()}
        
        # Usage stats for the specified month
        cursor.execute("""
            SELECT 
                SUM(count) as total,
                COUNT(DISTINCT user_id) as active_users,
                AVG(count) as avg_per_user
            FROM usage
            WHERE month = ? AND year = ?
        """, (month, year))
        row = cursor.fetchone()
        month_usage = row["total"] or 0
        active_users = row["active_users"] or 0
        avg_usage = row["avg_per_user"] or 0
        
        # Top users
        cursor.execute("""
            SELECT u.email, us.count
            FROM usage us
            JOIN users u ON us.user_id = u.id
            WHERE us.month = ? AND us.year = ?
            ORDER BY us.count DESC
            LIMIT 10
        """, (month, year))
        top_users = cursor.fetchall()
    
    print(f"\n{'='*50}")
    print(f"Usage Statistics - {month:02d}/{year}")
    print(f"{'='*50}")
    print(f"\n--- User Counts ---")
    print(f"Total Users:     {total_users}")
    print(f"Verified:        {verified_users} ({100*verified_users/total_users:.1f}%)" if total_users else "")
    print(f"")
    print(f"By Tier:")
    for tier in ['free', 'pro', 'enterprise']:
        count = tier_counts.get(tier, 0)
        print(f"  {tier.upper():<12} {count}")
    
    print(f"\n--- Monthly Usage ({month:02d}/{year}) ---")
    print(f"Total Optimizations:  {month_usage}")
    print(f"Active Users:         {active_users}")
    print(f"Avg per User:         {avg_usage:.1f}")
    
    if top_users:
        print(f"\n--- Top 10 Users ---")
        for i, row in enumerate(top_users, 1):
            print(f"  {i:2}. {row['email']:<35} {row['count']} optimizations")
    
    print(f"{'='*50}\n")


def reset_password(args):
    """Generate a password reset link for a user."""
    setup_database()
    auth = AuthService()
    
    user = auth.get_user_by_email(args.email)
    if not user:
        print(f"User not found: {args.email}")
        return
    
    success, message, token = auth.request_password_reset(args.email)
    
    if success and token:
        logger.info(f"ADMIN | Generated password reset for {args.email}")
        print(f"✓ Password reset token generated for {args.email}")
        print(f"\nReset Token (valid for 1 hour):")
        print(f"  {token}")
        print(f"\nIn production, this would be sent via email.")
    else:
        print(f"Failed: {message}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Catalyze Admin CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # list-users
    list_users_parser = subparsers.add_parser("list-users", help="List all users")
    list_users_parser.add_argument("--tier", choices=["free", "pro", "enterprise"], help="Filter by tier")
    list_users_parser.add_argument("--limit", type=int, help="Limit number of results")
    
    # user-info
    user_info_parser = subparsers.add_parser("user-info", help="Get user details")
    user_info_parser.add_argument("email", help="User email address")
    
    # change-tier
    change_tier_parser = subparsers.add_parser("change-tier", help="Change user tier")
    change_tier_parser.add_argument("email", help="User email address")
    change_tier_parser.add_argument("tier", choices=["free", "pro", "enterprise"], help="New tier")
    
    # verify-user
    verify_parser = subparsers.add_parser("verify-user", help="Manually verify user email")
    verify_parser.add_argument("email", help="User email address")
    
    # delete-user
    delete_parser = subparsers.add_parser("delete-user", help="Delete user account")
    delete_parser.add_argument("email", help="User email address")
    delete_parser.add_argument("--force", "-f", action="store_true", help="Skip confirmation")
    
    # usage-stats
    stats_parser = subparsers.add_parser("usage-stats", help="Show usage statistics")
    stats_parser.add_argument("--month", type=int, help="Month (1-12)")
    stats_parser.add_argument("--year", type=int, help="Year")
    
    # reset-password
    reset_parser = subparsers.add_parser("reset-password", help="Generate password reset")
    reset_parser.add_argument("email", help="User email address")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Dispatch to command handler
    commands = {
        "list-users": list_users,
        "user-info": user_info,
        "change-tier": change_tier,
        "verify-user": verify_user,
        "delete-user": delete_user,
        "usage-stats": usage_stats,
        "reset-password": reset_password,
    }
    
    handler = commands.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
