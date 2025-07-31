"""OpenAI Vision API client for text extraction from images."""

import json
import time
from typing import Dict, Any, Optional, List
import base64
from openai import OpenAI
from openai import APIError, RateLimitError, APIConnectionError, APITimeoutError
from PIL import Image
import io
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log
)
from src.utils.logger import get_logger, log_api_request, log_api_response, log_error_with_context
from src.utils.config import APIConfig
from src.core.prompt_manager import PromptManager, PromptType


logger = get_logger(__name__)


class VisionAPIError(Exception):
    """Custom exception for Vision API errors."""
    pass


class ImageValidationError(Exception):
    """Custom exception for image validation errors."""
    pass


class VisionClient:
    """Client for interacting with OpenAI ChatGPT-4 Vision API."""
    
    def __init__(self, config: APIConfig) -> None:
        """Initialize Vision API client.
        
        Args:
            config: API configuration object
        """
        self.config = config
        self.client = OpenAI(api_key=config.api_key)
        
        # Image validation limits
        self.max_image_size_mb = 20  # OpenAI limit
        self.max_image_dimension = 2048  # Our optimization limit
        self.supported_formats = ['PNG', 'JPEG', 'JPG', 'WEBP', 'GIF']
        
        # Retry configuration
        self.retry_decorator = retry(
            stop=stop_after_attempt(self.config.max_retries),
            wait=wait_exponential(
                multiplier=1,
                min=self.config.retry_delay,
                max=60  # Maximum wait time
            ),
            retry=retry_if_exception_type((
                RateLimitError,  # HTTP 429
                APIConnectionError,  # Connection issues
                APITimeoutError,  # Timeout errors
                APIError  # Other API errors (includes 500, 502, 503)
            )),
            before_sleep=before_sleep_log(logger, "WARNING"),
            after=after_log(logger, "INFO")
        )
        
        # Initialize prompt manager
        self.prompt_manager = PromptManager()
        
        logger.info(
            "VisionClient initialized",
            model=self.config.model_name,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            max_retries=self.config.max_retries,
            retry_delay=self.config.retry_delay,
            prompt_templates=len(self.prompt_manager.list_available_types())
        )
    
    def validate_image(self, image_data: bytes) -> Dict[str, Any]:
        """Validate image data before sending to API.
        
        Args:
            image_data: Raw image bytes
            
        Returns:
            Dictionary with image metadata
            
        Raises:
            ImageValidationError: If image validation fails
        """
        try:
            # Check size
            size_mb = len(image_data) / (1024 * 1024)
            if size_mb > self.max_image_size_mb:
                raise ImageValidationError(
                    f"Image size {size_mb:.1f}MB exceeds limit of {self.max_image_size_mb}MB"
                )
            
            # Check format and dimensions
            image = Image.open(io.BytesIO(image_data))
            
            if image.format not in self.supported_formats:
                raise ImageValidationError(
                    f"Unsupported image format: {image.format}. "
                    f"Supported formats: {', '.join(self.supported_formats)}"
                )
            
            width, height = image.size
            max_dimension = max(width, height)
            
            validation_result = {
                "size_bytes": len(image_data),
                "size_mb": size_mb,
                "format": image.format,
                "dimensions": (width, height),
                "max_dimension": max_dimension,
                "is_oversized": max_dimension > self.max_image_dimension
            }
            
            logger.debug(
                "Image validation completed",
                **validation_result
            )
            
            return validation_result
            
        except Exception as e:
            error_msg = f"Image validation failed: {e}"
            log_error_with_context(e, {"operation": "validate_image"})
            raise ImageValidationError(error_msg) from e
    
    def encode_image(self, image_data: bytes) -> str:
        """Encode image data to base64 string.
        
        Args:
            image_data: Raw image bytes
            
        Returns:
            Base64 encoded image string
        """
        try:
            encoded = base64.b64encode(image_data).decode('utf-8')
            logger.debug(f"Image encoded to base64, size: {len(encoded)} chars")
            return encoded
        except Exception as e:
            error_msg = f"Failed to encode image: {e}"
            log_error_with_context(e, {"operation": "encode_image"})
            raise VisionAPIError(error_msg) from e
    
    def build_extraction_prompt(
        self, 
        page_number: int,
        prompt_type: Optional[PromptType] = None,
        page_hints: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build prompt for Vision API to extract task information.
        
        Args:
            page_number: Page number for context
            prompt_type: Optional specific prompt type to use
            page_hints: Optional hints about page content for auto-selection
            
        Returns:
            Formatted prompt string
        """
        if prompt_type:
            return self.prompt_manager.get_prompt(prompt_type, page_number)
        else:
            return self.prompt_manager.get_prompt_auto(page_number, page_hints)
    
    def _make_api_call_with_retry(
        self,
        messages: List[Dict[str, Any]],
        page_number: int,
        attempt_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Make API call with retry logic.
        
        Args:
            messages: Messages for API
            page_number: Page number for logging
            attempt_context: Context for retry attempts
            
        Returns:
            API response data
            
        Raises:
            VisionAPIError: If all retries fail
        """
        @self.retry_decorator
        def _api_call():
            try:
                logger.debug(
                    f"Making API call attempt for page {page_number}",
                    attempt=attempt_context.get("attempt_number", 1),
                    max_retries=self.config.max_retries
                )
                
                response = self.client.chat.completions.create(
                    model=self.config.model_name,
                    messages=messages,
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                    timeout=self.config.timeout
                )
                
                logger.info(
                    f"API call successful for page {page_number}",
                    tokens_used=response.usage.total_tokens if response.usage else 0
                )
                
                return response
                
            except RateLimitError as e:
                logger.warning(
                    f"Rate limit hit for page {page_number}",
                    error=str(e),
                    retry_after=getattr(e, 'retry_after', 'unknown')
                )
                raise
                
            except APIConnectionError as e:
                logger.warning(
                    f"API connection error for page {page_number}",
                    error=str(e)
                )
                raise
                
            except APITimeoutError as e:
                logger.warning(
                    f"API timeout for page {page_number}",
                    error=str(e),
                    timeout=self.config.timeout
                )
                raise
                
            except APIError as e:
                logger.warning(
                    f"API error for page {page_number}",
                    error=str(e),
                    status_code=getattr(e, 'status_code', 'unknown')
                )
                raise
                
            except Exception as e:
                logger.error(
                    f"Unexpected error for page {page_number}",
                    error=str(e),
                    error_type=type(e).__name__
                )
                # Don't retry on unexpected errors
                raise VisionAPIError(f"Unexpected API error: {e}") from e
        
        try:
            return _api_call()
        except Exception as e:
            # If all retries failed, wrap in VisionAPIError
            if isinstance(e, VisionAPIError):
                raise
            else:
                logger.error(
                    f"All retry attempts failed for page {page_number}",
                    error=str(e),
                    max_retries=self.config.max_retries
                )
                raise VisionAPIError(f"API call failed after {self.config.max_retries} retries: {e}") from e
    
    def extract_tasks_from_page(
        self, 
        image_data: bytes, 
        page_number: int,
        custom_prompt: Optional[str] = None,
        prompt_type: Optional[PromptType] = None,
        page_hints: Optional[Dict[str, Any]] = None,
        use_fallback_on_error: bool = True
    ) -> Dict[str, Any]:
        """Extract mathematical tasks from page image using Vision API.
        
        Args:
            image_data: Image data as bytes
            page_number: Page number for context
            custom_prompt: Optional custom prompt (overrides other prompt options)
            prompt_type: Optional specific prompt type to use
            page_hints: Optional hints about page content for auto-selection
            use_fallback_on_error: Whether to retry with fallback prompt on parsing errors
            
        Returns:
            Dictionary with extracted tasks data
            
        Raises:
            VisionAPIError: If API call fails
            ImageValidationError: If image validation fails
        """
        start_time = time.time()
        
        try:
            # Validate image
            image_info = self.validate_image(image_data)
            
            # Encode image
            base64_image = self.encode_image(image_data)
            
            # Build prompt
            if custom_prompt:
                prompt = custom_prompt
            else:
                prompt = self.build_extraction_prompt(page_number, prompt_type, page_hints)
            
            # Prepare API request
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}",
                                "detail": "high"
                            }
                        }
                    ]
                }
            ]
            
            # Log API request
            log_api_request(
                url="https://api.openai.com/v1/chat/completions",
                method="POST",
                model=self.config.model_name,
                page_number=page_number,
                image_size_mb=image_info["size_mb"],
                max_tokens=self.config.max_tokens
            )
            
            # Make API call with retry logic
            attempt_context = {"attempt_number": 1}
            response = self._make_api_call_with_retry(messages, page_number, attempt_context)
            
            duration = time.time() - start_time
            
            # Log API response
            log_api_response(
                url="https://api.openai.com/v1/chat/completions",
                status_code=200,
                duration=duration,
                tokens_used=response.usage.total_tokens if response.usage else 0,
                model=self.config.model_name
            )
            
            # Extract response content
            content = response.choices[0].message.content
            
            # Try to validate JSON response
            try:
                parsed_data = self.prompt_manager.validate_response_json(content)
                json_valid = True
                logger.debug("Response JSON validation successful")
            except ValueError as e:
                logger.warning(f"JSON validation failed: {e}")
                parsed_data = None
                json_valid = False
                
                # Retry with fallback prompt if enabled and not already using fallback
                if (use_fallback_on_error and 
                    prompt_type != PromptType.FALLBACK and 
                    not custom_prompt):
                    
                    logger.info(f"Retrying page {page_number} with fallback prompt")
                    return self.extract_tasks_from_page(
                        image_data=image_data,
                        page_number=page_number,
                        prompt_type=PromptType.FALLBACK,
                        use_fallback_on_error=False  # Prevent infinite recursion
                    )
            
            logger.info(
                "Vision API call completed successfully",
                page_number=page_number,
                duration_seconds=round(duration, 2),
                tokens_used=response.usage.total_tokens if response.usage else 0,
                response_length=len(content) if content else 0,
                json_valid=json_valid
            )
            
            return {
                "content": content,
                "parsed_data": parsed_data,
                "json_valid": json_valid,
                "usage": response.usage.model_dump() if response.usage else {},
                "model": response.model,
                "processing_time": duration,
                "image_info": image_info,
                "prompt_type": prompt_type.value if prompt_type else "auto"
            }
            
        except Exception as e:
            duration = time.time() - start_time
            
            log_error_with_context(
                e,
                {
                    "operation": "extract_tasks_from_page",
                    "page_number": page_number,
                    "duration": duration,
                    "image_size_bytes": len(image_data)
                }
            )
            
            # Re-raise as VisionAPIError
            if isinstance(e, (ImageValidationError, VisionAPIError)):
                raise
            else:
                raise VisionAPIError(f"Vision API call failed: {e}") from e
    
    def test_api_connection(self) -> Dict[str, Any]:
        """Test API connection with a simple request.
        
        Returns:
            Dictionary with test results
            
        Raises:
            VisionAPIError: If connection test fails
        """
        try:
            logger.info("Testing API connection...")
            
            # Create a simple test image (1x1 pixel)
            test_image = Image.new('RGB', (1, 1), color='white')
            img_buffer = io.BytesIO()
            test_image.save(img_buffer, format='PNG')
            test_image_data = img_buffer.getvalue()
            
            # Simple test prompt
            test_prompt = "Describe what you see in this image in one word."
            
            # Make test call
            result = self.extract_tasks_from_page(
                image_data=test_image_data,
                page_number=0,
                custom_prompt=test_prompt
            )
            
            logger.info("API connection test successful")
            
            return {
                "status": "success",
                "model": result["model"],
                "response_time": result["processing_time"],
                "tokens_used": result["usage"].get("total_tokens", 0)
            }
            
        except Exception as e:
            log_error_with_context(e, {"operation": "test_api_connection"})
            raise VisionAPIError(f"API connection test failed: {e}") from e
    
    def get_retry_statistics(self) -> Dict[str, Any]:
        """Get retry configuration statistics.
        
        Returns:
            Dictionary with retry settings
        """
        return {
            "max_retries": self.config.max_retries,
            "base_retry_delay": self.config.retry_delay,
            "max_retry_delay": 60,
            "retry_strategy": "exponential_backoff",
            "retryable_errors": [
                "RateLimitError (HTTP 429)",
                "APIConnectionError",
                "APITimeoutError", 
                "APIError (HTTP 500, 502, 503)"
            ],
            "non_retryable_errors": [
                "ImageValidationError",
                "Authentication errors",
                "Invalid request format"
            ]
        }
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the configured model.
        
        Returns:
            Dictionary with model configuration
        """
        return {
            "model_name": self.config.model_name,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "timeout": self.config.timeout,
            "max_retries": self.config.max_retries,
            "retry_delay": self.config.retry_delay,
            "max_image_size_mb": self.max_image_size_mb,
            "max_image_dimension": self.max_image_dimension,
            "supported_formats": self.supported_formats
        }
    
    def estimate_cost(
        self, 
        image_count: int, 
        avg_tokens_per_response: int = 500
    ) -> Dict[str, float]:
        """Estimate API usage cost.
        
        Args:
            image_count: Number of images to process
            avg_tokens_per_response: Average tokens per API response
            
        Returns:
            Dictionary with cost estimates
        """
        # OpenAI GPT-4 Vision pricing (as of 2024)
        # These are approximate rates - check current pricing
        cost_per_image = 0.01275  # $0.01275 per image
        cost_per_1k_tokens = 0.03  # $0.03 per 1K tokens
        
        image_cost = image_count * cost_per_image
        token_cost = (image_count * avg_tokens_per_response / 1000) * cost_per_1k_tokens
        total_cost = image_cost + token_cost
        
        return {
            "image_count": image_count,
            "image_cost_usd": round(image_cost, 4),
            "token_cost_usd": round(token_cost, 4),
            "total_cost_usd": round(total_cost, 4),
            "avg_cost_per_page": round(total_cost / image_count, 4) if image_count > 0 else 0
        } 