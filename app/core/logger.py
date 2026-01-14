"""
Centralized logging configuration for the application.
Singleton pattern ensures consistent logging across all modules.
"""
import logging
import sys
from typing import Optional
from pathlib import Path


class AppLogger:
    """Singleton logger for the application"""
    
    _instance: Optional[logging.Logger] = None
    _initialized: bool = False
    
    @classmethod
    def get_logger(cls, name: str = "planetal") -> logging.Logger:
        """
        Get or create the application logger.
        
        Args:
            name: Logger name (default: "planetal")
            
        Returns:
            Configured logger instance
        """
        if cls._instance is None:
            cls._instance = cls._setup_logger(name)
            cls._initialized = True
        
        return cls._instance
    
    @classmethod
    def _setup_logger(cls, name: str) -> logging.Logger:
        """
        Configure the logger with formatters and handlers.
        
        Args:
            name: Logger name
            
        Returns:
            Configured logger
        """
        # Get log level from environment or default to INFO
        import os
        log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
        log_level = getattr(logging, log_level_str, logging.INFO)
        
        logger = logging.getLogger(name)
        logger.setLevel(log_level)
        
        # Avoid duplicate handlers
        if logger.handlers:
            return logger
        
        # Console handler with colored output
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        
        # Detailed formatter
        formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)
        
        logger.addHandler(console_handler)
        
        # File handler for persistent logs (optional)
        try:
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)
            
            file_handler = logging.FileHandler(
                log_dir / "app.log",
                encoding='utf-8'
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            
            # Error log file
            error_handler = logging.FileHandler(
                log_dir / "error.log",
                encoding='utf-8'
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(formatter)
            logger.addHandler(error_handler)
            
        except Exception as e:
            logger.warning(f"Could not create file handlers: {e}")
        
        return logger


# Convenience function for easy imports
def get_logger(module_name: Optional[str] = None) -> logging.Logger:
    """
    Get the application logger.
    
    Usage:
        from app.core.logger import get_logger
        logger = get_logger(__name__)
        logger.info("Message")
    
    Args:
        module_name: Optional module name for context (e.g., __name__)
        
    Returns:
        Configured logger instance
    """
    base_logger = AppLogger.get_logger()
    
    # If module name provided, create child logger for better context
    if module_name:
        return base_logger.getChild(module_name.split('.')[-1])
    
    return base_logger


# Performance logger for database operations
def get_perf_logger() -> logging.Logger:
    """Get logger specifically for performance metrics"""
    return AppLogger.get_logger().getChild("performance")
