"""
Адаптеры для мультимодальных API
================================

Абстрактный интерфейс и конкретные реализации для работы с разными
мультимодальными API (OpenAI, Gemini, Claude и др.)
"""

import json
import base64
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

# OpenAI
try:
    import openai
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Google Gemini
try:
    import google.generativeai as genai
    from google.generativeai import GenerativeModel
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# Anthropic Claude
try:
    import anthropic
    from anthropic import Anthropic
    CLAUDE_AVAILABLE = True
except ImportError:
    CLAUDE_AVAILABLE = False

from src.utils.logger import get_logger
from src.utils.config import APIConfig


logger = get_logger(__name__)


class VisionProvider(Enum):
    """Поддерживаемые провайдеры мультимодальных API"""
    OPENAI = "openai"
    GEMINI = "gemini"
    CLAUDE = "claude"


@dataclass
class VisionRequest:
    """Структура запроса к мультимодальному API"""
    image_data: bytes
    prompt: str
    page_number: int
    max_tokens: int = 4000
    temperature: float = 0.1
    model_name: Optional[str] = None


@dataclass
class VisionResponse:
    """Структура ответа от мультимодального API"""
    content: str
    model_used: str
    tokens_used: Optional[int] = None
    processing_time: float = 0.0
    error: Optional[str] = None


class VisionAPIAdapter(ABC):
    """Абстрактный адаптер для мультимодальных API"""
    
    def __init__(self, config: APIConfig):
        self.config = config
        self.provider = self._get_provider()
        
    @abstractmethod
    def _get_provider(self) -> VisionProvider:
        """Возвращает тип провайдера"""
        pass
    
    @abstractmethod
    def _encode_image(self, image_data: bytes) -> Union[str, Dict[str, Any]]:
        """Кодирует изображение для API"""
        pass
    
    @abstractmethod
    def _build_messages(self, request: VisionRequest) -> List[Dict[str, Any]]:
        """Строит сообщения для API"""
        pass
    
    @abstractmethod
    def _make_api_call(self, request: VisionRequest) -> VisionResponse:
        """Выполняет запрос к API"""
        pass
    
    def extract_tasks_from_page(
        self, 
        image_data: bytes, 
        page_number: int,
        prompt: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Извлекает задачи со страницы используя мультимодальный API.
        
        Args:
            image_data: Данные изображения страницы
            page_number: Номер страницы
            prompt: Промпт для анализа
            **kwargs: Дополнительные параметры
            
        Returns:
            Результат анализа страницы
        """
        start_time = time.time()
        
        try:
            # Создаем запрос
            request = VisionRequest(
                image_data=image_data,
                prompt=prompt,
                page_number=page_number,
                max_tokens=kwargs.get('max_tokens', 4000),
                temperature=kwargs.get('temperature', 0.1),
                model_name=kwargs.get('model_name', self.config.model_name)
            )
            
            # Выполняем запрос
            response = self._make_api_call(request)
            
            # Парсим результат
            result = self._parse_response(response, page_number)
            
            # Добавляем метаданные
            result.update({
                "provider": self.provider.value,
                "model_used": response.model_used,
                "processing_time": response.processing_time,
                "tokens_used": response.tokens_used,
                "timestamp": datetime.now().isoformat()
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при анализе страницы {page_number}: {e}")
            return self._create_error_response(page_number, str(e))
    
    def _parse_response(self, response: VisionResponse, page_number: int) -> Dict[str, Any]:
        """Парсит ответ от API"""
        if response.error:
            return self._create_error_response(page_number, response.error)
        
        try:
            # Пытаемся извлечь JSON из ответа
            content = response.content.strip()
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            
            if json_start != -1 and json_end > json_start:
                json_str = content[json_start:json_end]
                result = json.loads(json_str)
            else:
                # Если JSON не найден, создаем структуру из текста
                result = {"tasks": []}
                lines = content.split('\n')
                current_task = None
                
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith('```'):
                        if current_task is None:
                            current_task = {
                                "number": f"page_{page_number}_task_{len(result['tasks']) + 1}",
                                "text": line,
                                "type": "задача",
                                "difficulty": "неизвестно"
                            }
                        else:
                            current_task["text"] += " " + line
                
                if current_task:
                    result["tasks"].append(current_task)
            
            # Добавляем метаданные
            result.update({
                "page_number": page_number,
                "analysis_method": f"{self.provider.value}_api",
                "raw_response": content[:500] + "..." if len(content) > 500 else content
            })
            
            return result
            
        except json.JSONDecodeError as e:
            logger.warning(f"Ошибка парсинга JSON для страницы {page_number}: {e}")
            return self._create_fallback_structure(response.content, page_number)
    
    def _create_error_response(self, page_number: int, error: str) -> Dict[str, Any]:
        """Создает ответ об ошибке"""
        return {
            "page_number": page_number,
            "tasks": [],
            "error": error,
            "analysis_method": f"{self.provider.value}_api_error",
            "timestamp": datetime.now().isoformat()
        }
    
    def _create_fallback_structure(self, content: str, page_number: int) -> Dict[str, Any]:
        """Создает резервную структуру при ошибке парсинга"""
        return {
            "page_number": page_number,
            "tasks": [],
            "raw_content": content,
            "analysis_method": f"{self.provider.value}_api_fallback",
            "timestamp": datetime.now().isoformat()
        }
    
    def test_connection(self) -> Dict[str, Any]:
        """Тестирует подключение к API"""
        try:
            # Создаем тестовое изображение (1x1 пиксель)
            test_image = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04\x00\x01\xf5\xf7\xd8\xf8\x00\x00\x00\x00IEND\xaeB`\x82'
            
            request = VisionRequest(
                image_data=test_image,
                prompt="Это тестовое изображение. Ответь 'OK'.",
                page_number=0,
                max_tokens=10
            )
            
            response = self._make_api_call(request)
            
            return {
                "status": "success",
                "provider": self.provider.value,
                "model_used": response.model_used,
                "response": response.content,
                "processing_time": response.processing_time
            }
            
        except Exception as e:
            return {
                "status": "error",
                "provider": self.provider.value,
                "error": str(e)
            }


class OpenAIAdapter(VisionAPIAdapter):
    """Адаптер для OpenAI Vision API"""
    
    def __init__(self, config: APIConfig):
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI library not available. Install with: pip install openai")
        
        super().__init__(config)
        self.client = OpenAI(api_key=config.api_key)
    
    def _get_provider(self) -> VisionProvider:
        return VisionProvider.OPENAI
    
    def _encode_image(self, image_data: bytes) -> str:
        """Кодирует изображение в base64 для OpenAI"""
        return base64.b64encode(image_data).decode('utf-8')
    
    def _build_messages(self, request: VisionRequest) -> List[Dict[str, Any]]:
        """Строит сообщения для OpenAI API"""
        image_base64 = self._encode_image(request.image_data)
        
        return [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": request.prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_base64}"
                        }
                    }
                ]
            }
        ]
    
    def _make_api_call(self, request: VisionRequest) -> VisionResponse:
        """Выполняет запрос к OpenAI API"""
        start_time = time.time()
        
        try:
            response = self.client.chat.completions.create(
                model=request.model_name or "gpt-4-vision-preview",
                messages=self._build_messages(request),
                max_tokens=request.max_tokens,
                temperature=request.temperature
            )
            
            processing_time = time.time() - start_time
            
            return VisionResponse(
                content=response.choices[0].message.content,
                model_used=request.model_name or "gpt-4-vision-preview",
                tokens_used=getattr(response.usage, 'total_tokens', None),
                processing_time=processing_time
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            return VisionResponse(
                content="",
                model_used=request.model_name or "gpt-4-vision-preview",
                processing_time=processing_time,
                error=str(e)
            )


class GeminiAdapter(VisionAPIAdapter):
    """Адаптер для Google Gemini API"""
    
    def __init__(self, config: APIConfig):
        if not GEMINI_AVAILABLE:
            raise ImportError("Google Generative AI library not available. Install with: pip install google-generativeai")
        
        super().__init__(config)
        genai.configure(api_key=config.api_key)
        self.model = GenerativeModel(config.model_name or "gemini-2.0-flash-exp")
    
    def _get_provider(self) -> VisionProvider:
        return VisionProvider.GEMINI
    
    def _encode_image(self, image_data: bytes) -> Dict[str, Any]:
        """Кодирует изображение для Gemini API с сжатием"""
        try:
            # Сжимаем изображение для уменьшения размера
            from PIL import Image
            import io
            
            # Открываем изображение
            image = Image.open(io.BytesIO(image_data))
            
            # Уменьшаем размер если изображение слишком большое
            max_size = 1024
            if max(image.size) > max_size:
                ratio = max_size / max(image.size)
                new_size = tuple(int(dim * ratio) for dim in image.size)
                image = image.resize(new_size, Image.Resampling.LANCZOS)
            
            # Сохраняем с сжатием
            buffer = io.BytesIO()
            image.save(buffer, format='PNG', optimize=True, quality=85)
            compressed_data = buffer.getvalue()
            
            return {
                "mime_type": "image/png",
                "data": base64.b64encode(compressed_data).decode('utf-8')
            }
        except Exception as e:
            # Если сжатие не удалось, используем оригинальные данные
            return {
                "mime_type": "image/png",
                "data": base64.b64encode(image_data).decode('utf-8')
            }
    
    def _build_messages(self, request: VisionRequest) -> List[Dict[str, Any]]:
        """Строит сообщения для Gemini API"""
        return [
            {
                "role": "user",
                "parts": [
                    {"text": request.prompt},
                    {"inline_data": self._encode_image(request.image_data)}
                ]
            }
        ]
    
    def _make_api_call(self, request: VisionRequest) -> VisionResponse:
        """Выполняет запрос к Gemini API"""
        start_time = time.time()
        
        try:
            response = self.model.generate_content(
                self._build_messages(request),
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=request.max_tokens,
                    temperature=request.temperature
                )
            )
            
            processing_time = time.time() - start_time
            
            return VisionResponse(
                content=response.text,
                model_used="gemini-2.0-flash-exp",
                processing_time=processing_time
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = str(e)
            
            # Обрабатываем ошибку превышения лимита метаданных
            if "429" in error_msg and "metadata size exceeds" in error_msg:
                error_msg = "Превышен лимит размера метаданных (429). Попробуйте уменьшить размер изображения или использовать разделение страниц."
            
            return VisionResponse(
                content="",
                model_used="gemini-2.0-flash-exp",
                processing_time=processing_time,
                error=error_msg
            )


class ClaudeAdapter(VisionAPIAdapter):
    """Адаптер для Anthropic Claude API"""
    
    def __init__(self, config: APIConfig):
        if not CLAUDE_AVAILABLE:
            raise ImportError("Anthropic library not available. Install with: pip install anthropic")
        
        super().__init__(config)
        self.client = Anthropic(api_key=config.api_key)
    
    def _get_provider(self) -> VisionProvider:
        return VisionProvider.CLAUDE
    
    def _encode_image(self, image_data: bytes) -> Dict[str, Any]:
        """Кодирует изображение для Claude API"""
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": base64.b64encode(image_data).decode('utf-8')
            }
        }
    
    def _build_messages(self, request: VisionRequest) -> List[Dict[str, Any]]:
        """Строит сообщения для Claude API"""
        return [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": request.prompt},
                    self._encode_image(request.image_data)
                ]
            }
        ]
    
    def _make_api_call(self, request: VisionRequest) -> VisionResponse:
        """Выполняет запрос к Claude API"""
        start_time = time.time()
        
        try:
            response = self.client.messages.create(
                model=request.model_name or "claude-3-5-sonnet-20241022",
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                messages=self._build_messages(request)
            )
            
            processing_time = time.time() - start_time
            
            return VisionResponse(
                content=response.content[0].text,
                model_used=request.model_name or "claude-3-5-sonnet-20241022",
                tokens_used=getattr(response, 'usage', {}).get('total_tokens'),
                processing_time=processing_time
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            return VisionResponse(
                content="",
                model_used=request.model_name or "claude-3-5-sonnet-20241022",
                processing_time=processing_time,
                error=str(e)
            )


class VisionAdapterFactory:
    """Фабрика для создания адаптеров мультимодальных API"""
    
    @staticmethod
    def create_adapter(provider: VisionProvider, config: APIConfig) -> VisionAPIAdapter:
        """Создает адаптер для указанного провайдера"""
        
        if provider == VisionProvider.OPENAI:
            return OpenAIAdapter(config)
        elif provider == VisionProvider.GEMINI:
            return GeminiAdapter(config)
        elif provider == VisionProvider.CLAUDE:
            return ClaudeAdapter(config)
        else:
            raise ValueError(f"Неподдерживаемый провайдер: {provider}")
    
    @staticmethod
    def get_available_providers() -> List[VisionProvider]:
        """Возвращает список доступных провайдеров"""
        available = []
        
        if OPENAI_AVAILABLE:
            available.append(VisionProvider.OPENAI)
        
        if GEMINI_AVAILABLE:
            available.append(VisionProvider.GEMINI)
        
        if CLAUDE_AVAILABLE:
            available.append(VisionProvider.CLAUDE)
        
        return available
    
    @staticmethod
    def get_default_provider() -> VisionProvider:
        """Возвращает провайдер по умолчанию (Gemini)"""
        if GEMINI_AVAILABLE:
            return VisionProvider.GEMINI
        elif OPENAI_AVAILABLE:
            return VisionProvider.OPENAI
        elif CLAUDE_AVAILABLE:
            return VisionProvider.CLAUDE
        else:
            raise RuntimeError("Нет доступных мультимодальных API провайдеров") 