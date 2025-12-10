"""
Database module for Promptly authentication.
Supports both SQLite (local development) and PostgreSQL (Railway production).

Database selection:
- If DATABASE_URL is set, use PostgreSQL
- Otherwise, use SQLite in ./data/promptly.db
"""

import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Generator, Any, Union
from urllib.parse import urlparse

# Check for PostgreSQL (Railway sets DATABASE_URL)
DATABASE_URL = os.getenv("DATABASE_URL", "")
USE_POSTGRES = bool(DATABASE_URL)

# SQLite fallback for local development (override with PROMPTLY_DB_PATH for tests/custom setups)
_CUSTOM_DB_PATH = os.getenv("PROMPTLY_DB_PATH", "").strip()
if _CUSTOM_DB_PATH:
    DB_PATH = Path(_CUSTOM_DB_PATH)
    DATA_DIR = DB_PATH.parent
else:
    DATA_DIR = Path(__file__).parent.parent / "data"
    DB_PATH = DATA_DIR / "promptly.db"

# PostgreSQL connection (imported lazily to avoid dependency issues)
_pg_pool = None


def _get_pg_connection():
    """Get PostgreSQL connection from pool."""
    global _pg_pool
    if _pg_pool is None:
        try:
            import psycopg2
            from psycopg2 import pool
            _pg_pool = pool.SimpleConnectionPool(1, 10, DATABASE_URL)
        except ImportError:
            raise ImportError("psycopg2 not installed. Run: pip install psycopg2-binary")
    return _pg_pool.getconn()


def _release_pg_connection(conn):
    """Return connection to pool."""
    global _pg_pool
    if _pg_pool:
        _pg_pool.putconn(conn)


def init_database() -> None:
    """Initialize the database with required tables."""
    if USE_POSTGRES:
        _init_postgres()
    else:
        _init_sqlite()


def _init_sqlite() -> None:
    """Initialize SQLite database."""
    DATA_DIR.mkdir(exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            tier TEXT DEFAULT 'free',
            email_verified INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Migration: Add email_verified column if missing (for existing databases)
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'email_verified' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN email_verified INTEGER DEFAULT 0")
    
    # Usage tracking (per user, per month)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            month INTEGER NOT NULL,
            year INTEGER NOT NULL,
            count INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, month, year)
        )
    """)
    
    # Sessions for persistent login
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_token TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    # Waitlist for upgrade notifications
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS waitlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Password reset tokens
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            used INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    # Email verification tokens
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS email_verification_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            used INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(session_token)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_user_month ON usage(user_id, month, year)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_password_reset_token ON password_reset_tokens(token)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_verification_token ON email_verification_tokens(token)")
    
    conn.commit()
    conn.close()


def _init_postgres() -> None:
    """Initialize PostgreSQL database."""
    conn = _get_pg_connection()
    cursor = conn.cursor()
    
    try:
        # Users table (PostgreSQL syntax)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                tier TEXT DEFAULT 'free',
                email_verified BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Migration: Add email_verified column if missing
        cursor.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='users' AND column_name='email_verified'
                ) THEN
                    ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT FALSE;
                END IF;
            END $$;
        """)
        
        # Usage tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usage (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                month INTEGER NOT NULL,
                year INTEGER NOT NULL,
                count INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, month, year)
            )
        """)
        
        # Sessions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                session_token TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL
            )
        """)
        
        # Waitlist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS waitlist (
                id SERIAL PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Password reset tokens
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                token TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                used BOOLEAN DEFAULT FALSE
            )
        """)
        
        # Email verification tokens
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS email_verification_tokens (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                token TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                used BOOLEAN DEFAULT FALSE
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(session_token)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_user_month ON usage(user_id, month, year)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_password_reset_token ON password_reset_tokens(token)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_verification_token ON email_verification_tokens(token)")
        
        conn.commit()
    finally:
        _release_pg_connection(conn)


class PostgresRowWrapper:
    """Wrapper to make psycopg2 cursor results behave like sqlite3.Row."""
    def __init__(self, cursor, row):
        self._data = {}
        if row and cursor.description:
            for i, col in enumerate(cursor.description):
                self._data[col[0]] = row[i]
    
    def __getitem__(self, key):
        return self._data[key]
    
    def keys(self):
        return self._data.keys()


@contextmanager
def get_db_connection() -> Generator[Any, None, None]:
    """Context manager for database connections."""
    if USE_POSTGRES:
        conn = _get_pg_connection()
        try:
            yield PostgresConnection(conn)
        finally:
            _release_pg_connection(conn)
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()


class PostgresConnection:
    """Wrapper for PostgreSQL connection with sqlite3-like interface."""
    
    def __init__(self, conn):
        self._conn = conn
        self._cursor = None
    
    def cursor(self):
        self._cursor = PostgresCursor(self._conn.cursor())
        return self._cursor
    
    def commit(self):
        self._conn.commit()
    
    def close(self):
        pass  # Handled by pool


class PostgresCursor:
    """Wrapper for PostgreSQL cursor with sqlite3-like interface."""
    
    def __init__(self, cursor):
        self._cursor = cursor
        self._lastrowid = None
    
    def execute(self, sql, params=None):
        # Convert SQLite ? placeholders to PostgreSQL %s
        sql = sql.replace("?", "%s")
        
        # Handle INSERT...RETURNING for lastrowid
        if sql.strip().upper().startswith("INSERT") and "RETURNING" not in sql.upper():
            sql = sql.rstrip().rstrip(";") + " RETURNING id"
            self._cursor.execute(sql, params or ())
            result = self._cursor.fetchone()
            if result:
                self._lastrowid = result[0]
        else:
            self._cursor.execute(sql, params or ())
    
    def fetchone(self):
        row = self._cursor.fetchone()
        if row:
            return PostgresRowWrapper(self._cursor, row)
        return None
    
    def fetchall(self):
        rows = self._cursor.fetchall()
        return [PostgresRowWrapper(self._cursor, row) for row in rows]
    
    @property
    def lastrowid(self):
        return self._lastrowid
    
    @property
    def rowcount(self):
        return self._cursor.rowcount


def reset_database() -> None:
    """Reset database (for testing only). Drops all tables and recreates."""
    if USE_POSTGRES:
        conn = _get_pg_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DROP TABLE IF EXISTS email_verification_tokens CASCADE")
            cursor.execute("DROP TABLE IF EXISTS password_reset_tokens CASCADE")
            cursor.execute("DROP TABLE IF EXISTS waitlist CASCADE")
            cursor.execute("DROP TABLE IF EXISTS sessions CASCADE")
            cursor.execute("DROP TABLE IF EXISTS usage CASCADE")
            cursor.execute("DROP TABLE IF EXISTS users CASCADE")
            conn.commit()
        finally:
            _release_pg_connection(conn)
    else:
        if DB_PATH.exists():
            DB_PATH.unlink()
    init_database()
