"""Tests for logging module."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from src.utils.logger import (
    setup_logger,
    setup_production_logger,
    setup_development_logger,
    get_logger,
    log_function_call,
    log_function_result,
    log_api_request,
    log_api_response,
    log_processing_progress,
    log_error_with_context
)


class TestLoggerSetup:
    """Tests for logger setup functions."""
    
    def test_setup_logger_default(self):
        """Test logger setup with default parameters."""
        with tempfile.TemporaryDirectory() as temp_dir:
            logs_dir = Path(temp_dir) / "logs"
            
            # Should not raise any exceptions
            setup_logger(logs_dir=logs_dir)
            
            # Check that logs directory was created
            assert logs_dir.exists()
    
    @patch('src.utils.logger.logger')
    def test_setup_logger_console_only(self, mock_logger):
        """Test logger setup with console only."""
        mock_logger.remove = MagicMock()
        mock_logger.add = MagicMock()
        mock_logger.info = MagicMock()
        
        setup_logger(enable_console=True, enable_file=False)
        
        # Should call logger.add once for console
        assert mock_logger.add.call_count == 1
        mock_logger.info.assert_called_once()
    
    @patch('src.utils.logger.logger')
    def test_setup_logger_file_only(self, mock_logger):
        """Test logger setup with file only."""
        mock_logger.remove = MagicMock()
        mock_logger.add = MagicMock()
        mock_logger.info = MagicMock()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            logs_dir = Path(temp_dir) / "logs"
            setup_logger(logs_dir=logs_dir, enable_console=False, enable_file=True)
            
            # Should call logger.add twice (regular file + error file)
            assert mock_logger.add.call_count == 2
            mock_logger.info.assert_called_once()
    
    @patch('src.utils.logger.logger')
    def test_setup_logger_json_format(self, mock_logger):
        """Test logger setup with JSON format."""
        mock_logger.remove = MagicMock()
        mock_logger.add = MagicMock()
        mock_logger.info = MagicMock()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            logs_dir = Path(temp_dir) / "logs"
            setup_logger(
                logs_dir=logs_dir,
                enable_console=True,
                enable_file=True,
                enable_json=True
            )
            
            # Should call logger.add 3 times (console + json file + error file)
            assert mock_logger.add.call_count == 3
            mock_logger.info.assert_called_once()
    
    @patch('src.utils.logger.setup_logger')
    def test_setup_production_logger(self, mock_setup):
        """Test production logger setup."""
        logs_dir = Path("test_logs")
        setup_production_logger(logs_dir)
        
        mock_setup.assert_called_once_with(
            logs_dir=logs_dir,
            log_level="INFO",
            enable_console=True,
            enable_file=True,
            enable_json=True,
            max_file_size="50 MB",
            retention_days="60 days"
        )
    
    @patch('src.utils.logger.setup_logger')
    def test_setup_development_logger(self, mock_setup):
        """Test development logger setup."""
        logs_dir = Path("test_logs")
        setup_development_logger(logs_dir)
        
        mock_setup.assert_called_once_with(
            logs_dir=logs_dir,
            log_level="DEBUG",
            enable_console=True,
            enable_file=True,
            enable_json=False,
            max_file_size="20 MB",
            retention_days="7 days"
        )


class TestLoggerFunctions:
    """Tests for logger utility functions."""
    
    @patch('src.utils.logger.logger')
    def test_get_logger(self, mock_logger):
        """Test getting logger instance."""
        mock_logger.bind = MagicMock(return_value="bound_logger")
        
        result = get_logger("test_module")
        
        mock_logger.bind.assert_called_once_with(name="test_module")
        assert result == "bound_logger"
    
    @patch('src.utils.logger.logger')
    def test_log_function_call(self, mock_logger):
        """Test logging function calls."""
        mock_logger.debug = MagicMock()
        
        log_function_call("test_function", param1="value1", param2=42)
        
        mock_logger.debug.assert_called_once_with(
            "Calling test_function",
            param1="value1",
            param2=42
        )
    
    @patch('src.utils.logger.logger')
    def test_log_function_result_simple(self, mock_logger):
        """Test logging function result with simple data."""
        mock_logger.debug = MagicMock()
        
        log_function_result("test_function", result="success", duration=1.234)
        
        mock_logger.debug.assert_called_once_with(
            "Function test_function completed",
            function="test_function",
            result="success",
            duration_seconds=1.234
        )
    
    @patch('src.utils.logger.logger')
    def test_log_function_result_complex(self, mock_logger):
        """Test logging function result with complex data."""
        mock_logger.debug = MagicMock()
        
        log_function_result("test_function", result=[1, 2, 3, 4, 5])
        
        mock_logger.debug.assert_called_once_with(
            "Function test_function completed",
            function="test_function",
            result_type="list",
            result_length=5
        )
    
    @patch('src.utils.logger.logger')
    def test_log_api_request(self, mock_logger):
        """Test logging API requests."""
        mock_logger.info = MagicMock()
        
        log_api_request("https://api.example.com/test", "POST", headers={"Auth": "token"})
        
        mock_logger.info.assert_called_once_with(
            "API request: POST https://api.example.com/test",
            method="POST",
            url="https://api.example.com/test",
            headers={"Auth": "token"}
        )
    
    @patch('src.utils.logger.logger')
    def test_log_api_response(self, mock_logger):
        """Test logging API responses."""
        mock_logger.info = MagicMock()
        
        log_api_response("https://api.example.com/test", 200, 2.5, data_size=1024)
        
        mock_logger.info.assert_called_once_with(
            "API response: 200 from https://api.example.com/test",
            status_code=200,
            url="https://api.example.com/test",
            duration_seconds=2.5,
            data_size=1024
        )
    
    @patch('src.utils.logger.logger')
    def test_log_processing_progress(self, mock_logger):
        """Test logging processing progress."""
        mock_logger.info = MagicMock()
        
        log_processing_progress(50, 100, "pages")
        
        mock_logger.info.assert_called_once_with(
            "Processing progress: 50/100 pages (50.0%)",
            current=50,
            total=100,
            percentage=50.0,
            item_type="pages"
        )
    
    @patch('src.utils.logger.logger')
    def test_log_processing_progress_zero_total(self, mock_logger):
        """Test logging processing progress with zero total."""
        mock_logger.info = MagicMock()
        
        log_processing_progress(0, 0, "items")
        
        mock_logger.info.assert_called_once_with(
            "Processing progress: 0/0 items (0.0%)",
            current=0,
            total=0,
            percentage=0.0,
            item_type="items"
        )
    
    @patch('src.utils.logger.logger')
    def test_log_error_with_context(self, mock_logger):
        """Test logging errors with context."""
        mock_logger.error = MagicMock()
        
        error = ValueError("Test error")
        context = {"page": 5, "operation": "processing"}
        
        log_error_with_context(error, context)
        
        mock_logger.error.assert_called_once_with(
            "Error occurred: Test error",
            error_type="ValueError",
            error_message="Test error",
            page=5,
            operation="processing"
        )
    
    @patch('src.utils.logger.logger')
    def test_log_error_without_context(self, mock_logger):
        """Test logging errors without context."""
        mock_logger.error = MagicMock()
        
        error = RuntimeError("Runtime error")
        
        log_error_with_context(error)
        
        mock_logger.error.assert_called_once_with(
            "Error occurred: Runtime error",
            error_type="RuntimeError",
            error_message="Runtime error"
        ) 