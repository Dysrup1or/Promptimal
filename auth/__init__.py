"""
Authentication module for Promptly 3.0
======================================
Provides user authentication, session management, usage tracking, and logging.
"""

from .database import init_database, get_db_connection
from .models import User, Session, Usage
from .auth_service import AuthService
from .usage_service import UsageService
from .logger import (
    logger,
    log_auth_event,
    log_usage_event,
    log_llm_call,
    log_db_operation,
    log_request,
    mask_email,
    mask_sensitive,
)

__all__ = [
    'init_database',
    'get_db_connection', 
    'User',
    'Session',
    'Usage',
    'AuthService',
    'UsageService',
    # Logging
    'logger',
    'log_auth_event',
    'log_usage_event',
    'log_llm_call',
    'log_db_operation',
    'log_request',
    'mask_email',
    'mask_sensitive',
]
