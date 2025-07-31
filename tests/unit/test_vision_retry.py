"""Tests for VisionClient retry logic."""

import time
from unittest.mock import Mock, patch, MagicMock
import pytest
from openai import APIError, RateLimitError, APIConnectionError, APITimeoutError
from src.core.vision_client import VisionClient, VisionAPIError, ImageValidationError
from src.utils.config import APIConfig


class TestVisionClientRetry:
    """Tests for VisionClient retry functionality."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.config = APIConfig(
            api_key="test_api_key",
            model_name="gpt-4-vision-preview",
            max_tokens=4096,
            temperature=0.1,
            timeout=60,
            max_retries=3,
            retry_delay=1  # Short delay for testing
        )
    
    def create_test_image(self) -> bytes:
        """Create test image data."""
        from PIL import Image
        import io
        
        image = Image.new('RGB', (100, 100), color='white')
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        return buffer.getvalue()
    
    @patch('src.core.vision_client.OpenAI')
    def test_retry_on_rate_limit_error(self, mock_openai):
        """Test retry behavior on rate limit error."""
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        # Setup mock to fail twice with rate limit, then succeed
        rate_limit_error = RateLimitError(
            message="Rate limit exceeded",
            response=Mock(status_code=429),
            body={"error": {"message": "Rate limit exceeded"}}
        )
        
        mock_choice = Mock()
        mock_choice.message.content = "Success after retry"
        
        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage = None
        mock_response.model = "gpt-4-vision-preview"
        
        # Fail twice, then succeed
        mock_client.chat.completions.create.side_effect = [
            rate_limit_error,
            rate_limit_error,
            mock_response
        ]
        
        client = VisionClient(self.config)
        image_data = self.create_test_image()
        
        # Should succeed after retries
        result = client.extract_tasks_from_page(image_data, 1)
        
        assert result["content"] == "Success after retry"
        assert mock_client.chat.completions.create.call_count == 3
    
    @patch('src.core.vision_client.OpenAI')
    def test_retry_on_connection_error(self, mock_openai):
        """Test retry behavior on connection error."""
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        # Setup mock to fail with connection error, then succeed
        connection_error = APIConnectionError(
            message="Connection failed",
            request=Mock()
        )
        
        mock_choice = Mock()
        mock_choice.message.content = "Connected successfully"
        
        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage = None
        mock_response.model = "gpt-4-vision-preview"
        
        mock_client.chat.completions.create.side_effect = [
            connection_error,
            mock_response
        ]
        
        client = VisionClient(self.config)
        image_data = self.create_test_image()
        
        result = client.extract_tasks_from_page(image_data, 1)
        
        assert result["content"] == "Connected successfully"
        assert mock_client.chat.completions.create.call_count == 2
    
    @patch('src.core.vision_client.OpenAI')
    def test_retry_on_timeout_error(self, mock_openai):
        """Test retry behavior on timeout error."""
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        timeout_error = APITimeoutError(
            message="Request timeout",
            request=Mock()
        )
        
        mock_choice = Mock()
        mock_choice.message.content = "Request completed"
        
        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage = None
        mock_response.model = "gpt-4-vision-preview"
        
        mock_client.chat.completions.create.side_effect = [
            timeout_error,
            mock_response
        ]
        
        client = VisionClient(self.config)
        image_data = self.create_test_image()
        
        result = client.extract_tasks_from_page(image_data, 1)
        
        assert result["content"] == "Request completed"
        assert mock_client.chat.completions.create.call_count == 2
    
    @patch('src.core.vision_client.OpenAI')
    def test_retry_on_api_error_500(self, mock_openai):
        """Test retry behavior on API 500 error."""
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        api_error = APIError(
            message="Internal server error",
            request=Mock(),
            body={"error": {"message": "Internal server error"}}
        )
        api_error.status_code = 500
        
        mock_choice = Mock()
        mock_choice.message.content = "Server recovered"
        
        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage = None
        mock_response.model = "gpt-4-vision-preview"
        
        mock_client.chat.completions.create.side_effect = [
            api_error,
            mock_response
        ]
        
        client = VisionClient(self.config)
        image_data = self.create_test_image()
        
        result = client.extract_tasks_from_page(image_data, 1)
        
        assert result["content"] == "Server recovered"
        assert mock_client.chat.completions.create.call_count == 2
    
    @patch('src.core.vision_client.OpenAI')
    def test_retry_exhausted_all_attempts(self, mock_openai):
        """Test behavior when all retry attempts are exhausted."""
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        # Setup to always fail with rate limit
        rate_limit_error = RateLimitError(
            message="Rate limit exceeded",
            response=Mock(status_code=429),
            body={"error": {"message": "Rate limit exceeded"}}
        )
        
        mock_client.chat.completions.create.side_effect = rate_limit_error
        
        client = VisionClient(self.config)
        image_data = self.create_test_image()
        
        # Should fail after max_retries attempts
        with pytest.raises(VisionAPIError, match="API call failed after 3 retries"):
            client.extract_tasks_from_page(image_data, 1)
        
        # Should have tried max_retries times
        assert mock_client.chat.completions.create.call_count == self.config.max_retries
    
    @patch('src.core.vision_client.OpenAI')
    def test_no_retry_on_image_validation_error(self, mock_openai):
        """Test that image validation errors are not retried."""
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        client = VisionClient(self.config)
        
        # Invalid image data should not be retried
        invalid_image_data = b"not_an_image"
        
        with pytest.raises(ImageValidationError):
            client.extract_tasks_from_page(invalid_image_data, 1)
        
        # API should not be called at all
        assert mock_client.chat.completions.create.call_count == 0
    
    @patch('src.core.vision_client.OpenAI')
    def test_no_retry_on_authentication_error(self, mock_openai):
        """Test that authentication errors are not retried."""
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        # Setup authentication error (typically status 401)
        auth_error = APIError(
            message="Invalid API key",
            request=Mock(),
            body={"error": {"message": "Invalid API key"}}
        )
        auth_error.status_code = 401
        
        mock_client.chat.completions.create.side_effect = auth_error
        
        client = VisionClient(self.config)
        image_data = self.create_test_image()
        
        # Should fail without retries for auth errors
        with pytest.raises(VisionAPIError):
            client.extract_tasks_from_page(image_data, 1)
        
        # Should only try once for auth errors
        assert mock_client.chat.completions.create.call_count == 1
    
    @patch('src.core.vision_client.OpenAI')
    def test_no_retry_on_unexpected_error(self, mock_openai):
        """Test that unexpected errors are not retried."""
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        # Setup unexpected error (like ValueError)
        unexpected_error = ValueError("Unexpected error")
        mock_client.chat.completions.create.side_effect = unexpected_error
        
        client = VisionClient(self.config)
        image_data = self.create_test_image()
        
        # Should fail immediately without retries
        with pytest.raises(VisionAPIError, match="Unexpected API error"):
            client.extract_tasks_from_page(image_data, 1)
        
        # Should only try once for unexpected errors
        assert mock_client.chat.completions.create.call_count == 1
    
    @patch('src.core.vision_client.OpenAI')
    @patch('time.sleep')  # Mock sleep to speed up test
    def test_exponential_backoff_timing(self, mock_sleep, mock_openai):
        """Test exponential backoff timing."""
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        # Setup to fail twice, then succeed
        rate_limit_error = RateLimitError(
            message="Rate limit exceeded",
            response=Mock(status_code=429),
            body={"error": {"message": "Rate limit exceeded"}}
        )
        
        mock_choice = Mock()
        mock_choice.message.content = "Success"
        
        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage = None
        mock_response.model = "gpt-4-vision-preview"
        
        mock_client.chat.completions.create.side_effect = [
            rate_limit_error,
            rate_limit_error,
            mock_response
        ]
        
        client = VisionClient(self.config)
        image_data = self.create_test_image()
        
        result = client.extract_tasks_from_page(image_data, 1)
        
        assert result["content"] == "Success"
        
        # Check that sleep was called with exponential backoff
        assert mock_sleep.call_count == 2  # Two retries
        sleep_times = [call[0][0] for call in mock_sleep.call_args_list]
        
        # First sleep should be around base delay (1 second)
        assert sleep_times[0] >= 1.0
        # Second sleep should be longer (exponential backoff)
        assert sleep_times[1] > sleep_times[0]
    
    @patch('src.core.vision_client.OpenAI')
    def test_retry_with_different_error_types(self, mock_openai):
        """Test retry with mixed error types."""
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        # Setup different types of retryable errors
        rate_limit_error = RateLimitError(
            message="Rate limit exceeded",
            response=Mock(status_code=429),
            body={"error": {"message": "Rate limit exceeded"}}
        )
        
        connection_error = APIConnectionError(
            message="Connection failed",
            request=Mock()
        )
        
        mock_choice = Mock()
        mock_choice.message.content = "Final success"
        
        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage = None
        mock_response.model = "gpt-4-vision-preview"
        
        # Mix of different error types, then success
        mock_client.chat.completions.create.side_effect = [
            rate_limit_error,
            connection_error,
            mock_response
        ]
        
        client = VisionClient(self.config)
        image_data = self.create_test_image()
        
        result = client.extract_tasks_from_page(image_data, 1)
        
        assert result["content"] == "Final success"
        assert mock_client.chat.completions.create.call_count == 3
    
    @patch('src.core.vision_client.OpenAI')
    def test_get_retry_statistics(self, mock_openai):
        """Test getting retry configuration statistics."""
        client = VisionClient(self.config)
        
        stats = client.get_retry_statistics()
        
        assert stats["max_retries"] == 3
        assert stats["base_retry_delay"] == 1
        assert stats["max_retry_delay"] == 60
        assert stats["retry_strategy"] == "exponential_backoff"
        assert "RateLimitError (HTTP 429)" in stats["retryable_errors"]
        assert "APIConnectionError" in stats["retryable_errors"]
        assert "APITimeoutError" in stats["retryable_errors"]
        assert "APIError (HTTP 500, 502, 503)" in stats["retryable_errors"]
        assert "ImageValidationError" in stats["non_retryable_errors"]
        assert "Authentication errors" in stats["non_retryable_errors"]
    
    @patch('src.core.vision_client.OpenAI')
    def test_custom_retry_config(self, mock_openai):
        """Test VisionClient with custom retry configuration."""
        custom_config = APIConfig(
            api_key="test_api_key",
            model_name="gpt-4-vision-preview",
            max_tokens=4096,
            temperature=0.1,
            timeout=60,
            max_retries=5,  # Custom max retries
            retry_delay=2   # Custom delay
        )
        
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        # Setup to always fail to test max retries
        rate_limit_error = RateLimitError(
            message="Rate limit exceeded",
            response=Mock(status_code=429),
            body={"error": {"message": "Rate limit exceeded"}}
        )
        
        mock_client.chat.completions.create.side_effect = rate_limit_error
        
        client = VisionClient(custom_config)
        image_data = self.create_test_image()
        
        with pytest.raises(VisionAPIError, match="API call failed after 5 retries"):
            client.extract_tasks_from_page(image_data, 1)
        
        # Should respect custom max_retries
        assert mock_client.chat.completions.create.call_count == 5
        
        # Check custom config in statistics
        stats = client.get_retry_statistics()
        assert stats["max_retries"] == 5
        assert stats["base_retry_delay"] == 2


class TestRetryLogging:
    """Tests for retry logging functionality."""
    
    @patch('src.core.vision_client.OpenAI')
    @patch('src.core.vision_client.logger')
    def test_retry_logging_on_rate_limit(self, mock_logger, mock_openai):
        """Test that retry attempts are properly logged."""
        config = APIConfig(
            api_key="test_api_key",
            model_name="gpt-4-vision-preview",
            max_retries=2,
            retry_delay=1
        )
        
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        rate_limit_error = RateLimitError(
            message="Rate limit exceeded",
            response=Mock(status_code=429),
            body={"error": {"message": "Rate limit exceeded"}}
        )
        rate_limit_error.retry_after = 30  # Mock retry_after header
        
        mock_choice = Mock()
        mock_choice.message.content = "Success"
        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage = None
        mock_response.model = "gpt-4-vision-preview"
        
        mock_client.chat.completions.create.side_effect = [
            rate_limit_error,
            mock_response
        ]
        
        client = VisionClient(config)
        image_data = client.create_test_image() if hasattr(client, 'create_test_image') else b"test"
        
        # Mock image creation for testing
        from PIL import Image
        import io
        test_image = Image.new('RGB', (100, 100), color='white')
        buffer = io.BytesIO()
        test_image.save(buffer, format='PNG')
        image_data = buffer.getvalue()
        
        result = client.extract_tasks_from_page(image_data, 1)
        
        assert result["content"] == "Success"
        
        # Check that warning was logged for rate limit
        warning_calls = [call for call in mock_logger.warning.call_args_list 
                        if "Rate limit hit" in str(call)]
        assert len(warning_calls) > 0 