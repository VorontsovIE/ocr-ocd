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
from src.utils.logger import setup_development_logger, setup_production_logger, get_logger


def generate_file_identifier(pdf_path: str) -> str:
    """
    Генерирует уникальный идентификатор для PDF файла.
    
    Использует MD5 хеш содержимого файла + basename для создания
    уникального идентификатора, который позволяет избежать 
    конфликтов при обработке разных файлов.
    
    Args:
        pdf_path: Путь к PDF файлу
        
    Returns:
        Уникальный идентификатор в формате "basename_md5hash"
    """
    file_path = Path(pdf_path)
    basename = file_path.stem  # Имя файла без расширения
    
    # Генерируем MD5 хеш содержимого файла
    hash_md5 = hashlib.md5()
    with open(pdf_path, "rb") as f:
        # Читаем файл блоками для эффективности с большими файлами
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    
    file_hash = hash_md5.hexdigest()[:8]  # Берем первые 8 символов хеша
    
    # Очищаем basename от проблемных символов
    clean_basename = "".join(c for c in basename if c.isalnum() or c in "_-")[:20]
    
    return f"{clean_basename}_{file_hash}"


def split_image_for_analysis(image_data: bytes, split_mode: str = "vertical") -> List[bytes]:
    """
    Разделяет изображение на части для лучшего анализа многоколоночных страниц.
    
    Args:
        image_data: Данные изображения
        split_mode: Режим разделения ("vertical", "horizontal", "grid")
        
    Returns:
        Список частей изображения
    """
    try:
        image = Image.open(io.BytesIO(image_data))
        width, height = image.size
        parts = []
        
        if split_mode == "vertical":
            # Разделяем вертикально на 2 части (левая/правая)
            left_part = image.crop((0, 0, width // 2, height))
            right_part = image.crop((width // 2, 0, width, height))
            
            # Конвертируем в bytes
            for part, name in [(left_part, "left"), (right_part, "right")]:
                buffer = io.BytesIO()
                part.save(buffer, format='PNG', quality=95)
                parts.append(buffer.getvalue())
                
        elif split_mode == "horizontal":
            # Разделяем горизонтально на 2 части (верх/низ)
            top_part = image.crop((0, 0, width, height // 2))
            bottom_part = image.crop((0, height // 2, width, height))
            
            for part in [top_part, bottom_part]:
                buffer = io.BytesIO()
                part.save(buffer, format='PNG', quality=95)
                parts.append(buffer.getvalue())
                
        elif split_mode == "grid":
            # Разделяем на 4 части (сетка 2x2)
            half_width, half_height = width // 2, height // 2
            
            grid_parts = [
                image.crop((0, 0, half_width, half_height)),  # top-left
                image.crop((half_width, 0, width, half_height)),  # top-right
                image.crop((0, half_height, half_width, height)),  # bottom-left
                image.crop((half_width, half_height, width, height))  # bottom-right
            ]
            
            for part in grid_parts:
                buffer = io.BytesIO()
                part.save(buffer, format='PNG', quality=95)
                parts.append(buffer.getvalue())
        
        return parts
        
    except Exception as e:
        # В случае ошибки возвращаем оригинальное изображение
        return [image_data]


class DirectVisionAPI:
    """Прямой клиент для GPT-4 Vision API (проверенно рабочий)."""
    
    def __init__(self, images_dir: Optional[Path] = None):
        load_dotenv()
        self.client = openai.OpenAI()
        self.logger = get_logger(__name__)
        self.images_dir = images_dir
        
        # Создаем папки для изображений если указана директория
        if self.images_dir:
            self.images_dir.mkdir(parents=True, exist_ok=True)
            (self.images_dir / "original").mkdir(exist_ok=True)
            (self.images_dir / "enhanced").mkdir(exist_ok=True)
            self.logger.info(f"Images will be saved to: {self.images_dir}")
    
    def _save_image_to_disk(self, image_data: bytes, filename: str, subfolder: str = "") -> Optional[Path]:
        """
        Сохраняет изображение на диск для отладки и анализа.
        
        Args:
            image_data: Данные изображения
            filename: Имя файла
            subfolder: Подпапка (original/enhanced)
            
        Returns:
            Путь к сохраненному файлу или None если не удалось сохранить
        """
        if not self.images_dir:
            return None
            
        try:
            save_path = self.images_dir / subfolder / filename
            with open(save_path, 'wb') as f:
                f.write(image_data)
            
            self.logger.debug(f"Image saved: {save_path} ({len(image_data)} bytes)")
            return save_path
            
        except Exception as e:
            self.logger.warning(f"Failed to save image {filename}: {e}")
            return None
    
    def _enhance_image_for_ocr(self, image_data: bytes) -> bytes:
        """
        Улучшает изображение для лучшего распознавания формул и текста.
        
        Args:
            image_data: Исходные данные изображения
            
        Returns:
            Улучшенные данные изображения
        """
        try:
            # Открываем изображение
            image = Image.open(io.BytesIO(image_data))
            
            # Конвертируем в RGB если нужно
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Увеличиваем разрешение для лучшего качества
            # Увеличиваем в 1.5 раза для баланса качества и размера
            original_size = image.size
            new_size = (int(original_size[0] * 1.5), int(original_size[1] * 1.5))
            image = image.resize(new_size, Image.Resampling.LANCZOS)
            
            # Улучшаем контрастность для лучшего распознавания формул
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.2)  # Повышаем контраст на 20%
            
            # Улучшаем резкость для четкости мелких деталей
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(1.3)  # Повышаем резкость на 30%
            
            # Небольшое увеличение яркости если изображение темное
            enhancer = ImageEnhance.Brightness(image)
            image = enhancer.enhance(1.1)  # Повышаем яркость на 10%
            
            # Применяем легкое сглаживание для уменьшения шума
            image = image.filter(ImageFilter.SMOOTH_MORE)
            
            # Конвертируем обратно в bytes
            output_buffer = io.BytesIO()
            image.save(output_buffer, format='PNG', quality=95, optimize=True)
            enhanced_data = output_buffer.getvalue()
            
            self.logger.debug(f"Image enhanced: {len(image_data)} -> {len(enhanced_data)} bytes, "
                            f"size: {original_size} -> {new_size}")
            
            return enhanced_data
            
        except Exception as e:
            self.logger.warning(f"Image enhancement failed: {e}, using original")
            return image_data
        
    def extract_tasks_from_page(self, image_data: bytes, page_number: int, use_split_analysis: bool = True) -> Dict[str, Any]:
        """
        Извлекает задачи со страницы используя прямой GPT-4 Vision API.
        
        Args:
            image_data: Данные изображения
            page_number: Номер страницы  
            use_split_analysis: Использовать разделение изображения для лучшего анализа
        """
        
        # Сохраняем исходное изображение
        original_filename = f"page_{page_number:03d}_original.png"
        self._save_image_to_disk(image_data, original_filename, "original")
        
        # Улучшаем изображение для лучшего распознавания
        enhanced_image_data = self._enhance_image_for_ocr(image_data)
        
        # Сохраняем обработанное изображение
        enhanced_filename = f"page_{page_number:03d}_enhanced.png"
        enhanced_path = self._save_image_to_disk(enhanced_image_data, enhanced_filename, "enhanced")
        
        # Логируем информацию об изображениях
        self.logger.debug(f"Page {page_number} images: original={len(image_data)} bytes, enhanced={len(enhanced_image_data)} bytes")
        if enhanced_path:
            self.logger.info(f"Page {page_number} images saved to disk: {enhanced_path.parent}")
        
        if use_split_analysis:
            return self._analyze_with_split_method(enhanced_image_data, page_number)
        else:
            return self._analyze_whole_image(enhanced_image_data, page_number)
    
    def _analyze_with_split_method(self, enhanced_image_data: bytes, page_number: int) -> Dict[str, Any]:
        """
        Анализирует страницу с разделением на части для лучшего покрытия.
        """
        self.logger.info(f"Page {page_number}: Using split analysis method")
        
        # Разделяем изображение на части
        image_parts = split_image_for_analysis(enhanced_image_data, "vertical")
        
        all_tasks = []
        combined_processing_time = 0
        combined_tokens = 0
        all_raw_responses = []
        
        # Анализируем каждую часть отдельно
        for part_idx, part_data in enumerate(image_parts):
            part_name = "левая_часть" if part_idx == 0 else "правая_часть"
            
            # Сохраняем части для отладки
            part_filename = f"page_{page_number:03d}_part_{part_idx+1}_{part_name}.png"
            self._save_image_to_disk(part_data, part_filename, "enhanced")
            
            self.logger.debug(f"Page {page_number}: Analyzing {part_name}")
            
            # Анализируем часть
            part_result = self._analyze_image_part(part_data, page_number, part_name, part_idx + 1)
            
            if part_result.get('success', False):
                part_tasks = part_result.get('response', {}).get('tasks', [])
                
                # Обновляем location_on_page для задач из этой части
                for task in part_tasks:
                    task['location_on_page'] = part_name
                    task['analyzed_as_part'] = True
                    task['part_number'] = part_idx + 1
                
                all_tasks.extend(part_tasks)
                combined_processing_time += part_result.get('processing_time', 0)
                combined_tokens += part_result.get('tokens', 0)
                all_raw_responses.append(f"Part {part_idx+1} ({part_name}): {part_result.get('raw_content', '')}")
                
                self.logger.info(f"Page {page_number} {part_name}: Found {len(part_tasks)} tasks")
            else:
                self.logger.warning(f"Page {page_number} {part_name}: Analysis failed - {part_result.get('error', 'Unknown error')}")
        
        return {
            "success": True,
            "response": {
                "page_number": page_number,
                "tasks": all_tasks
            },
            "processing_time": combined_processing_time,
            "json_valid": True,
            "model": "gpt-4o",
            "tokens": combined_tokens,
            "raw_content": "\n\n".join(all_raw_responses),
            "split_analysis_used": True,
            "parts_analyzed": len(image_parts)
        }
    
    def _analyze_image_part(self, part_data: bytes, page_number: int, part_name: str, part_number: int) -> Dict[str, Any]:
        """
        Анализирует отдельную часть изображения.
        """
        b64_image = base64.b64encode(part_data).decode('utf-8')
        
        # Упрощенный промпт для анализа части
        prompt = f"""Проанализируй эту часть страницы {page_number} математического учебника ({part_name}).

🎯 ЗАДАЧА: Найди ВСЕ математические задачи, упражнения и формулы в этой части изображения.

📝 ЧТО ИСКАТЬ:
• Текстовые задачи с вопросами
• Математические примеры и выражения  
• Команды и инструкции
• Геометрические задачи
• Формулы и символы

📊 ФОРМАТ ОТВЕТА (строго JSON):
{{
  "page_number": {page_number},
  "tasks": [
    {{
      "task_number": "1",
      "task_text": "полный текст задачи",
      "has_image": true,
      "task_type": "текстовая_задача|математический_пример|формула|геометрическая_задача",
      "location_on_page": "{part_name}"
    }}
  ]
}}

✨ ТРЕБОВАНИЯ:
- Извлекай ВСЕ найденные задачи
- Пиши ТОЧНЫЙ текст как на изображении
- Для формул используй LaTeX
- Если номер неясен, используй "unknown-1", "unknown-2"
- Отвечай ТОЛЬКО JSON"""

        try:
            start_time = time.time()
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user", 
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_image}"}}
                        ]
                    }
                ],
                max_tokens=1500,
                temperature=0.1
            )
            
            processing_time = time.time() - start_time
            content = response.choices[0].message.content
            
            # Попытка парсинга JSON
            try:
                parsed_data = json.loads(content)
                json_valid = True
            except json.JSONDecodeError:
                # Пытаемся извлечь JSON из текста
                import re
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    try:
                        parsed_data = json.loads(json_match.group())
                        json_valid = True
                    except json.JSONDecodeError:
                        parsed_data = self._create_fallback_structure(content, page_number)
                        json_valid = False
                else:
                    parsed_data = self._create_fallback_structure(content, page_number)
                    json_valid = False
            
            return {
                "success": True,
                "response": parsed_data,
                "processing_time": processing_time,
                "json_valid": json_valid,
                "model": response.model,
                "tokens": response.usage.total_tokens if response.usage else 0,
                "raw_content": content
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "processing_time": 0,
                "page_number": page_number
            }
    
    def _analyze_whole_image(self, enhanced_image_data: bytes, page_number: int) -> Dict[str, Any]:
        """
        Анализирует всё изображение целиком (оригинальный метод).
        """
        # Кодируем улучшенное изображение
        b64_image = base64.b64encode(enhanced_image_data).decode('utf-8')
        
        # Улучшенный промпт для полного анализа страницы
        prompt = f"""Проанализируй ВСЮ эту страницу {page_number} школьного математического учебника.

🎯 КРИТИЧЕСКИ ВАЖНО: 
- Проанализируй ВСЁ изображение полностью
- Если страница разделена на колонки - обязательно проанализируй ВСЕ колонки
- НЕ ПРОПУСКАЙ ничего

🔍 ЗАДАЧА: Найди ВСЕ математические задачи, упражнения и формулы на ВСЕЙ странице.

📝 ЧТО ИСКАТЬ (по всей странице):
• Текстовые задачи: "Сколько...?", "Где...?", "Что...?", "Как...?"
• Команды и инструкции: "Покажи...", "Найди...", "Реши...", "Положи...", "Вычисли...", "Определи..."
• Математические примеры: числа, выражения (2+3, 5-1, 10+5), уравнения
• Математические формулы и символы: +, -, =, >, <, цифры, дроби
• Геометрические задачи: фигуры, измерения, сравнения размеров
• Сравнения: "больше/меньше", "длиннее/короче", "выше/ниже"
• Счёт объектов: "посчитай...", "сосчитай...", "сколько всего..."
• Логические задачи: последовательности, закономерности
• Задачи с картинками: описание изображений для подсчета
* И тому подобное...


📊 ФОРМАТ ОТВЕТА (строго JSON):
{{
  "page_number": {page_number},
  "tasks": [
    {{
      "task_number": "1",
      "task_text": "полный текст задачи или формулы",
      "has_image": true,
      "task_type": "текстовая_задача|математический_пример|формула|геометрическая_задача",
      "location_on_page": "левая_часть|правая_часть|центр|верх|низ"
    }},
    {{
      "task_number": "2", 
      "task_text": "следующая задача",
      "has_image": false,
      "task_type": "математический_пример",
      "location_on_page": "правая_часть"
    }}
  ]
}}

✨ КРИТИЧЕСКИЕ ТРЕБОВАНИЯ: 
- ОБЯЗАТЕЛЬНО просмотри ВСЮ страницу от края до края
- Если видишь несколько колонок - извлеки задачи из ВСЕХ
- Включай ВСЕ математические элементы, даже простейшие
- Для формул используй LaTeX
- Если номер задачи не виден, используй "unknown-1", "unknown-2" и т.д.
- Указывай примерное расположение задачи на странице
- Если в задаче есть картинка - укажи, что она есть
- Следи за тем, чтобы задача целиком была в одной JSON-записи
- Пиши СТРОГО ТОТ ТЕКСТ, который виден на изображении, НЕ добавляй никаких дополнительных комментариев, НЕ переформулируй
- Отвечай ТОЛЬКО JSON, без дополнительного текста"""

        try:
            start_time = time.time()
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user", 
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_image}"}}
                        ]
                    }
                ],
                max_tokens=2000,
                temperature=0.1
            )
            
            processing_time = time.time() - start_time
            content = response.choices[0].message.content
            
            self.logger.info(f"GPT-4 Vision response for page {page_number}: {len(content)} chars")
            
            # Попытка парсинга JSON
            try:
                parsed_data = json.loads(content)
                json_valid = True
                self.logger.debug(f"Valid JSON parsed for page {page_number}")
            except json.JSONDecodeError as e:
                # Если не JSON, пытаемся извлечь JSON из текста
                json_valid = False
                self.logger.warning(f"JSON parse failed for page {page_number}: {e}")
                
                # Ищем JSON блок в ответе
                import re
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    try:
                        parsed_data = json.loads(json_match.group())
                        json_valid = True
                        self.logger.info(f"Extracted JSON from text for page {page_number}")
                    except json.JSONDecodeError:
                        parsed_data = self._create_fallback_structure(content, page_number)
                else:
                    parsed_data = self._create_fallback_structure(content, page_number)
            
            return {
                "success": True,
                "response": parsed_data,
                "processing_time": processing_time,
                "json_valid": json_valid,
                "model": response.model,
                "tokens": response.usage.total_tokens if response.usage else 0,
                "raw_content": content  # Сохраняем полный ответ без обрезания
            }
            
        except Exception as e:
            self.logger.error(f"API error for page {page_number}: {e}")
            return {
                "success": False,
                "error": str(e),
                "processing_time": 0,
                "page_number": page_number
            }
    
    def _create_fallback_structure(self, content: str, page_number: int) -> Dict[str, Any]:
        """Создаёт fallback структуру когда JSON не распарсился."""
        
        # Пытаемся найти задачи в тексте
        lines = content.split('\n')
        tasks = []
        
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if len(line) > 10 and any(keyword in line.lower() for keyword in 
                                     ['сколько', 'найди', 'реши', 'покажи', 'положи', '?', 'задач']):
                tasks.append({
                    "task_number": f"extracted-{i}",
                    "task_text": line,
                    "has_image": True
                })
        
        if not tasks:
            # Если ничего не нашли, берём весь контент как одну задачу
            tasks.append({
                "task_number": "fallback-1",
                "task_text": content[:1000] + "..." if len(content) > 1000 else content,
                "has_image": False
            })
        
        return {
            "page_number": page_number,
            "tasks": tasks
        }


class ParallelProcessingManager:
    """Управляет параллельной обработкой с учетом rate limits OpenAI."""
    
    def __init__(self, max_concurrent_requests: int = 5, requests_per_minute: int = 80):
        """
        Инициализация менеджера параллельной обработки.
        
        Args:
            max_concurrent_requests: Максимум одновременных запросов
            requests_per_minute: Максимум запросов в минуту (оставляем запас от лимита 100)
        """
        self.max_concurrent_requests = max_concurrent_requests
        self.requests_per_minute = requests_per_minute
        self.request_times = []
        self.logger = get_logger(__name__)
        
    async def _wait_for_rate_limit(self):
        """Ожидает если нужно для соблюдения rate limits."""
        current_time = time.time()
        
        # Убираем запросы старше минуты
        self.request_times = [t for t in self.request_times if current_time - t < 60]
        
        # Проверяем, можем ли делать запрос
        if len(self.request_times) >= self.requests_per_minute:
            wait_time = 60 - (current_time - self.request_times[0])
            if wait_time > 0:
                self.logger.info(f"Rate limit: waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
                await self._wait_for_rate_limit()  # Проверяем снова после ожидания
        
        # Записываем время текущего запроса
        self.request_times.append(current_time)
    
    async def process_page_async(self, vision_api: DirectVisionAPI, image_data: bytes, page_number: int) -> Dict[str, Any]:
        """Асинхронная обработка одной страницы."""
        await self._wait_for_rate_limit()
        
        # Запускаем синхронный метод в отдельном потоке
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(
                executor, 
                vision_api.extract_tasks_from_page,
                image_data,
                page_number
            )
        
        return result
    
    async def process_pages_batch(self, vision_api: DirectVisionAPI, pages_data: List[tuple]) -> List[Dict[str, Any]]:
        """
        Обрабатывает пакет страниц параллельно.
        
        Args:
            vision_api: Экземпляр DirectVisionAPI
            pages_data: Список кортежей (image_data, page_number)
            
        Returns:
            Список результатов обработки
        """
        semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        
        async def process_with_semaphore(image_data, page_number):
            async with semaphore:
                return await self.process_page_async(vision_api, image_data, page_number)
        
        # Создаем задачи для всех страниц
        tasks = [
            process_with_semaphore(image_data, page_number)
            for image_data, page_number in pages_data
        ]
        
        # Запускаем все задачи параллельно
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Обрабатываем исключения
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                page_number = pages_data[i][1]
                self.logger.error(f"Error processing page {page_number}: {result}")
                processed_results.append({
                    "page_number": page_number,
                    "success": False,
                    "error": str(result),
                    "processing_time": 0
                })
            else:
                processed_results.append(result)
        
        return processed_results


class PureVisionFixedExtractor:
    """Исправленная Pure Vision система с прямой интеграцией OpenAI."""
    
    def __init__(self, pdf_path: str, images_dir: Optional[Path] = None):
        """
        Инициализация исправленного Pure Vision экстрактора.
        
        Args:
            pdf_path: Путь к PDF файлу
            images_dir: Папка для сохранения изображений (опционально)
        """
        self.logger = get_logger(__name__)
        
        # Инициализируем компоненты
        self.pdf_processor = PDFProcessor(pdf_path)
        self.vision_api = DirectVisionAPI(images_dir)
        
        # Загружаем PDF
        self.pdf_processor.load_pdf()
        
        if images_dir:
            self.logger.info(f"Pure Vision Fixed extractor initialized: {pdf_path}, images will be saved to: {images_dir}")
        else:
            self.logger.info(f"Pure Vision Fixed extractor initialized: {pdf_path}")
    
    def extract_tasks_from_page(self, page_number: int, use_split_analysis: bool = True) -> Dict[str, Any]:
        """
        Извлекает задачи со страницы используя исправленный Pure Vision.
        
        Args:
            page_number: Номер страницы для обработки (1-based)
            
        Returns:
            Словарь с результатами извлечения
        """
        start_time = time.time()
        
        try:
            # Получаем изображение страницы
            page_image = self.pdf_processor.convert_page_to_image(page_number - 1, save_to_file=False)  # 0-based index
            
            if not page_image:
                return {
                    "page_number": page_number,
                    "tasks": [],
                    "processing_time": time.time() - start_time,
                    "method": "pure_vision_fixed_no_image",
                    "error": f"Не удалось получить изображение страницы {page_number}"
                }
            
            # Анализируем через прямой GPT-4 Vision API
            self.logger.debug(f"Analyzing page {page_number} with Direct GPT-4 Vision")
            
            api_result = self.vision_api.extract_tasks_from_page(page_image, page_number, use_split_analysis)
            
            if not api_result.get('success', False):
                return {
                    "page_number": page_number,
                    "tasks": [],
                    "processing_time": time.time() - start_time,
                    "method": "pure_vision_fixed_api_failed",
                    "error": f"Direct Vision API failed: {api_result.get('error', 'Unknown error')}"
                }
            
            # Извлекаем задачи из ответа GPT
            parsed_response = api_result.get('response', {})
            tasks_data = parsed_response.get('tasks', [])
            
            # Преобразуем в наш формат
            tasks = []
            for i, task_data in enumerate(tasks_data, 1):
                task = {
                    'task_number': task_data.get('task_number', f"fixed-{page_number}-{i}"),
                    'task_text': task_data.get('task_text', ''),
                    'has_image': task_data.get('has_image', False),
                    'task_type': task_data.get('task_type', 'unknown'),
                    'location_on_page': task_data.get('location_on_page', 'unknown'),
                    'extraction_method': 'pure_vision_fixed_enhanced',
                    'vision_api_used': True,
                    'api_model': api_result.get('model', 'gpt-4o'),
                    'processing_confidence': self._calculate_confidence(task_data, api_result),
                    'pure_vision_fixed': True,
                    'enhanced_prompt': True
                }
                tasks.append(task)
            
            processing_time = time.time() - start_time
            
            self.logger.debug(f"Pure Vision Fixed extracted {len(tasks)} tasks from page {page_number}")
            
            return {
                "page_number": page_number,
                "tasks": tasks,
                "processing_time": processing_time,
                "method": "pure_vision_fixed_success",
                "api_model": api_result.get('model', 'gpt-4o'),
                "api_tokens": api_result.get('tokens', 0),
                "api_time": api_result.get('processing_time', 0),
                "json_valid": api_result.get('json_valid', False),
                "raw_response": api_result.get('raw_content', '')
            }
            
        except Exception as e:
            self.logger.error(f"Error extracting tasks from page {page_number}: {e}")
            return {
                "page_number": page_number,
                "tasks": [],
                "processing_time": time.time() - start_time,
                "method": "pure_vision_fixed_error",
                "error": str(e)
            }
    
    def _calculate_confidence(self, task_data: Dict[str, Any], api_result: Dict[str, Any]) -> float:
        """Вычисляет confidence score для Pure Vision Fixed."""
        
        confidence = 0.8  # Базовый confidence для Direct API
        
        # Бонус за успешный JSON парсинг
        if api_result.get('json_valid', False):
            confidence += 0.1
        
        # Бонус за математические ключевые слова
        task_text = task_data.get('task_text', '').lower()
        math_keywords = ['сколько', 'найди', 'реши', 'покажи', 'положи', 'посчитай', '?', '+', '-', '=']
        keyword_count = sum(1 for keyword in math_keywords if keyword in task_text)
        confidence += min(keyword_count * 0.02, 0.1)
        
        return min(confidence, 1.0)


class PureVisionFixedStorage:
    """Управление промежуточным сохранением для Pure Vision Fixed."""
    
    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
    def save_page_result(self, page_number: int, page_data: Dict[str, Any]) -> None:
        """Сохраняет результат Pure Vision Fixed обработки страницы."""
        file_path = self.storage_dir / f"pure_vision_fixed_page_{page_number:03d}.json"
        
        # Добавляем метаданные Pure Vision Fixed
        page_data.update({
            'processed_at': datetime.now().isoformat(),
            'page_number': page_number,
            'storage_version': '5.0-pure-vision-fixed',
            'architecture': 'pure_gpt4_vision_direct_api'
        })
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(page_data, f, ensure_ascii=False, indent=2)
    
    def load_page_result(self, page_number: int) -> Optional[Dict[str, Any]]:
        """Загружает результат Pure Vision Fixed обработки страницы."""
        file_path = self.storage_dir / f"pure_vision_fixed_page_{page_number:03d}.json"
        
        if not file_path.exists():
            return None
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Ошибка загрузки Pure Vision Fixed страницы {page_number}: {e}")
            return None
    
    def get_processed_pages(self) -> List[int]:
        """Возвращает список номеров уже обработанных страниц."""
        processed = []
        
        for file_path in sorted(self.storage_dir.glob("pure_vision_fixed_page_*.json")):
            try:
                page_num = int(file_path.stem.split('_')[4])
                processed.append(page_num)
            except (ValueError, IndexError):
                continue
                
        return sorted(processed)
    
    def load_all_results(self) -> List[Dict[str, Any]]:
        """Загружает все сохранённые Pure Vision Fixed результаты."""
        results = []
        
        for page_num in self.get_processed_pages():
            page_data = self.load_page_result(page_num)
            if page_data:
                results.append(page_data)
        
        return results
    
    def clear_storage(self) -> None:
        """Очищает все промежуточные файлы Pure Vision Fixed."""
        for file_path in self.storage_dir.glob("pure_vision_fixed_page_*.json"):
            file_path.unlink()


async def process_pages_parallel(extractor, parallel_manager, storage, start_page, end_page, 
                                processed_pages, force, verbose, batch_size):
    """
    Обрабатывает страницы параллельно пакетами.
    
    Returns:
        Tuple: (processed_count, skipped_count, error_count, total_tasks, total_tokens, total_api_time)
    """
    processed_count = 0
    skipped_count = 0
    error_count = 0
    total_tasks = 0
    total_tokens = 0
    total_api_time = 0
    
    # Собираем страницы для обработки
    pages_to_process = []
    for page_num in range(start_page, end_page + 1):
        if not force and page_num in processed_pages:
            skipped_count += 1
            if verbose:
                print(f"⏭️  Страница {page_num}: пропущена (уже обработана)")
            continue
        pages_to_process.append(page_num)
    
    print(f"📦 Подготовлено к обработке: {len(pages_to_process)} страниц")
    
    # Обрабатываем пакетами
    for i in range(0, len(pages_to_process), batch_size):
        batch_pages = pages_to_process[i:i + batch_size]
        batch_start = i + 1
        batch_end = min(i + batch_size, len(pages_to_process))
        
        print(f"\n🔄 Пакет {batch_start}-{batch_end} из {len(pages_to_process)} страниц...")
        
        # Подготавливаем данные изображений для пакета
        batch_data = []
        for page_num in batch_pages:
            try:
                # Получаем изображение страницы
                page_image = extractor.pdf_processor.convert_page_to_image(page_num - 1, save_to_file=False)
                if page_image:
                    batch_data.append((page_image, page_num))
                else:
                    error_count += 1
                    print(f"     ❌ Не удалось получить изображение страницы {page_num}")
            except Exception as e:
                error_count += 1
                print(f"     ❌ Ошибка получения изображения страницы {page_num}: {e}")
        
        if not batch_data:
            print("     ⚠️  Нет изображений для обработки в пакете")
            continue
        
        # Параллельная обработка пакета
        batch_start_time = time.time()
        try:
            batch_results = await parallel_manager.process_pages_batch(
                extractor.vision_api, batch_data
            )
            batch_time = time.time() - batch_start_time
            
            # Обрабатываем результаты пакета
            for result in batch_results:
                page_num = result.get('page_number', 0)
                
                if not result.get('success', False):
                    error_count += 1
                    print(f"     ❌ Ошибка API для страницы {page_num}: {result.get('error', 'Unknown')}")
                    continue
                
                # Извлекаем задачи из ответа GPT
                parsed_response = result.get('response', {})
                tasks_data = parsed_response.get('tasks', [])
                
                # Преобразуем в наш формат
                tasks = []
                for j, task_data in enumerate(tasks_data, 1):
                    task = {
                        'task_number': task_data.get('task_number', f"parallel-{page_num}-{j}"),
                        'task_text': task_data.get('task_text', ''),
                        'has_image': task_data.get('has_image', False),
                        'task_type': task_data.get('task_type', 'unknown'),
                        'location_on_page': task_data.get('location_on_page', 'unknown'),
                        'extraction_method': 'pure_vision_fixed_parallel',
                        'vision_api_used': True,
                        'api_model': result.get('model', 'gpt-4o'),
                        'processing_confidence': extractor._calculate_confidence(task_data, result),
                        'pure_vision_fixed': True,
                        'enhanced_prompt': True,
                        'parallel_processed': True
                    }
                    tasks.append(task)
                
                # Сохранение результата
                api_time = result.get('processing_time', 0)
                api_tokens = result.get('tokens', 0)
                json_valid = result.get('json_valid', False)
                
                page_result = {
                    'page_number': page_num,
                    'tasks': tasks,
                    'processing_time': api_time,
                    'method': 'pure_vision_fixed_parallel_success',
                    'api_model': result.get('model', 'gpt-4o'),
                    'api_tokens': api_tokens,
                    'api_time': api_time,
                    'json_valid': json_valid,
                    'task_count': len(tasks),
                    'raw_response': result.get('raw_content', ''),
                    'batch_processed': True
                }
                
                storage.save_page_result(page_num, page_result)
                
                # Обновляем счетчики
                processed_count += 1
                total_tasks += len(tasks)
                total_tokens += api_tokens
                total_api_time += api_time
                
                if verbose:
                    confidence_avg = sum(t.get('processing_confidence', 0) for t in tasks) / len(tasks) if tasks else 0
                    print(f"     ✅ Страница {page_num}: {len(tasks)} задач, JSON={'✅' if json_valid else '❌'}, conf={confidence_avg:.2f}")
            
            print(f"     🔄 Пакет обработан за {batch_time:.1f}s: {len(batch_results)} страниц")
            
        except Exception as e:
            print(f"     ❌ Ошибка пакетной обработки: {e}")
            error_count += len(batch_data)
    
    return processed_count, skipped_count, error_count, total_tasks, total_tokens, total_api_time


@click.command()
@click.argument('pdf_file', type=click.Path(exists=True))
@click.argument('output_csv', type=click.Path())
@click.option('--force', is_flag=True, help='Принудительно переобработать все страницы')
@click.option('--start-page', type=int, default=1, help='Начальная страница для обработки')
@click.option('--end-page', type=int, default=None, help='Конечная страница для обработки')
@click.option('--production', is_flag=True, help='Production режим логирования')
@click.option('--verbose', is_flag=True, help='Подробный вывод')
@click.option('--parallel', is_flag=True, help='🧪 ЭКСПЕРИМЕНТАЛЬНО: Включить параллельную обработку (может быть нестабильно)')
@click.option('--max-concurrent', type=int, default=3, help='Максимум одновременных запросов для --parallel (по умолчанию: 3, рекомендуется не более 5)')
@click.option('--batch-size', type=int, default=5, help='Размер пакета для параллельной обработки (по умолчанию: 5)')
@click.option('--split-analysis', is_flag=True, default=True, help='🎯 РЕКОМЕНДУЕТСЯ: Разделять изображения на части для лучшего анализа многоколоночных страниц (по умолчанию: включено)')
@click.option('--no-split', is_flag=True, help='Отключить разделение изображений (использовать старый метод анализа целой страницы)')
def process_textbook_pure_vision_fixed(pdf_file, output_csv, force, start_page, end_page, production, verbose, parallel, max_concurrent, batch_size, split_analysis, no_split):
    """
    OCR-OCD Pure Vision Fixed: Исправленная прямая интеграция GPT-4 Vision.
    
    Исправленная система с рабочим Direct OpenAI API:
    - PDF → изображения страниц → прямой GPT-4 Vision → CSV
    """
    
    # Определяем использовать ли split analysis
    use_split_analysis = split_analysis and not no_split
    
    print("🚀🔧 OCR-OCD Pure Vision Fixed: Enhanced Direct OpenAI API")
    print("=" * 65)
    print(f"📖 PDF файл: {pdf_file}")
    print(f"📊 Вывод: {output_csv}")
    print(f"🔄 Force режим: {'✅' if force else '❌'}")
    if parallel:
        print(f"⚡ Режим обработки: 🧪 ПАРАЛЛЕЛЬНЫЙ (экспериментальный)")
        print(f"🔄 Одновременных запросов: {max_concurrent}")
        print(f"📦 Размер пакета: {batch_size}")
        print(f"⚠️  ВНИМАНИЕ: Параллельный режим может быть нестабилен!")
    else:
        print(f"⚡ Режим обработки: 📌 ПОСЛЕДОВАТЕЛЬНЫЙ (рекомендуется)")
        print(f"💡 Для экспериментального параллелизма добавьте --parallel")
    print(f"🎯 Анализ изображений: {'🔄 SPLIT-режим (части)' if use_split_analysis else '📄 ЦЕЛАЯ страница'}")
    if use_split_analysis:
        print(f"   ✨ Разделение на части для лучшего анализа многоколоночных страниц")
    print(f"🎯 Улучшенный подход: прямой OpenAI API + предобработка изображений")
    print(f"✨ Полный анализ страниц + формулы")
    
    # Настройка логирования
    if production:
        setup_production_logger()
    else:
        setup_development_logger()
    
    logger = get_logger(__name__)
    
    # Генерируем уникальный идентификатор для входного файла
    print(f"🔍 Генерация уникального идентификатора файла...")
    file_identifier = generate_file_identifier(pdf_file)
    print(f"📁 Идентификатор файла: {file_identifier}")
    
    # Создаём необходимые директории
    paths = {
        'output': Path("output"),
        'temp': Path("temp"), 
        'logs': Path("logs"),
        'storage': Path(f"temp/processed_pages_pure_vision_fixed_{file_identifier}"),
        'images': Path(f"temp/images_pure_vision_fixed_{file_identifier}")
    }
    
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    
    print(f"📂 Промежуточные результаты: {paths['storage']}")
    print(f"🖼️  Изображения сохраняются в: {paths['images']}")
    
    # Инициализация Pure Vision Fixed хранилища
    storage = PureVisionFixedStorage(paths['storage'])
    
    if force:
        print("🗑️  Force режим: очистка промежуточных результатов...")
        storage.clear_storage()
        # Также очищаем папку с изображениями
        if paths['images'].exists():
            import shutil
            shutil.rmtree(paths['images'])
            paths['images'].mkdir(parents=True, exist_ok=True)
    
    start_time = datetime.now()
    
    try:
        # Инициализация Pure Vision Fixed экстрактора
        print(f"🔧 Инициализация Pure Vision Fixed экстрактора...")
        extractor = PureVisionFixedExtractor(pdf_file, images_dir=paths['images'])
        
        # Получаем информацию о PDF
        total_pages = extractor.pdf_processor.get_page_count()
        
        if end_page is None:
            end_page = total_pages
        else:
            end_page = min(end_page, total_pages)
        
        print(f"✅ Pure Vision Fixed система инициализирована")
        print(f"📚 PDF: {total_pages} страниц")
        print(f"🎯 Обработка: страницы {start_page}-{end_page}")
        print(f"🔧 Прямой OpenAI API: готов к работе")
        
        # Проверяем уже обработанные страницы
        processed_pages = set(storage.get_processed_pages())
        
        if processed_pages and not force:
            print(f"📋 Найдено {len(processed_pages)} уже обработанных страниц")
            print(f"📊 Последняя: {max(processed_pages) if processed_pages else 'none'}")
        
        # Счётчики
        processed_count = 0
        skipped_count = 0 
        error_count = 0
        total_tasks = 0
        total_tokens = 0
        total_api_time = 0
        
        print(f"\n🚀 Начинаем Pure Vision Fixed обработку...")
        
        # Инициализация менеджера параллельной обработки если нужно
        if parallel:
            parallel_manager = ParallelProcessingManager(
                max_concurrent_requests=max_concurrent,
                requests_per_minute=80  # Оставляем запас от лимита OpenAI
            )
            print(f"⚡ Параллельная обработка включена: {max_concurrent} одновременных запросов")
            
            # Запускаем параллельную обработку
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                processed_count, skipped_count, error_count, total_tasks, total_tokens, total_api_time = loop.run_until_complete(
                    process_pages_parallel(
                        extractor, parallel_manager, storage, 
                        start_page, end_page, processed_pages, force, verbose, batch_size
                    )
                )
            finally:
                loop.close()
        else:
            # Последовательная обработка (оригинальный код)
            for page_num in range(start_page, end_page + 1):
                page_start_time = time.time()
                
                # Проверяем, нужно ли обрабатывать страницу
                if not force and page_num in processed_pages:
                    skipped_count += 1
                    if verbose:
                        print(f"⏭️  Страница {page_num}: пропущена (уже обработана)")
                    continue
                
                try:
                    progress = (page_num - start_page + 1) / (end_page - start_page + 1) * 100
                    print(f"\n📖 Страница {page_num}/{end_page} ({progress:.1f}%)")
                    
                    # Pure Vision Fixed обработка
                    if verbose:
                        analysis_mode = "split-анализ" if use_split_analysis else "целая страница"
                        print(f"  🔧 Pure Vision Fixed анализ ({analysis_mode})...")
                    
                    result = extractor.extract_tasks_from_page(page_num, use_split_analysis)
                    
                    if 'error' in result:
                        error_count += 1
                        print(f"     ❌ Ошибка: {result['error']}")
                        continue
                    
                    tasks = result['tasks']
                    method = result.get('method', 'unknown')
                    api_time = result.get('api_time', 0)
                    api_tokens = result.get('api_tokens', 0)
                    json_valid = result.get('json_valid', False)
                    
                    # Обновляем счётчики
                    total_tokens += api_tokens
                    total_api_time += api_time
                    
                    if verbose:
                        print(f"  ✅ Pure Vision Fixed анализ завершён")
                        print(f"  🎯 Метод: {method}")
                        print(f"  📊 JSON валидный: {'✅' if json_valid else '❌'}")
                        print(f"  🔤 Tokens: {api_tokens}")
                        print(f"  ⏱️ API время: {api_time:.2f}s")
                    
                    # Сохранение промежуточного результата
                    page_result = {
                        'page_number': page_num,
                        'tasks': tasks,
                        'processing_time': result['processing_time'],
                        'method': method,
                        'api_model': result.get('api_model', 'gpt-4o'),
                        'api_tokens': api_tokens,
                        'api_time': api_time,
                        'json_valid': json_valid,
                        'task_count': len(tasks),
                        'raw_response': result.get('raw_response', '')
                    }
                    
                    storage.save_page_result(page_num, page_result)
                    
                    processed_count += 1
                    total_tasks += len(tasks)
                    
                    processing_time = time.time() - page_start_time
                    print(f"     ✅ Задач: {len(tasks)}, Время: {processing_time:.2f}s")
                    
                    if verbose and tasks:
                        for i, task in enumerate(tasks[:3], 1):  # Показываем первые 3
                            confidence = task.get('processing_confidence', 0)
                            print(f"       {i}. [conf:{confidence:.2f}] {task['task_number']}: {task['task_text'][:50]}...")
                    
                    # Пауза для API
                    time.sleep(1.0)  # Разумная пауза между запросами
                    
                except Exception as e:
                    logger.error(f"Error processing page {page_num}: {e}")
                    print(f"     ❌ Ошибка на странице {page_num}: {e}")
                    error_count += 1
                    continue
        
        # Финальный сбор результатов
        print(f"\n💾 Сбор финальных Pure Vision Fixed результатов...")
        all_results = storage.load_all_results()
        
        # Создание итогового CSV
        if all_results:
            print(f"📊 Создание Pure Vision Fixed CSV файла...")
            create_pure_vision_fixed_csv(all_results, output_csv)
        
        # Детальная статистика
        total_time = (datetime.now() - start_time).total_seconds()
        avg_api_time = total_api_time / processed_count if processed_count > 0 else 0
        estimated_cost = total_tokens * 0.00001  # Примерная стоимость
        
        print(f"\n🎉 PURE VISION FIXED ОБРАБОТКА ЗАВЕРШЕНА!")
        print(f"=" * 55)
        print(f"📊 Общая статистика:")
        print(f"   📚 Страниц обработано: {processed_count}")
        print(f"   ⏭️  Страниц пропущено: {skipped_count}")
        print(f"   ❌ Ошибок: {error_count}")
        print(f"   📝 Задач извлечено: {total_tasks}")
        print(f"   🔤 Всего tokens: {total_tokens}")
        print(f"   ⏱️  Общее время: {total_time:.1f}s ({total_time/60:.1f} минут)")
        print(f"   ⚡ Среднее API время: {avg_api_time:.2f}s")
        print(f"   💰 Примерная стоимость: ${estimated_cost:.4f}")
        if processed_count > 0:
            print(f"   📈 Среднее задач/страница: {total_tasks/processed_count:.1f}")
            print(f"   🏃 Скорость: {processed_count/total_time*60:.1f} страниц/час")
        
        print(f"\n📁 Pure Vision Fixed CSV: {output_csv}")
        print(f"🎯 Метод: Прямая интеграция OpenAI API")
        print(f"⚡ Режим: {'Параллельный (экспериментальный)' if parallel else 'Последовательный (стабильный)'}")
        print(f"✨ Файл-специфичное кеширование: {file_identifier}")
        
        return True
        
    except Exception as e:
        logger.error(f"Critical Pure Vision Fixed error: {e}")
        print(f"❌ Критическая ошибка Pure Vision Fixed: {e}")
        return False


def create_pure_vision_fixed_csv(results: List[Dict], output_path: str) -> None:
    """Создаёт Pure Vision Fixed CSV файл из результатов."""
    
    all_tasks = []
    
    for page_result in results:
        page_num = page_result['page_number']
        processing_time = page_result.get('processing_time', 0)
        method = page_result.get('method', 'unknown')
        api_model = page_result.get('api_model', 'gpt-4o')
        api_tokens = page_result.get('api_tokens', 0)
        api_time = page_result.get('api_time', 0)
        json_valid = page_result.get('json_valid', False)
        
        for task_data in page_result.get('tasks', []):
            task_row = {
                'page_number': page_num,
                'task_number': task_data.get('task_number', 'unknown'),
                'task_text': task_data.get('task_text', ''),
                'has_image': task_data.get('has_image', False),
                'task_type': task_data.get('task_type', 'unknown'),
                'location_on_page': task_data.get('location_on_page', 'unknown'),
                'processing_confidence': task_data.get('processing_confidence', 0.0),
                'processing_time': processing_time,
                'api_method': method,
                'api_model': api_model,
                'api_tokens': api_tokens,
                'api_time': api_time,
                'extraction_method': task_data.get('extraction_method', 'pure_vision_fixed_direct'),
                'vision_api_used': task_data.get('vision_api_used', True),
                'pure_vision_fixed': task_data.get('pure_vision_fixed', True),
                'enhanced_prompt': task_data.get('enhanced_prompt', True),
                'parallel_processed': task_data.get('parallel_processed', False),
                'batch_processed': page_result.get('batch_processed', False),
                'json_valid': json_valid,
                'extracted_at': page_result.get('processed_at', ''),
                'word_count': len(task_data.get('task_text', '').split()),
                'system_type': 'pure_gpt4_vision_fixed_enhanced',
                'architecture': 'pdf_direct_openai_api_enhanced'
            }
            all_tasks.append(task_row)
    
    # Сортируем по номеру страницы и уверенности
    all_tasks.sort(key=lambda x: (x['page_number'], -x['processing_confidence']))
    
    # Записываем CSV
    import csv
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        if all_tasks:
            fieldnames = list(all_tasks[0].keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_tasks)
    
    print(f"✅ Pure Vision Fixed CSV создан: {len(all_tasks)} задач сохранено")
    print(f"📊 Новые поля: task_type, location_on_page, enhanced_prompt, parallel_processed")
    print(f"🔧 Улучшения: предобработка изображений, полный анализ страниц, поддержка параллелизма")


if __name__ == "__main__":
    process_textbook_pure_vision_fixed() 