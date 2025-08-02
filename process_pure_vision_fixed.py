#!/usr/bin/env python3
"""
OCR-OCD Pure Vision Fixed: Прямая интеграция OpenAI
==================================================

Исправленная чистая система:
- 📖 PDF → изображения страниц
- 🖼️ Прямой GPT-4 Vision API → анализ задач  
- 📊 CSV → структурированные результаты

С рабочей прямой интеграцией OpenAI!
"""

import sys
import json
import time
import base64
import os
import click
import openai
import asyncio
import concurrent.futures
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from PIL import Image, ImageEnhance, ImageFilter
import io

# Добавляем src в Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.core.pdf_processor import PDFProcessor
from src.core.vision_adapters import VisionAdapterFactory, VisionProvider
from src.utils.logger import setup_development_logger, setup_production_logger, get_logger
from src.utils.config import APIConfig


class FileIdentifier:
    """Генератор уникальных идентификаторов для файлов"""
    
    @staticmethod
    def generate(pdf_path: str) -> str:
        """
        Генерирует уникальный идентификатор для PDF файла.
        
        Args:
            pdf_path: Путь к PDF файлу
            
        Returns:
            Уникальный идентификатор в формате "basename_md5hash"
        """
        file_path = Path(pdf_path)
        basename = file_path.stem
        
        # Генерируем MD5 хеш содержимого файла
        hash_md5 = hashlib.md5()
        with open(pdf_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        
        file_hash = hash_md5.hexdigest()[:8]
        clean_basename = "".join(c for c in basename if c.isalnum() or c in "_-")[:20]
        
        return f"{clean_basename}_{file_hash}"


class ImageSplitter:
    """Разделение изображений для лучшего анализа"""
    
    @staticmethod
    def split_image(image_data: bytes, split_mode: str = "vertical") -> List[bytes]:
        """
        Разделяет изображение на части для лучшего анализа многоколоночных страниц.
        
        Args:
            image_data: Данные изображения
            split_mode: Режим разделения ("original", "vertical", "horizontal", "grid")
            
        Returns:
            Список частей изображения
        """
        if split_mode == "original":
            return [image_data]
        
        image = Image.open(io.BytesIO(image_data))
        width, height = image.size
        parts = []
        
        if split_mode == "vertical":
            # Разделяем вертикально на 2 части (левая/правая)
            left_part = image.crop((0, 0, width // 2, height))
            right_part = image.crop((width // 2, 0, width, height))
            
            for part in [left_part, right_part]:
                buffer = io.BytesIO()
                part.save(buffer, format='PNG', quality=95)
                parts.append(buffer.getvalue())
                
        elif split_mode == "horizontal":
            # Разделяем горизонтально на 2 части (верхняя/нижняя)
            top_part = image.crop((0, 0, width, height // 2))
            bottom_part = image.crop((0, height // 2, width, height))
            
            for part in [top_part, bottom_part]:
                buffer = io.BytesIO()
                part.save(buffer, format='PNG', quality=95)
                parts.append(buffer.getvalue())
                
        elif split_mode == "grid":
            # Разделяем на сетку 2x2
            for i in range(2):
                for j in range(2):
                    part = image.crop((
                        i * width // 2, 
                        j * height // 2, 
                        (i + 1) * width // 2, 
                        (j + 1) * height // 2
                    ))
                    buffer = io.BytesIO()
                    part.save(buffer, format='PNG', quality=95)
                    parts.append(buffer.getvalue())
        
        return parts


class ImageEnhancer:
    """Улучшение качества изображений для OCR"""
    
    @staticmethod
    def enhance_image(image_data: bytes) -> bytes:
        """
        Улучшает качество изображения для лучшего распознавания.
        
        Args:
            image_data: Исходные данные изображения
            
        Returns:
            Улучшенные данные изображения
        """
        image = Image.open(io.BytesIO(image_data))
        
        # Конвертируем в RGB если нужно
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Увеличиваем контрастность
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.5)
        
        # Увеличиваем резкость
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(1.3)
        
        # Увеличиваем яркость
        enhancer = ImageEnhance.Brightness(image)
        image = enhancer.enhance(1.1)
        
        # Сохраняем улучшенное изображение
        buffer = io.BytesIO()
        image.save(buffer, format='PNG', quality=95)
        return buffer.getvalue()


class VisionAPI:
    """Интерфейс для работы с мультимодальными API"""
    
    def __init__(self, provider: VisionProvider = VisionProvider.GEMINI, images_dir: Optional[Path] = None):
        load_dotenv()
        self.provider = provider
        self.images_dir = images_dir or Path("temp/images")
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger(__name__)
        
        # Создаем конфигурацию API
        api_key = None
        model_name = "gpt-4-vision-preview"  # По умолчанию для OpenAI
        
        if provider == VisionProvider.OPENAI:
            api_key = os.getenv("OPENAI_API_KEY")
            model_name = "gpt-4-vision-preview"
        elif provider == VisionProvider.GEMINI:
            api_key = os.getenv("GEMINI_API_KEY")
            model_name = "gemini-2.0-flash-exp"
        elif provider == VisionProvider.CLAUDE:
            api_key = os.getenv("CLAUDE_API_KEY")
            model_name = "claude-3-5-sonnet-20241022"
        
        if not api_key:
            raise ValueError(f"API key for {provider.value} is required")
        
        self.api_config = APIConfig(
            provider=provider.value,
            api_key=api_key,
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            gemini_api_key=os.getenv("GEMINI_API_KEY"),
            claude_api_key=os.getenv("CLAUDE_API_KEY"),
            model_name=model_name
        )
        
        # Создаем адаптер для выбранного провайдера
        self.adapter = VisionAdapterFactory.create_adapter(provider, self.api_config)
        
    def _save_image_to_disk(self, image_data: bytes, filename: str, subfolder: str = "") -> Optional[Path]:
        """Сохраняет изображение на диск для отладки"""
        try:
            subfolder_path = self.images_dir / subfolder
            subfolder_path.mkdir(parents=True, exist_ok=True)
            
            file_path = subfolder_path / filename
            with open(file_path, 'wb') as f:
                f.write(image_data)
            return file_path
        except Exception as e:
            get_logger(__name__).warning(f"Не удалось сохранить изображение: {e}")
            return None
    
    def _enhance_image_for_ocr(self, image_data: bytes) -> bytes:
        """Улучшает изображение для OCR"""
        return ImageEnhancer.enhance_image(image_data)
    
    def extract_tasks_from_page(self, image_data: bytes, page_number: int, 
                               use_split_analysis: bool = True, split_mode: str = "vertical") -> Dict[str, Any]:
        """
        Извлекает задачи со страницы используя мультимодальный API.
        
        Args:
            image_data: Данные изображения страницы
            page_number: Номер страницы
            use_split_analysis: Использовать ли разделение изображения
            split_mode: Режим разделения
            
        Returns:
            Результат анализа страницы
        """
        enhanced_image_data = self._enhance_image_for_ocr(image_data)
        
        if use_split_analysis:
            return self._analyze_with_split_method(enhanced_image_data, page_number, split_mode)
        else:
            return self._analyze_whole_image(enhanced_image_data, page_number)
    
    def _analyze_with_split_method(self, enhanced_image_data: bytes, page_number: int, 
                                  split_mode: str = "vertical") -> Dict[str, Any]:
        """Анализирует изображение с разделением на части"""
        image_parts = ImageSplitter.split_image(enhanced_image_data, split_mode)
        
        all_tasks = []
        part_results = []
        has_errors = False
        max_retry_delay = None
        
        for i, part_data in enumerate(image_parts):
            part_name = f"part_{i+1}"
            part_result = self._analyze_image_part(part_data, page_number, part_name, i+1)
            part_results.append(part_result)
            
            # Проверяем ошибки в частях
            if part_result.get("error"):
                has_errors = True
                self.logger.error(f"Страница {page_number}, часть {part_name}: {part_result['error']}")
            
            # Проверяем retry_delay в частях
            if part_result.get("retry_delay"):
                retry_delay = part_result["retry_delay"]
                if max_retry_delay is None or retry_delay > max_retry_delay:
                    max_retry_delay = retry_delay
            
            if part_result.get("tasks"):
                all_tasks.extend(part_result["tasks"])
        
        # Объединяем результаты
        combined_result = {
            "page_number": page_number,
            "analysis_method": f"split_{split_mode}",
            "parts_analyzed": len(image_parts),
            "tasks": all_tasks,
            "part_results": part_results,
            "total_tasks": len(all_tasks),
            "timestamp": datetime.now().isoformat()
        }
        
        # Если есть ошибки в частях, добавляем общую ошибку
        if has_errors:
            combined_result["error"] = f"Ошибки в {len([p for p in part_results if p.get('error')])} из {len(part_results)} частей"
        
        # Передаем максимальный retry_delay из частей
        if max_retry_delay:
            combined_result["retry_delay"] = max_retry_delay
        
        return combined_result
    
    def _analyze_image_part(self, part_data: bytes, page_number: int, 
                           part_name: str, part_number: int) -> Dict[str, Any]:
        """Анализирует часть изображения"""
        try:
            # Сохраняем часть для отладки
            debug_filename = f"page_{page_number}_{part_name}.png"
            self._save_image_to_disk(part_data, debug_filename, f"page_{page_number}")
            
            # Формируем короткий промпт для анализа
            prompt = f"""Найди математические задачи на странице {page_number} (часть {part_number}). Верни JSON:
{{
    "tasks": [
        {{
            "number": "номер",
            "text": "текст задачи",
            "type": "тип",
            "difficulty": "сложность",
            "part": "{part_name}"
        }}
    ]
}}"""
            
            # Используем адаптер для отправки запроса
            result = self.adapter.extract_tasks_from_page(
                image_data=part_data,
                page_number=page_number,
                prompt=prompt
            )
            
            # Добавляем метаданные
            result.update({
                "page_number": page_number,
                "part_name": part_name,
                "part_number": part_number,
                "analysis_method": f"{self.provider.value}_api_split",
                "timestamp": datetime.now().isoformat()
            })
            
            return result
                
        except Exception as e:
            self.logger.error(f"Ошибка анализа части {part_name}: {e}")
            return {
                "page_number": page_number,
                "part_name": part_name,
                "part_number": part_number,
                "tasks": [],
                "error": str(e),
                "analysis_method": f"{self.provider.value}_api_split",
                "timestamp": datetime.now().isoformat()
            }
    
    def _analyze_whole_image(self, enhanced_image_data: bytes, page_number: int) -> Dict[str, Any]:
        """Анализирует целое изображение без разделения"""
        try:
            # Сохраняем изображение для отладки
            debug_filename = f"page_{page_number}_whole.png"
            self._save_image_to_disk(enhanced_image_data, debug_filename, f"page_{page_number}")
            
            # Формируем короткий промпт для анализа
            prompt = f"""Найди математические задачи на странице {page_number}. Верни JSON:
{{
    "tasks": [
        {{
            "number": "номер",
            "text": "текст задачи",
            "type": "тип",
            "difficulty": "сложность"
        }}
    ]
}}"""
            
            # Используем адаптер для отправки запроса
            result = self.adapter.extract_tasks_from_page(
                image_data=enhanced_image_data,
                page_number=page_number,
                prompt=prompt
            )
            
            # Добавляем метаданные
            result.update({
                "page_number": page_number,
                "analysis_method": f"{self.provider.value}_api_whole",
                "timestamp": datetime.now().isoformat()
            })
            
            return result
                
        except Exception as e:
            self.logger.error(f"Ошибка анализа страницы {page_number}: {e}")
            return {
                "page_number": page_number,
                "tasks": [],
                "error": str(e),
                "analysis_method": f"{self.provider.value}_api_whole",
                "timestamp": datetime.now().isoformat()
            }
    
    def _create_fallback_structure(self, content: str, page_number: int) -> Dict[str, Any]:
        """Создает резервную структуру при ошибке парсинга JSON"""
        return {
            "page_number": page_number,
            "tasks": [
                {
                    "number": "fallback_1",
                    "text": content[:500] + "..." if len(content) > 500 else content,
                    "type": "задача",
                    "difficulty": "неизвестно",
                    "note": "Извлечено из неструктурированного ответа API"
                }
            ],
            "analysis_method": "fallback",
            "timestamp": datetime.now().isoformat()
        }


class ParallelProcessor:
    """Управление параллельной обработкой страниц"""
    
    def __init__(self, max_concurrent_requests: int = 5, requests_per_minute: int = 80):
        self.max_concurrent_requests = max_concurrent_requests
        self.requests_per_minute = requests_per_minute
        self.semaphore = asyncio.Semaphore(max_concurrent_requests)
        self.request_times = []
        self.logger = get_logger(__name__)
    
    async def _wait_for_rate_limit(self):
        """Ожидание для соблюдения лимитов API"""
        current_time = time.time()
        
        # Удаляем старые записи (старше 1 минуты)
        self.request_times = [t for t in self.request_times if current_time - t < 60]
        
        # Если достигли лимита, ждем
        if len(self.request_times) >= self.requests_per_minute:
            wait_time = 60 - (current_time - self.request_times[0])
            if wait_time > 0:
                self.logger.info(f"Достигнут лимит запросов, ожидание {wait_time:.1f} секунд")
                await asyncio.sleep(wait_time)
        
        # Добавляем небольшую задержку между запросами для бесплатного плана
        if self.requests_per_minute <= 60:  # Бесплатный план
            await asyncio.sleep(1)  # 1 секунда между запросами
        
        self.request_times.append(current_time)
    
    async def process_page_async(self, vision_api: VisionAPI, image_data: bytes, 
                                page_number: int, split_mode: str = "vertical") -> Dict[str, Any]:
        """Асинхронная обработка одной страницы"""
        async with self.semaphore:
            await self._wait_for_rate_limit()
            
            try:
                result = vision_api.extract_tasks_from_page(
                    image_data, page_number, 
                    use_split_analysis=True, 
                    split_mode=split_mode
                )
                
                # Проверяем retry_delay в результате
                if result.get("retry_delay"):
                    retry_delay = result["retry_delay"]
                    self.logger.warning(f"Страница {page_number}: API рекомендует задержку {retry_delay} секунд")
                    await asyncio.sleep(retry_delay)
                
                self.logger.info(f"Страница {page_number} обработана успешно")
                return result
            except Exception as e:
                self.logger.error(f"Ошибка обработки страницы {page_number}: {e}")
                return {
                    "page_number": page_number,
                    "tasks": [],
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
    
    async def process_pages_batch(self, vision_api: VisionAPI, pages_data: List[tuple], 
                                 split_mode: str = "vertical") -> List[Dict[str, Any]]:
        """Обработка пакета страниц"""
        tasks = []
        
        for image_data, page_number in pages_data:
            task = self.process_page_async(vision_api, image_data, page_number, split_mode)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Обрабатываем исключения
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                page_number = pages_data[i][1]
                processed_results.append({
                    "page_number": page_number,
                    "tasks": [],
                    "error": str(result),
                    "timestamp": datetime.now().isoformat()
                })
            else:
                processed_results.append(result)
        
        return processed_results


class TaskExtractor:
    """Основной класс для извлечения задач из PDF"""
    
    def __init__(self, pdf_path: str, provider: VisionProvider = VisionProvider.GEMINI, images_dir: Optional[Path] = None):
        self.pdf_path = pdf_path
        self.file_identifier = FileIdentifier.generate(pdf_path)
        self.pdf_processor = PDFProcessor(pdf_path)
        self.vision_api = VisionAPI(provider, images_dir)
        self.logger = get_logger(__name__)
        
        # Загружаем PDF
        self.pdf_processor.load_pdf()
        
        # Создаем директории для временных файлов
        self.temp_dir = Path("temp") / self.file_identifier
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        if images_dir:
            self.images_dir = Path(images_dir)
            self.images_dir.mkdir(parents=True, exist_ok=True)
    
    def extract_tasks_from_page(self, page_number: int, use_split_analysis: bool = True, 
                               split_mode: str = "vertical") -> Dict[str, Any]:
        """
        Извлекает задачи с конкретной страницы.
        
        Args:
            page_number: Номер страницы
            use_split_analysis: Использовать ли разделение изображения
            split_mode: Режим разделения
            
        Returns:
            Результат анализа страницы
        """
        try:
            self.logger.info(f"Обработка страницы {page_number}")
            
            # Получаем изображение страницы
            image_data = self.pdf_processor.convert_page_to_image(page_number)
            
            if image_data is None:
                self.logger.error(f"Не удалось получить изображение страницы {page_number}")
                return {
                    "page_number": page_number,
                    "tasks": [],
                    "error": "Не удалось получить изображение страницы",
                    "timestamp": datetime.now().isoformat()
                }
            
            # Анализируем страницу
            result = self.vision_api.extract_tasks_from_page(
                image_data, page_number, use_split_analysis, split_mode
            )
            
            # Добавляем информацию о файле
            result["file_identifier"] = self.file_identifier
            result["pdf_path"] = str(self.pdf_path)
            
            # Проверяем ошибки в результате
            if result.get("error"):
                self.logger.error(f"Страница {page_number}: {result['error']}")
            else:
                self.logger.info(f"Страница {page_number} обработана: найдено {len(result.get('tasks', []))} задач")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Ошибка обработки страницы {page_number}: {e}")
            return {
                "page_number": page_number,
                "tasks": [],
                "error": str(e),
                "file_identifier": self.file_identifier,
                "pdf_path": str(self.pdf_path),
                "timestamp": datetime.now().isoformat()
            }
    
    def get_total_pages(self) -> int:
        """Возвращает общее количество страниц в PDF"""
        return self.pdf_processor.get_page_count()
    
    def _calculate_confidence(self, task_data: Dict[str, Any], api_result: Dict[str, Any]) -> float:
        """Вычисляет уверенность в результате анализа"""
        # Простая эвристика для оценки качества результата
        confidence = 0.5  # Базовая уверенность
        
        if api_result.get("tasks"):
            confidence += 0.3
        
        if not api_result.get("error"):
            confidence += 0.2
        
        return min(confidence, 1.0)


class ResultStorage:
    """Хранение результатов обработки"""
    
    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    def save_page_result(self, page_number: int, page_data: Dict[str, Any]) -> None:
        """Сохраняет результат обработки страницы"""
        filename = f"page_{page_number:04d}.json"
        file_path = self.storage_dir / filename
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(page_data, f, ensure_ascii=False, indent=2)
    
    def load_page_result(self, page_number: int) -> Optional[Dict[str, Any]]:
        """Загружает результат обработки страницы"""
        filename = f"page_{page_number:04d}.json"
        file_path = self.storage_dir / filename
        
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    
    def get_processed_pages(self) -> List[int]:
        """Возвращает список обработанных страниц"""
        processed = []
        for file_path in self.storage_dir.glob("page_*.json"):
            try:
                page_num = int(file_path.stem.split('_')[1])
                processed.append(page_num)
            except (ValueError, IndexError):
                continue
        return sorted(processed)
    
    def get_successful_pages(self) -> List[int]:
        """Возвращает список успешно обработанных страниц (без ошибок)"""
        successful = []
        for page_num in self.get_processed_pages():
            result = self.load_page_result(page_num)
            if result and not result.get("error"):
                successful.append(page_num)
        return successful
    
    def get_failed_pages(self) -> List[int]:
        """Возвращает список страниц с ошибками"""
        failed = []
        for page_num in self.get_processed_pages():
            result = self.load_page_result(page_num)
            if result and result.get("error"):
                failed.append(page_num)
        return failed
    
    def is_page_successful(self, page_number: int) -> bool:
        """Проверяет, была ли страница успешно обработана"""
        result = self.load_page_result(page_number)
        return result is not None and not result.get("error")
    
    def load_all_results(self) -> List[Dict[str, Any]]:
        """Загружает все результаты обработки"""
        results = []
        for page_num in self.get_processed_pages():
            result = self.load_page_result(page_num)
            if result:
                results.append(result)
        return results
    
    def clear_storage(self) -> None:
        """Очищает хранилище результатов"""
        for file_path in self.storage_dir.glob("page_*.json"):
            file_path.unlink()


async def process_pages_parallel(extractor: TaskExtractor, parallel_processor: ParallelProcessor, 
                               storage: ResultStorage, start_page: int, end_page: int, 
                               processed_pages: List[int], force: bool, verbose: bool, 
                               batch_size: int, split_mode: str):
    """Параллельная обработка страниц"""
    logger = get_logger(__name__)
    
    # Определяем страницы для обработки
    pages_to_process = []
    for page_num in range(start_page, end_page + 1):
        # Обрабатываем страницу если:
        # 1. Принудительная переобработка (force=True)
        # 2. Страница не была успешно обработана ранее
        # 3. Страница вообще не обрабатывалась
        should_process = force or page_num not in processed_pages
        
        if should_process:
            try:
                image_data = extractor.pdf_processor.convert_page_to_image(page_num)
                if image_data:
                    pages_to_process.append((image_data, page_num))
                    if verbose:
                        logger.info(f"Добавлена страница {page_num} для обработки")
                else:
                    logger.warning(f"Не удалось получить изображение страницы {page_num}")
            except Exception as e:
                logger.error(f"Ошибка получения изображения страницы {page_num}: {e}")
        elif verbose:
            logger.info(f"Страница {page_num} уже успешно обработана, пропускаем")
    
    if not pages_to_process:
        logger.info("Нет страниц для обработки")
        return []
    
    logger.info(f"Начинаем параллельную обработку {len(pages_to_process)} страниц")
    
    # Обрабатываем страницы пакетами
    all_results = []
    for i in range(0, len(pages_to_process), batch_size):
        batch = pages_to_process[i:i + batch_size]
        
        if verbose:
            page_numbers = [page_num for _, page_num in batch]
            logger.info(f"Обрабатываем пакет страниц: {page_numbers}")
        
        batch_results = await parallel_processor.process_pages_batch(
            extractor.vision_api, batch, split_mode
        )
        
        # Сохраняем результаты
        for result in batch_results:
            page_num = result.get("page_number")
            if page_num:
                storage.save_page_result(page_num, result)
        
        all_results.extend(batch_results)
        
        if verbose:
            logger.info(f"Пакет обработан: {len(batch_results)} результатов")
    
    logger.info(f"Параллельная обработка завершена: {len(all_results)} результатов")
    return all_results


def process_pages_sequential(extractor: TaskExtractor, storage: ResultStorage, 
                           start_page: int, end_page: int, processed_pages: List[int], 
                           force: bool, verbose: bool, split_mode: str):
    """Последовательная обработка страниц"""
    logger = get_logger(__name__)
    
    results = []
    for page_num in range(start_page, end_page + 1):
        # Обрабатываем страницу если:
        # 1. Принудительная переобработка (force=True)
        # 2. Страница не была успешно обработана ранее
        # 3. Страница вообще не обрабатывалась
        should_process = force or page_num not in processed_pages
        
        if should_process:
            if verbose:
                logger.info(f"Обработка страницы {page_num}")
            
            result = extractor.extract_tasks_from_page(
                page_num, use_split_analysis=True, split_mode=split_mode
            )
            
            storage.save_page_result(page_num, result)
            results.append(result)
            
            if verbose:
                tasks_count = len(result.get("tasks", []))
                error = result.get("error", "")
                if error:
                    logger.info(f"Страница {page_num} обработана с ошибкой: {error}")
                else:
                    logger.info(f"Страница {page_num} обработана успешно: {tasks_count} задач")
        else:
            if verbose:
                logger.info(f"Страница {page_num} уже успешно обработана, пропускаем")
    
    return results


@click.command()
@click.argument('pdf_file', type=click.Path(exists=True))
@click.argument('output_csv', type=click.Path())
@click.option('--force', is_flag=True, help='Принудительно переобработать все страницы')
@click.option('--start-page', type=int, default=1, help='Начальная страница для обработки')
@click.option('--end-page', type=int, default=None, help='Конечная страница для обработки')
@click.option('--production', is_flag=True, help='Production режим логирования')
@click.option('--verbose', is_flag=True, help='Подробный вывод')
@click.option('--parallel', is_flag=True, help='🧪 ЭКСПЕРИМЕНТАЛЬНО: Включить параллельную обработку (может быть нестабильно)')
@click.option('--max-concurrent', type=int, default=2, help='Максимум одновременных запросов для --parallel (по умолчанию: 2 для бесплатного плана, рекомендуется не более 3)')
@click.option('--batch-size', type=int, default=5, help='Размер пакета для параллельной обработки (по умолчанию: 5)')
@click.option('--provider', type=click.Choice(['openai', 'gemini', 'claude']), default='gemini', help='Провайдер мультимодального API (openai, gemini, claude)')
@click.option('--split-analysis', is_flag=True, default=True, help='🎯 РЕКОМЕНДУЕТСЯ: Разделять изображения на части для лучшего анализа многоколоночных страниц (по умолчанию: включено)')
@click.option('--no-split', is_flag=True, help='Отключить разделение изображений (использовать старый метод анализа целой страницы)')
@click.option('--split-mode', type=click.Choice(['original', 'vertical', 'horizontal', 'grid']), default='vertical', help='🎯 Режим разделения изображения: original (без разделения), vertical (лево/право), horizontal (верх/низ), grid (сетка 2x2)')
def process_textbook_pure_vision_fixed(pdf_file, output_csv, force, start_page, end_page, 
                                      production, verbose, parallel, max_concurrent, batch_size, 
                                      provider, split_analysis, no_split, split_mode):
    """
    Обрабатывает учебник математики используя OpenAI Vision API.
    
    Извлекает математические задачи из PDF файла и сохраняет результаты в CSV.
    """
    # Настройка логирования
    if production:
        setup_production_logger()
    else:
        setup_development_logger()
    
    logger = get_logger(__name__)
    
    # Определяем режим разделения
    if no_split:
        split_mode = "original"
        split_analysis = False
    elif not split_analysis:
        split_mode = "original"
    
    logger.info("=" * 60)
    logger.info("🚀 ЗАПУСК OCR-OCD Pure Vision Fixed")
    logger.info("=" * 60)
    # Определяем провайдер
    provider_enum = VisionProvider(provider)
    
    logger.info(f"📖 PDF файл: {pdf_file}")
    logger.info(f"📊 Выходной CSV: {output_csv}")
    logger.info(f"📄 Страницы: {start_page}-{end_page if end_page else 'конец'}")
    logger.info(f"🤖 Провайдер API: {provider.upper()}")
    logger.info(f"🔧 Режим разделения: {split_mode}")
    logger.info(f"⚡ Параллельная обработка: {'ВКЛ' if parallel else 'ВЫКЛ'}")
    logger.info(f"🔄 Принудительная переобработка: {'ДА' if force else 'НЕТ'}")
    logger.info("=" * 60)
    
    try:
        # Инициализация компонентов
        extractor = TaskExtractor(pdf_file, provider_enum)
        total_pages = extractor.get_total_pages()
        
        if end_page is None:
            end_page = total_pages
        
        logger.info(f"📚 Всего страниц в PDF: {total_pages}")
        logger.info(f"🎯 Страниц для обработки: {end_page - start_page + 1}")
        
        # Создаем хранилище результатов
        file_identifier = FileIdentifier.generate(pdf_file)
        storage_dir = Path("temp") / file_identifier / "results"
        storage = ResultStorage(storage_dir)
        
        # Проверяем уже обработанные страницы
        all_processed_pages = storage.get_processed_pages()
        successful_pages = storage.get_successful_pages()
        failed_pages = storage.get_failed_pages()
        
        if all_processed_pages and not force:
            logger.info(f"📋 Найдено {len(all_processed_pages)} уже обработанных страниц")
            logger.info(f"✅ Успешно обработано: {len(successful_pages)} страниц")
            logger.info(f"❌ С ошибками: {len(failed_pages)} страниц")
            
            # Для повторной обработки используем только успешные страницы
            processed_pages = successful_pages
        else:
            processed_pages = []
        
        # Обрабатываем страницы
        start_time = time.time()
        
        if parallel:
            logger.info("🔄 Запуск параллельной обработки...")
            
            # Создаем параллельный процессор
            parallel_processor = ParallelProcessor(
                max_concurrent_requests=max_concurrent,
                requests_per_minute=60  # Оптимизировано для бесплатного плана Gemini
            )
            
            # Запускаем асинхронную обработку
            results = asyncio.run(process_pages_parallel(
                extractor, parallel_processor, storage,
                start_page, end_page, processed_pages,
                force, verbose, batch_size, split_mode
            ))
        else:
            logger.info("🔄 Запуск последовательной обработки...")
            results = process_pages_sequential(
                extractor, storage, start_page, end_page,
                processed_pages, force, verbose, split_mode
            )
        
        # Загружаем все результаты
        all_results = storage.load_all_results()
        
        # Создаем CSV файл (только успешные результаты)
        create_pure_vision_fixed_csv(successful_results, output_csv)
        
        # Статистика
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Фильтруем результаты: исключаем страницы с ошибками из CSV
        successful_results = [r for r in all_results if not r.get("error")]
        failed_results = [r for r in all_results if r.get("error")]
        
        total_tasks = sum(len(result.get("tasks", [])) for result in successful_results)
        successful_pages = len(successful_results)
        failed_pages = len(failed_results)
        
        logger.info("=" * 60)
        logger.info("✅ ОБРАБОТКА ЗАВЕРШЕНА")
        logger.info("=" * 60)
        logger.info(f"⏱️  Время обработки: {processing_time:.1f} секунд")
        logger.info(f"📄 Всего страниц: {len(all_results)}")
        logger.info(f"✅ Успешных страниц (в CSV): {successful_pages}")
        logger.info(f"❌ Страниц с ошибками (исключены): {failed_pages}")
        logger.info(f"📝 Всего задач в CSV: {total_tasks}")
        logger.info(f"📊 Результат сохранен в: {output_csv}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        sys.exit(1)


def create_pure_vision_fixed_csv(results: List[Dict], output_path: str) -> None:
    """
    Создает CSV файл с результатами обработки.
    Страницы с ошибками исключаются из CSV и только логируются.
    
    Args:
        results: Список результатов обработки страниц
        output_path: Путь к выходному CSV файлу
    """
    import csv
    
    # Подготавливаем данные для CSV (результаты уже отфильтрованы)
    csv_data = []
    
    for page_result in results:
        page_number = page_result.get("page_number", "unknown")
        tasks = page_result.get("tasks", [])
        
        if not tasks:
            # Если задач нет, добавляем пустую строку
            csv_data.append({
                "page_number": page_number,
                "task_number": "",
                "task_text": "",
                "task_type": "",
                "difficulty": "",
                "part": "",
                "analysis_method": page_result.get("analysis_method", ""),
                "error": ""
            })
        else:
            # Добавляем каждую задачу
            for task in tasks:
                csv_data.append({
                    "page_number": page_number,
                    "task_number": task.get("number", ""),
                    "task_text": task.get("text", ""),
                    "task_type": task.get("type", ""),
                    "difficulty": task.get("difficulty", ""),
                    "part": task.get("part", ""),
                    "analysis_method": page_result.get("analysis_method", ""),
                    "error": ""
                })
    
    # Записываем CSV файл
    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = [
            "page_number", "task_number", "task_text", "task_type", 
            "difficulty", "part", "analysis_method", "error"
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        writer.writerows(csv_data)


if __name__ == "__main__":
    process_textbook_pure_vision_fixed() 