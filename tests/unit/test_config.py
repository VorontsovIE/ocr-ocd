"""Tests for configuration module."""

import os
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open
from src.utils.config import APIConfig, Config, load_config


class TestAPIConfig:
    """Tests for APIConfig model."""
    
    def test_api_config_valid(self):
        """Test creating valid API configuration."""
        config = APIConfig(api_key="test_key")
        assert config.api_key == "test_key"
        assert config.model_name == "gpt-4-vision-preview"
        assert config.max_tokens == 4096
        assert config.temperature == 0.1
        assert config.timeout == 60
        assert config.max_retries == 3
        assert config.retry_delay == 5
    
    def test_api_config_custom_values(self):
        """Test creating API configuration with custom values."""
        config = APIConfig(
            api_key="custom_key",
            model_name="custom-model",
            max_tokens=2048,
            temperature=0.5,
            timeout=120,
            max_retries=5,
            retry_delay=10
        )
        assert config.api_key == "custom_key"
        assert config.model_name == "custom-model"
        assert config.max_tokens == 2048
        assert config.temperature == 0.5
        assert config.timeout == 120
        assert config.max_retries == 5
        assert config.retry_delay == 10
    
    def test_api_config_missing_key(self):
        """Test that API config requires api_key."""
        with pytest.raises(ValueError):
            APIConfig()


class TestConfig:
    """Tests for Config model."""
    
    def test_config_with_api(self):
        """Test creating config with API configuration."""
        api_config = APIConfig(api_key="test_key")
        config = Config(api=api_config)
        
        assert config.api.api_key == "test_key"
        assert config.input_dir == Path(".")
        assert config.output_dir == Path("output")
        assert config.temp_dir == Path("temp")
        assert config.logs_dir == Path("logs")
    
    def test_config_custom_paths(self):
        """Test creating config with custom paths."""
        api_config = APIConfig(api_key="test_key")
        config = Config(
            api=api_config,
            input_dir=Path("/custom/input"),
            output_dir=Path("/custom/output"),
            temp_dir=Path("/custom/temp"),
            logs_dir=Path("/custom/logs")
        )
        
        assert config.input_dir == Path("/custom/input")
        assert config.output_dir == Path("/custom/output")
        assert config.temp_dir == Path("/custom/temp")
        assert config.logs_dir == Path("/custom/logs")


class TestLoadConfig:
    """Tests for load_config function."""
    
    @patch.dict(os.environ, {
        'OPENAI_API_KEY': 'test_key_123',
        'MODEL_NAME': 'gpt-4-custom',
        'MAX_TOKENS': '2048',
        'TEMPERATURE': '0.5',
        'TIMEOUT': '120',
        'MAX_RETRIES': '5',
        'RETRY_DELAY': '10',
        'OUTPUT_DIR': 'custom_output',
        'TEMP_DIR': 'custom_temp',
        'LOGS_DIR': 'custom_logs'
    })
    @patch('src.utils.config.Path.mkdir')
    def test_load_config_from_env(self, mock_mkdir):
        """Test loading configuration from environment variables."""
        config = load_config()
        
        # Check API config
        assert config.api.api_key == 'test_key_123'
        assert config.api.model_name == 'gpt-4-custom'
        assert config.api.max_tokens == 2048
        assert config.api.temperature == 0.5
        assert config.api.timeout == 120
        assert config.api.max_retries == 5
        assert config.api.retry_delay == 10
        
        # Check paths
        assert config.output_dir == Path('custom_output')
        assert config.temp_dir == Path('custom_temp')
        assert config.logs_dir == Path('custom_logs')
        
        # Check that directories were created
        assert mock_mkdir.call_count == 3
    
    @patch.dict(os.environ, {}, clear=True)
    def test_load_config_missing_api_key(self):
        """Test that missing API key raises ValueError."""
        with pytest.raises(ValueError, match="OPENAI_API_KEY environment variable is required"):
            load_config()
    
    @patch.dict(os.environ, {
        'OPENAI_API_KEY': 'test_key',
        'MAX_TOKENS': 'invalid_number'
    })
    def test_load_config_invalid_values(self):
        """Test that invalid environment values raise ValueError."""
        with pytest.raises(ValueError, match="Invalid configuration"):
            load_config()
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test_key'})
    @patch('src.utils.config.Path.mkdir')
    def test_load_config_defaults(self, mock_mkdir):
        """Test loading configuration with default values."""
        config = load_config()
        
        # Check default API values
        assert config.api.api_key == 'test_key'
        assert config.api.model_name == 'gpt-4-vision-preview'
        assert config.api.max_tokens == 4096
        assert config.api.temperature == 0.1
        assert config.api.timeout == 60
        assert config.api.max_retries == 3
        assert config.api.retry_delay == 5
        
        # Check default paths
        assert config.input_dir == Path('.')
        assert config.output_dir == Path('output')
        assert config.temp_dir == Path('temp')
        assert config.logs_dir == Path('logs')
    
    @patch('src.utils.config.load_dotenv')
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test_key'})
    @patch('src.utils.config.Path.mkdir')
    def test_load_config_with_env_file(self, mock_mkdir, mock_load_dotenv):
        """Test loading configuration with .env file."""
        env_file = Path('.env.test')
        load_config(env_file)
        
        mock_load_dotenv.assert_called_once_with(env_file)
    
    @patch('src.utils.config.load_dotenv')
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test_key'})
    @patch('src.utils.config.Path.mkdir')
    def test_load_config_without_env_file(self, mock_mkdir, mock_load_dotenv):
        """Test loading configuration without specifying .env file."""
        load_config()
        
        mock_load_dotenv.assert_called_once_with() 