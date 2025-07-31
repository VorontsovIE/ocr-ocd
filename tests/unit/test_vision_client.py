"""Tests for VisionClient module."""

import json
import io
from unittest.mock import Mock, patch, MagicMock
import pytest
from PIL import Image
from src.core.vision_client import VisionClient, VisionAPIError, ImageValidationError
from src.utils.config import APIConfig


class TestVisionClient:
    """Tests for VisionClient class."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.config = APIConfig(
            api_key="test_api_key",
            model_name="gpt-4-vision-preview",
            max_tokens=4096,
            temperature=0.1,
            timeout=60,
            max_retries=3,
            retry_delay=5
        )
    
    @patch('src.core.vision_client.OpenAI')
    def test_vision_client_init(self, mock_openai):
        """Test VisionClient initialization."""
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        client = VisionClient(self.config)
        
        assert client.config == self.config
        assert client.client == mock_client
        assert client.max_image_size_mb == 20
        assert client.max_image_dimension == 2048
        assert "PNG" in client.supported_formats
        
        mock_openai.assert_called_once_with(api_key="test_api_key")
    
    def create_test_image(self, width: int = 100, height: int = 100, format: str = "PNG") -> bytes:
        """Create test image data.
        
        Args:
            width: Image width
            height: Image height
            format: Image format
            
        Returns:
            Image data as bytes
        """
        image = Image.new('RGB', (width, height), color='white')
        buffer = io.BytesIO()
        image.save(buffer, format=format)
        return buffer.getvalue()
    
    @patch('src.core.vision_client.OpenAI')
    def test_validate_image_success(self, mock_openai):
        """Test successful image validation."""
        client = VisionClient(self.config)
        image_data = self.create_test_image(800, 600)
        
        result = client.validate_image(image_data)
        
        assert result["format"] == "PNG"
        assert result["dimensions"] == (800, 600)
        assert result["max_dimension"] == 800
        assert result["is_oversized"] is False
        assert result["size_mb"] < 1.0
    
    @patch('src.core.vision_client.OpenAI')
    def test_validate_image_too_large_file(self, mock_openai):
        """Test image validation with file too large."""
        client = VisionClient(self.config)
        
        # Create mock image data that's too large
        large_image_data = b"x" * (25 * 1024 * 1024)  # 25MB
        
        with patch('src.core.vision_client.Image') as mock_image:
            mock_img = Mock()
            mock_img.format = "PNG"
            mock_img.size = (1000, 1000)
            mock_image.open.return_value = mock_img
            
            with pytest.raises(ImageValidationError, match="exceeds limit"):
                client.validate_image(large_image_data)
    
    @patch('src.core.vision_client.OpenAI')
    def test_validate_image_unsupported_format(self, mock_openai):
        """Test image validation with unsupported format."""
        client = VisionClient(self.config)
        image_data = self.create_test_image()
        
        with patch('src.core.vision_client.Image') as mock_image:
            mock_img = Mock()
            mock_img.format = "TIFF"  # Unsupported format
            mock_img.size = (100, 100)
            mock_image.open.return_value = mock_img
            
            with pytest.raises(ImageValidationError, match="Unsupported image format"):
                client.validate_image(image_data)
    
    @patch('src.core.vision_client.OpenAI')
    def test_validate_image_oversized_dimensions(self, mock_openai):
        """Test image validation with oversized dimensions."""
        client = VisionClient(self.config)
        image_data = self.create_test_image(3000, 2000)  # Large dimensions
        
        result = client.validate_image(image_data)
        
        assert result["is_oversized"] is True
        assert result["max_dimension"] == 3000
    
    @patch('src.core.vision_client.OpenAI')
    def test_encode_image_success(self, mock_openai):
        """Test successful image encoding."""
        client = VisionClient(self.config)
        image_data = b"test_image_data"
        
        result = client.encode_image(image_data)
        
        # Should be base64 encoded
        import base64
        expected = base64.b64encode(image_data).decode('utf-8')
        assert result == expected
    
    @patch('src.core.vision_client.OpenAI')
    def test_encode_image_error(self, mock_openai):
        """Test image encoding with error."""
        client = VisionClient(self.config)
        
        with patch('base64.b64encode', side_effect=Exception("Encoding failed")):
            with pytest.raises(VisionAPIError, match="Failed to encode image"):
                client.encode_image(b"test_data")
    
    @patch('src.core.vision_client.OpenAI')
    def test_build_extraction_prompt(self, mock_openai):
        """Test prompt building."""
        client = VisionClient(self.config)
        
        prompt = client.build_extraction_prompt(5)
        
        assert "страницу 5" in prompt
        assert "JSON" in prompt
        assert "task_number" in prompt
        assert "task_text" in prompt
        assert "has_image" in prompt
        assert "confidence" in prompt
    
    @patch('src.core.vision_client.OpenAI')
    def test_extract_tasks_from_page_success(self, mock_openai):
        """Test successful task extraction."""
        # Setup mock client
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        # Setup mock response
        mock_usage = Mock()
        mock_usage.total_tokens = 150
        mock_usage.model_dump.return_value = {"total_tokens": 150}
        
        mock_choice = Mock()
        mock_choice.message.content = '{"page_number": 1, "tasks": []}'
        
        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage
        mock_response.model = "gpt-4-vision-preview"
        
        mock_client.chat.completions.create.return_value = mock_response
        
        client = VisionClient(self.config)
        image_data = self.create_test_image()
        
        result = client.extract_tasks_from_page(image_data, 1)
        
        assert result["content"] == '{"page_number": 1, "tasks": []}'
        assert result["model"] == "gpt-4-vision-preview"
        assert result["usage"]["total_tokens"] == 150
        assert "processing_time" in result
        assert "image_info" in result
        
        # Verify API call was made
        mock_client.chat.completions.create.assert_called_once()
        call_args = mock_client.chat.completions.create.call_args
        
        assert call_args[1]["model"] == "gpt-4-vision-preview"
        assert call_args[1]["max_tokens"] == 4096
        assert call_args[1]["temperature"] == 0.1
        assert len(call_args[1]["messages"]) == 1
    
    @patch('src.core.vision_client.OpenAI')
    def test_extract_tasks_with_custom_prompt(self, mock_openai):
        """Test task extraction with custom prompt."""
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        mock_choice = Mock()
        mock_choice.message.content = "Custom response"
        
        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage = None
        mock_response.model = "gpt-4-vision-preview"
        
        mock_client.chat.completions.create.return_value = mock_response
        
        client = VisionClient(self.config)
        image_data = self.create_test_image()
        custom_prompt = "Custom test prompt"
        
        result = client.extract_tasks_from_page(
            image_data, 1, custom_prompt=custom_prompt
        )
        
        assert result["content"] == "Custom response"
        
        # Check that custom prompt was used
        call_args = mock_client.chat.completions.create.call_args
        message_content = call_args[1]["messages"][0]["content"]
        
        # Find the text content in the message
        text_content = None
        for item in message_content:
            if item["type"] == "text":
                text_content = item["text"]
                break
        
        assert text_content == custom_prompt
    
    @patch('src.core.vision_client.OpenAI')
    def test_extract_tasks_api_error(self, mock_openai):
        """Test task extraction with API error."""
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        # Mock API error
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        
        client = VisionClient(self.config)
        image_data = self.create_test_image()
        
        with pytest.raises(VisionAPIError, match="Vision API call failed"):
            client.extract_tasks_from_page(image_data, 1)
    
    @patch('src.core.vision_client.OpenAI')
    def test_extract_tasks_image_validation_error(self, mock_openai):
        """Test task extraction with image validation error."""
        client = VisionClient(self.config)
        
        # Create invalid image data
        invalid_image_data = b"not_an_image"
        
        with pytest.raises(ImageValidationError):
            client.extract_tasks_from_page(invalid_image_data, 1)
    
    @patch('src.core.vision_client.OpenAI')
    def test_test_api_connection_success(self, mock_openai):
        """Test successful API connection test."""
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        # Setup mock response
        mock_choice = Mock()
        mock_choice.message.content = "White"
        
        mock_usage = Mock()
        mock_usage.total_tokens = 50
        mock_usage.model_dump.return_value = {"total_tokens": 50}
        
        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage
        mock_response.model = "gpt-4-vision-preview"
        
        mock_client.chat.completions.create.return_value = mock_response
        
        client = VisionClient(self.config)
        
        result = client.test_api_connection()
        
        assert result["status"] == "success"
        assert result["model"] == "gpt-4-vision-preview"
        assert result["tokens_used"] == 50
        assert "response_time" in result
    
    @patch('src.core.vision_client.OpenAI')
    def test_test_api_connection_failure(self, mock_openai):
        """Test API connection test failure."""
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        mock_client.chat.completions.create.side_effect = Exception("Connection failed")
        
        client = VisionClient(self.config)
        
        with pytest.raises(VisionAPIError, match="API connection test failed"):
            client.test_api_connection()
    
    @patch('src.core.vision_client.OpenAI')
    def test_get_model_info(self, mock_openai):
        """Test getting model information."""
        client = VisionClient(self.config)
        
        info = client.get_model_info()
        
        assert info["model_name"] == "gpt-4-vision-preview"
        assert info["max_tokens"] == 4096
        assert info["temperature"] == 0.1
        assert info["timeout"] == 60
        assert info["max_retries"] == 3
        assert info["retry_delay"] == 5
        assert info["max_image_size_mb"] == 20
        assert info["max_image_dimension"] == 2048
        assert "PNG" in info["supported_formats"]
    
    @patch('src.core.vision_client.OpenAI')
    def test_estimate_cost(self, mock_openai):
        """Test cost estimation."""
        client = VisionClient(self.config)
        
        # Test with 10 images
        cost_estimate = client.estimate_cost(10, avg_tokens_per_response=500)
        
        assert cost_estimate["image_count"] == 10
        assert cost_estimate["image_cost_usd"] > 0
        assert cost_estimate["token_cost_usd"] > 0
        assert cost_estimate["total_cost_usd"] > 0
        assert cost_estimate["avg_cost_per_page"] > 0
        
        # Total should be sum of image and token costs
        expected_total = cost_estimate["image_cost_usd"] + cost_estimate["token_cost_usd"]
        assert abs(cost_estimate["total_cost_usd"] - expected_total) < 0.0001
    
    @patch('src.core.vision_client.OpenAI')
    def test_estimate_cost_zero_images(self, mock_openai):
        """Test cost estimation with zero images."""
        client = VisionClient(self.config)
        
        cost_estimate = client.estimate_cost(0)
        
        assert cost_estimate["image_count"] == 0
        assert cost_estimate["image_cost_usd"] == 0
        assert cost_estimate["token_cost_usd"] == 0
        assert cost_estimate["total_cost_usd"] == 0
        assert cost_estimate["avg_cost_per_page"] == 0


class TestVisionAPIError:
    """Tests for VisionAPIError exception."""
    
    def test_vision_api_error_creation(self):
        """Test creating VisionAPIError."""
        error = VisionAPIError("Test API error")
        assert str(error) == "Test API error"
        assert isinstance(error, Exception)


class TestImageValidationError:
    """Tests for ImageValidationError exception."""
    
    def test_image_validation_error_creation(self):
        """Test creating ImageValidationError."""
        error = ImageValidationError("Test validation error")
        assert str(error) == "Test validation error"
        assert isinstance(error, Exception) 