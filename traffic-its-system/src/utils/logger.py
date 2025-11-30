"""
Logging Utility
Centralized logging for the ITS system
"""

import logging
import sys
from pathlib import Path
from datetime import datetime


class SystemLogger:
    """Configure and manage system logging"""
    
    def __init__(self, name: str = "ITS", log_file: str = None, level: str = "INFO"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper()))
        
        # Remove existing handlers
        self.logger.handlers.clear()
        
        # Console handler with UTF-8 encoding
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        
        # Force UTF-8 encoding on Windows
        if hasattr(sys.stdout, 'reconfigure'):
            try:
                sys.stdout.reconfigure(encoding='utf-8')
            except:
                pass
        
        console_format = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_format)
        self.logger.addHandler(console_handler)
        
        # File handler (if specified)
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            file_format = logging.Formatter(
                '%(asctime)s | %(name)s | %(levelname)-8s | %(message)s'
            )
            file_handler.setFormatter(file_format)
            self.logger.addHandler(file_handler)
    
    def _safe_message(self, message: str) -> str:
        """Remove emojis for systems that don't support them"""
        try:
            # Try to encode with system encoding
            message.encode(sys.stdout.encoding or 'utf-8')
            return message
        except (UnicodeEncodeError, AttributeError):
            # Remove common emojis if encoding fails
            emoji_map = {
                '✅': '[OK]',
                '❌': '[ERROR]',
                '⚠️': '[WARNING]',
                '📂': '[DIR]',
                '📊': '[STATS]',
                '🧠': '[AI]',
                '🗺️': '[MAP]',
                '🔮': '[PREDICT]',
                '📥': '[INPUT]',
                '🚀': '[START]',
                '✓': '[OK]',
                '•': '*'
            }
            for emoji, replacement in emoji_map.items():
                message = message.replace(emoji, replacement)
            return message
    
    def info(self, message: str):
        """Log info message"""
        self.logger.info(self._safe_message(message))
    
    def debug(self, message: str):
        """Log debug message"""
        self.logger.debug(self._safe_message(message))
    
    def warning(self, message: str):
        """Log warning message"""
        self.logger.warning(self._safe_message(message))
    
    def error(self, message: str):
        """Log error message"""
        self.logger.error(self._safe_message(message))
    
    def critical(self, message: str):
        """Log critical message"""
        self.logger.critical(self._safe_message(message))


# Global logger instance
_logger = None

def get_logger(name: str = "ITS", log_file: str = None, level: str = "INFO") -> SystemLogger:
    """Get global logger instance"""
    global _logger
    if _logger is None:
        _logger = SystemLogger(name, log_file, level)
    return _logger
