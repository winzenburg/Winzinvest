#!/usr/bin/env python3
"""
Centralized logging configuration with automatic rotation.

Prevents log files from growing unbounded. Use this instead of logging.basicConfig
in any script that runs frequently (snapshots, monitors, executors, schedulers).

Usage:
    from logging_config import setup_rotating_logger
    logger = setup_rotating_logger(__name__, "my_script.log")
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


def setup_rotating_logger(
    name: str,
    log_filename: str,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB default
    backup_count: int = 3,
    level: int = logging.INFO,
    logs_dir: Optional[Path] = None,
) -> logging.Logger:
    """
    Configure a logger with rotating file handler and console output.
    
    Args:
        name: Logger name (typically __name__)
        log_filename: Name of log file (e.g. "portfolio_snapshot.log")
        max_bytes: Maximum size before rotation (default 10MB)
        backup_count: Number of backup files to keep (default 3)
        level: Logging level (default INFO)
        logs_dir: Directory for logs (defaults to ../logs relative to this file)
    
    Returns:
        Configured logger instance
    
    Example:
        logger = setup_rotating_logger(__name__, "my_script.log")
        logger.info("Script started")
    """
    if logs_dir is None:
        logs_dir = Path(__file__).resolve().parent.parent / "logs"
    
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / log_filename
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Rotating file handler
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(level)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    
    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # Prevent propagation to root logger
    logger.propagate = False
    
    return logger


def get_logger_for_script(script_name: str, max_mb: int = 10) -> logging.Logger:
    """
    Convenience function - automatically derives log filename from script name.
    
    Example:
        # In portfolio_snapshot.py:
        logger = get_logger_for_script(__name__)
        # Creates logs/portfolio_snapshot.log with 10MB rotation
    """
    if '.' in script_name:
        # Handle module names like 'agents.dashboard_api'
        script_name = script_name.split('.')[-1]
    
    log_filename = f"{script_name}.log"
    return setup_rotating_logger(
        script_name,
        log_filename,
        max_bytes=max_mb * 1024 * 1024,
        backup_count=3
    )
