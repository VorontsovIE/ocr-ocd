"""Logging configuration module."""

import sys
from pathlib import Path
from typing import Optional
from loguru import logger
from datetime import datetime


def setup_logger(
    logs_dir: Path = Path("logs"),
    log_level: str = "INFO",
    enable_console: bool = True,
    enable_file: bool = True,
    enable_json: bool = False,
    max_file_size: str = "100 MB",
    retention_days: str = "30 days",
    max_files: int = 10
) -> None:
    """Setup application logging with loguru.
    
    Args:
        logs_dir: Directory to store log files
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        enable_console: Enable console logging
        enable_file: Enable file logging
        enable_json: Enable JSON format logging for production
        max_file_size: Maximum size of log file before rotation
        retention_days: How long to keep old log files
        max_files: Maximum number of log files to keep
    """
    # Remove default logger
    logger.remove()
    
    # Console logging with beautiful formatting for development
    if enable_console:
        console_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        )
        
        if enable_json:
            # Production console - JSON format
            console_format = "{time} | {level} | {name}:{function}:{line} | {message}"
            colorize = False
        else:
            # Development console - colorized
            colorize = True
        
        logger.add(
            sys.stdout,
            level=log_level,
            format=console_format,
            colorize=colorize,
            backtrace=True,
            diagnose=True
        )
    
    # File logging
    if enable_file:
        logs_dir.mkdir(exist_ok=True, parents=True)
        timestamp = datetime.now().strftime("%Y%m%d")
        
        if enable_json:
            # Production JSON logging
            log_file = logs_dir / f"ocr_ocd_{timestamp}.json"
            logger.add(
                log_file,
                level=log_level,
                format="{time} | {level} | {name}:{function}:{line} | {message}",
                rotation=max_file_size,
                retention=retention_days,
                compression="zip",
                serialize=True,  # JSON format
                backtrace=True,
                diagnose=True
            )
        else:
            # Development text logging
            log_file = logs_dir / f"ocr_ocd_{timestamp}.log"
            logger.add(
                log_file,
                level=log_level,
                format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
                rotation=max_file_size,
                retention=retention_days,
                compression="zip",
                backtrace=True,
                diagnose=True
            )
        
        # Error file - separate file for errors and above
        error_file = logs_dir / f"ocr_ocd_errors_{timestamp}.log"
        logger.add(
            error_file,
            level="ERROR",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message} | {exception}",
            rotation=max_file_size,
            retention=retention_days,
            compression="zip",
            backtrace=True,
            diagnose=True
        )
    
    logger.info(
        "Logger initialized",
        level=log_level,
        console=enable_console,
        file=enable_file,
        json_format=enable_json,
        logs_dir=str(logs_dir)
    )


def get_logger(name: str):
    """Get logger instance for a module.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Logger instance
    """
    return logger.bind(name=name)


def setup_production_logger(logs_dir: Path = Path("logs")) -> None:
    """Setup logger for production environment with JSON format.
    
    Args:
        logs_dir: Directory to store log files
    """
    setup_logger(
        logs_dir=logs_dir,
        log_level="INFO",
        enable_console=True,
        enable_file=True,
        enable_json=True,
        max_file_size="50 MB",
        retention_days="60 days"
    )


def setup_development_logger(logs_dir: Path = Path("logs")) -> None:
    """Setup logger for development environment with colorized output.
    
    Args:
        logs_dir: Directory to store log files
    """
    setup_logger(
        logs_dir=logs_dir,
        log_level="DEBUG",
        enable_console=True,
        enable_file=True,
        enable_json=False,
        max_file_size="20 MB",
        retention_days="7 days"
    )


def log_function_call(func_name: str, **kwargs) -> None:
    """Log function call with parameters.
    
    Args:
        func_name: Name of the function being called
        **kwargs: Function parameters to log
    """
    logger.debug(f"Calling {func_name}", **kwargs)


def log_function_result(func_name: str, result=None, duration: Optional[float] = None) -> None:
    """Log function result and execution time.
    
    Args:
        func_name: Name of the function
        result: Function result (will be summarized if large)
        duration: Execution time in seconds
    """
    log_data = {"function": func_name}
    
    if duration is not None:
        log_data["duration_seconds"] = round(duration, 4)
    
    if result is not None:
        if isinstance(result, (str, int, float, bool)):
            log_data["result"] = result
        elif isinstance(result, (list, tuple)):
            log_data["result_type"] = type(result).__name__
            log_data["result_length"] = len(result)
        elif isinstance(result, dict):
            log_data["result_type"] = "dict"
            log_data["result_keys"] = len(result)
        else:
            log_data["result_type"] = type(result).__name__
    
    logger.debug(f"Function {func_name} completed", **log_data)


def log_api_request(url: str, method: str = "GET", **kwargs) -> None:
    """Log API request details.
    
    Args:
        url: API endpoint URL
        method: HTTP method
        **kwargs: Additional request parameters
    """
    logger.info(f"API request: {method} {url}", method=method, url=url, **kwargs)


def log_api_response(url: str, status_code: int, duration: float, **kwargs) -> None:
    """Log API response details.
    
    Args:
        url: API endpoint URL
        status_code: HTTP status code
        duration: Request duration in seconds
        **kwargs: Additional response data
    """
    logger.info(
        f"API response: {status_code} from {url}",
        status_code=status_code,
        url=url,
        duration_seconds=round(duration, 4),
        **kwargs
    )


def log_processing_progress(current: int, total: int, item_type: str = "items") -> None:
    """Log processing progress.
    
    Args:
        current: Current number of processed items
        total: Total number of items to process
        item_type: Type of items being processed
    """
    percentage = (current / total * 100) if total > 0 else 0
    logger.info(
        f"Processing progress: {current}/{total} {item_type} ({percentage:.1f}%)",
        current=current,
        total=total,
        percentage=round(percentage, 1),
        item_type=item_type
    )


def log_error_with_context(error: Exception, context: dict = None) -> None:
    """Log error with additional context.
    
    Args:
        error: Exception that occurred
        context: Additional context information
    """
    error_data = {
        "error_type": type(error).__name__,
        "error_message": str(error)
    }
    
    if context:
        error_data.update(context)
    
    logger.error(f"Error occurred: {error}", **error_data) 