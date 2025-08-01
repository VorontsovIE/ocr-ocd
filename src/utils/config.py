"""Configuration management module."""

from typing import Optional
from pathlib import Path
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import os


class APIConfig(BaseModel):
    """API configuration for different providers."""
    provider: str = Field(..., description="API provider (openai, gemini, claude)")
    api_key: str = Field(..., description="API key for the selected provider")
    openai_api_key: Optional[str] = Field(None, description="OpenAI API key")
    gemini_api_key: Optional[str] = Field(None, description="Gemini API key")
    claude_api_key: Optional[str] = Field(None, description="Claude API key")
    model_name: str = Field(default="gpt-4o", description="Model name")
    max_tokens: int = Field(default=4096, description="Maximum tokens in response")
    temperature: float = Field(default=0.1, description="Generation temperature")
    timeout: int = Field(default=60, description="Request timeout in seconds")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    retry_delay: int = Field(default=5, description="Delay between retries in seconds")


class Config(BaseModel):
    """Application configuration."""
    api: APIConfig
    input_dir: Path = Field(default=Path("."), description="Input directory")
    output_dir: Path = Field(default=Path("output"), description="Output directory")
    temp_dir: Path = Field(default=Path("temp"), description="Temporary files directory")
    logs_dir: Path = Field(default=Path("logs"), description="Logs directory")


def load_config(env_file: Optional[Path] = None, provider: str = "openai") -> Config:
    """Load configuration from environment variables.
    
    Args:
        env_file: Optional path to .env file
        provider: API provider to use
        
    Returns:
        Configuration object
    """
    if env_file:
        load_dotenv(env_file)
    else:
        load_dotenv()
    
    # Get API keys for different providers
    openai_api_key = os.getenv("OPENAI_API_KEY")
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    claude_api_key = os.getenv("CLAUDE_API_KEY")
    
    # Select API key based on provider
    if provider == "openai":
        api_key = openai_api_key
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
    elif provider == "gemini":
        api_key = gemini_api_key
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
    elif provider == "claude":
        api_key = claude_api_key
        if not api_key:
            raise ValueError("CLAUDE_API_KEY environment variable is required")
    else:
        raise ValueError(f"Unsupported provider: {provider}")
    
    try:
        api_config = APIConfig(
            provider=provider,
            api_key=api_key,
            openai_api_key=openai_api_key,
            gemini_api_key=gemini_api_key,
            claude_api_key=claude_api_key,
            model_name=os.getenv("MODEL_NAME", "gpt-4-vision-preview"),
            max_tokens=int(os.getenv("MAX_TOKENS", "4096")),
            temperature=float(os.getenv("TEMPERATURE", "0.1")),
            timeout=int(os.getenv("TIMEOUT", "60")),
            max_retries=int(os.getenv("MAX_RETRIES", "3")),
            retry_delay=int(os.getenv("RETRY_DELAY", "5"))
        )
        
        config = Config(
            api=api_config,
            input_dir=Path(os.getenv("INPUT_DIR", ".")),
            output_dir=Path(os.getenv("OUTPUT_DIR", "output")),
            temp_dir=Path(os.getenv("TEMP_DIR", "temp")),
            logs_dir=Path(os.getenv("LOGS_DIR", "logs"))
        )
        
        # Create directories if they don't exist
        config.output_dir.mkdir(exist_ok=True)
        config.temp_dir.mkdir(exist_ok=True)
        config.logs_dir.mkdir(exist_ok=True)
        
        return config
        
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid configuration: {e}") 