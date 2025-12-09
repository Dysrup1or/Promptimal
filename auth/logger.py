# ==============================================
# PROMPTLY 3.0 - STRUCTURED LOGGING
# ==============================================
"""
Centralized logging configuration using Loguru.

Features:
- Console output with color coding
- Rotating file logs
- Structured JSON logs for production
- Context-aware logging with user/session info
"""

import os
import sys
from pathlib import Path
from loguru import logger

# ==============================================
# CONFIGURATION
# ==============================================

# Log levels: TRACE < DEBUG < INFO < SUCCESS < WARNING < ERROR < CRITICAL
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

# Log directory
LOG_DIR = Path(__file__).parent.parent / "logs"

# Environment detection
IS_PRODUCTION = bool(os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("DATABASE_URL"))

# ==============================================
# LOG FORMATS
# ==============================================

# Console format (colorful, human-readable)
CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<level>{message}</level>"
)

# File format (structured, parseable)
FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
    "{level: <8} | "
    "{name}:{function}:{line} | "
    "{message}"
)

# JSON format for production (structured logs for log aggregation)
JSON_FORMAT = "{message}"


# ==============================================
# LOGGER SETUP
# ==============================================

def setup_logger():
    """
    Configure the global logger with appropriate handlers.
    
    In development: Console (colored) + File (rotating)
    In production: Console (simple) + JSON file for log aggregation
    """
    # Remove default handler
    logger.remove()
    
    # Console handler - always enabled
    logger.add(
        sys.stderr,
        format=CONSOLE_FORMAT,
        level=LOG_LEVEL,
        colorize=not IS_PRODUCTION,  # No colors in production (logs may be parsed)
    )
    
    # Create logs directory if needed (skip in production - use stdout only)
    if not IS_PRODUCTION:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        
        # File handler - rotating log files
        logger.add(
            LOG_DIR / "promptly_{time:YYYY-MM-DD}.log",
            format=FILE_FORMAT,
            level="DEBUG",  # Capture more detail in files
            rotation="10 MB",  # Rotate when file reaches 10MB
            retention="7 days",  # Keep logs for 7 days
            compression="zip",  # Compress old logs
            enqueue=True,  # Thread-safe
        )
        
        # Error-specific log file
        logger.add(
            LOG_DIR / "errors_{time:YYYY-MM-DD}.log",
            format=FILE_FORMAT,
            level="ERROR",
            rotation="10 MB",
            retention="30 days",  # Keep errors longer
            compression="zip",
            enqueue=True,
        )
    
    return logger


# ==============================================
# CONTEXTUAL LOGGING HELPERS
# ==============================================

def log_auth_event(event: str, email: str = None, user_id: int = None, success: bool = True, **kwargs):
    """
    Log authentication-related events with consistent structure.
    
    Args:
        event: Event type (login, logout, register, password_reset, etc.)
        email: User email (masked for privacy)
        user_id: User ID if available
        success: Whether the operation succeeded
        **kwargs: Additional context
    """
    masked_email = mask_email(email) if email else None
    
    log_data = {
        "event": event,
        "email": masked_email,
        "user_id": user_id,
        "success": success,
        **kwargs
    }
    
    if success:
        logger.info(f"AUTH | {event} | {log_data}")
    else:
        logger.warning(f"AUTH | {event} FAILED | {log_data}")


def log_usage_event(user_id: int, action: str, tokens: int = 0, **kwargs):
    """
    Log usage/quota events.
    
    Args:
        user_id: User ID
        action: Action type (optimize, check_quota, etc.)
        tokens: Token count if applicable
        **kwargs: Additional context
    """
    log_data = {
        "user_id": user_id,
        "action": action,
        "tokens": tokens,
        **kwargs
    }
    logger.info(f"USAGE | {action} | {log_data}")


def log_llm_call(model: str, prompt_tokens: int, completion_tokens: int, duration_ms: float, success: bool = True, error: str = None):
    """
    Log LLM API calls for monitoring and debugging.
    
    Args:
        model: Model name
        prompt_tokens: Input token count
        completion_tokens: Output token count
        duration_ms: Call duration in milliseconds
        success: Whether the call succeeded
        error: Error message if failed
    """
    log_data = {
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "duration_ms": round(duration_ms, 2),
        "success": success,
    }
    
    if error:
        log_data["error"] = error
        logger.error(f"LLM | CALL FAILED | {log_data}")
    else:
        logger.info(f"LLM | CALL | {log_data}")


def log_db_operation(operation: str, table: str, duration_ms: float = None, success: bool = True, error: str = None, **kwargs):
    """
    Log database operations for debugging and performance monitoring.
    
    Args:
        operation: Operation type (INSERT, SELECT, UPDATE, DELETE)
        table: Table name
        duration_ms: Operation duration
        success: Whether operation succeeded
        error: Error message if failed
        **kwargs: Additional context
    """
    log_data = {
        "operation": operation,
        "table": table,
        **kwargs
    }
    
    if duration_ms is not None:
        log_data["duration_ms"] = round(duration_ms, 2)
    
    if error:
        log_data["error"] = error
        logger.error(f"DB | {operation} FAILED | {log_data}")
    else:
        logger.debug(f"DB | {operation} | {log_data}")


def log_request(endpoint: str, method: str = "GET", user_id: int = None, duration_ms: float = None, status: int = 200):
    """
    Log HTTP/page requests for analytics.
    
    Args:
        endpoint: Page or endpoint name
        method: HTTP method
        user_id: User ID if authenticated
        duration_ms: Request duration
        status: HTTP status code
    """
    log_data = {
        "endpoint": endpoint,
        "method": method,
        "user_id": user_id,
        "status": status,
    }
    
    if duration_ms is not None:
        log_data["duration_ms"] = round(duration_ms, 2)
    
    logger.info(f"REQUEST | {method} {endpoint} | {log_data}")


# ==============================================
# UTILITY FUNCTIONS
# ==============================================

def mask_email(email: str) -> str:
    """
    Mask email for privacy in logs.
    
    Example: john.doe@example.com -> j*******@example.com
    """
    if not email or "@" not in email:
        return "***"
    
    local, domain = email.split("@", 1)
    
    if len(local) <= 2:
        masked_local = local[0] + "*" * (len(local) - 1)
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
    
    return f"{masked_local}@{domain}"


def mask_sensitive(value: str, show_chars: int = 4) -> str:
    """
    Mask sensitive data, showing only first/last few characters.
    
    Example: "secret_token_12345" -> "secr***************2345"
    """
    if not value or len(value) <= show_chars * 2:
        return "*" * len(value) if value else "***"
    
    return value[:show_chars] + "*" * (len(value) - show_chars * 2) + value[-show_chars:]


# ==============================================
# INITIALIZATION
# ==============================================

# Setup logger on module import
setup_logger()

# Re-export logger for easy imports
__all__ = [
    "logger",
    "log_auth_event",
    "log_usage_event", 
    "log_llm_call",
    "log_db_operation",
    "log_request",
    "mask_email",
    "mask_sensitive",
    "setup_logger",
]
