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
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# Добавляем src в Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.core.pdf_processor import PDFProcessor
from src.utils.logger import setup_development_logger, setup_production_logger, get_logger


class DirectVisionAPI:
    """Прямой клиент для GPT-4 Vision API (проверенно рабочий)."""
    
    def __init__(self):
        load_dotenv()
        self.client = openai.OpenAI()
        self.logger = get_logger(__name__)
        
    def extract_tasks_from_page(self, image_data: bytes, page_number: int) -> Dict[str, Any]:
        """Извлекает задачи со страницы используя прямой GPT-4 Vision API."""
        
        # Кодируем изображение
        b64_image = base64.b64encode(image_data).decode('utf-8')
        
        # Оптимизированный промпт для математических задач
        prompt = f"""Проанализируй эту страницу {page_number} математического учебника для 1 класса.

🎯 ЗАДАЧА: Найди ВСЕ математические задачи и упражнения на странице.

📝 ЧТО ИСКАТЬ:
• Вопросы: "Сколько...?", "Где...?", "Что...?"
• Команды: "Покажи...", "Найди...", "Реши...", "Положи..."
• Примеры: числа, выражения (2+3, 5-1)
• Сравнения: "больше/меньше", "длиннее/короче"
• Счёт объектов: "посчитай...", "сосчитай..."

📊 ФОРМАТ ОТВЕТА (строго JSON):
{{
  "page_number": {page_number},
  "tasks": [
    {{
      "task_number": "1",
      "task_text": "полный текст задачи",
      "has_image": true
    }},
    {{
      "task_number": "2", 
      "task_text": "следующая задача",
      "has_image": false
    }}
  ]
}}

✨ ВАЖНО: 
- Если номер не виден, используй "unknown-1", "unknown-2"
- Включай даже простые задачи
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
                "raw_content": content[:200] + "..." if len(content) > 200 else content
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
                "task_text": content[:300] + "..." if len(content) > 300 else content,
                "has_image": False
            })
        
        return {
            "page_number": page_number,
            "tasks": tasks
        }


class PureVisionFixedExtractor:
    """Исправленная Pure Vision система с прямой интеграцией OpenAI."""
    
    def __init__(self, pdf_path: str):
        """
        Инициализация исправленного Pure Vision экстрактора.
        
        Args:
            pdf_path: Путь к PDF файлу
        """
        self.logger = get_logger(__name__)
        
        # Инициализируем компоненты
        self.pdf_processor = PDFProcessor(pdf_path)
        self.vision_api = DirectVisionAPI()
        
        # Загружаем PDF
        self.pdf_processor.load_pdf()
        
        self.logger.info(f"Pure Vision Fixed extractor initialized: {pdf_path}")
    
    def extract_tasks_from_page(self, page_number: int) -> Dict[str, Any]:
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
            
            api_result = self.vision_api.extract_tasks_from_page(page_image, page_number)
            
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
                    'extraction_method': 'pure_vision_fixed_direct',
                    'vision_api_used': True,
                    'api_model': api_result.get('model', 'gpt-4o'),
                    'processing_confidence': self._calculate_confidence(task_data, api_result),
                    'pure_vision_fixed': True
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


@click.command()
@click.argument('pdf_file', type=click.Path(exists=True))
@click.argument('output_csv', type=click.Path())
@click.option('--force', is_flag=True, help='Принудительно переобработать все страницы')
@click.option('--start-page', type=int, default=1, help='Начальная страница для обработки')
@click.option('--end-page', type=int, default=None, help='Конечная страница для обработки')
@click.option('--production', is_flag=True, help='Production режим логирования')
@click.option('--verbose', is_flag=True, help='Подробный вывод')
def process_textbook_pure_vision_fixed(pdf_file, output_csv, force, start_page, end_page, production, verbose):
    """
    OCR-OCD Pure Vision Fixed: Исправленная прямая интеграция GPT-4 Vision.
    
    Исправленная система с рабочим Direct OpenAI API:
    - PDF → изображения страниц → прямой GPT-4 Vision → CSV
    """
    
    print("🚀🔧 OCR-OCD Pure Vision Fixed: Direct OpenAI API")
    print("=" * 55)
    print(f"📖 PDF файл: {pdf_file}")
    print(f"📊 Вывод: {output_csv}")
    print(f"🔄 Force режим: {'✅' if force else '❌'}")
    print(f"🎯 Исправленный подход: прямой OpenAI API")
    print(f"✨ Проверенно рабочий метод")
    
    # Настройка логирования
    if production:
        setup_production_logger()
    else:
        setup_development_logger()
    
    logger = get_logger(__name__)
    
    # Создаём необходимые директории
    paths = {
        'output': Path("output"),
        'temp': Path("temp"), 
        'logs': Path("logs"),
        'storage': Path("temp/processed_pages_pure_vision_fixed")
    }
    
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    
    # Инициализация Pure Vision Fixed хранилища
    storage = PureVisionFixedStorage(paths['storage'])
    
    if force:
        print("🗑️  Force режим: очистка промежуточных результатов...")
        storage.clear_storage()
    
    start_time = datetime.now()
    
    try:
        # Инициализация Pure Vision Fixed экстрактора
        print(f"🔧 Инициализация Pure Vision Fixed экстрактора...")
        extractor = PureVisionFixedExtractor(pdf_file)
        
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
                    print(f"  🔧 Pure Vision Fixed анализ...")
                
                result = extractor.extract_tasks_from_page(page_num)
                
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
        print(f"✨ Проверенно рабочий подход")
        
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
                'processing_confidence': task_data.get('processing_confidence', 0.0),
                'processing_time': processing_time,
                'api_method': method,
                'api_model': api_model,
                'api_tokens': api_tokens,
                'api_time': api_time,
                'extraction_method': task_data.get('extraction_method', 'pure_vision_fixed_direct'),
                'vision_api_used': task_data.get('vision_api_used', True),
                'pure_vision_fixed': task_data.get('pure_vision_fixed', True),
                'json_valid': json_valid,
                'extracted_at': page_result.get('processed_at', ''),
                'word_count': len(task_data.get('task_text', '').split()),
                'system_type': 'pure_gpt4_vision_fixed',
                'architecture': 'pdf_direct_openai_api'
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
    print(f"📊 Поля: pure_vision_fixed, api_tokens, api_time, json_valid")


if __name__ == "__main__":
    process_textbook_pure_vision_fixed() 