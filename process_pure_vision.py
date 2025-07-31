#!/usr/bin/env python3
"""
OCR-OCD Pure Vision: Только GPT-4 Vision
=========================================

Простая и эффективная система:
- 📖 PDF → изображения страниц
- 🖼️ GPT-4 Vision → анализ и извлечение задач
- 📊 CSV → структурированные результаты

Без сложностей с внешними OCR системами!
"""

import sys
import json
import time
import click
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

# Добавляем src в Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.utils.logger import setup_development_logger, setup_production_logger, get_logger
from src.core.pdf_processor import PDFProcessor
from src.core.vision_client import VisionClient
from src.core.data_extractor import DataExtractor
from src.utils.config import load_config


class PureVisionExtractor:
    """Чистая система: только GPT-4 Vision для анализа изображений."""
    
    def __init__(self, pdf_path: str, config_path: str = None):
        """
        Инициализация Pure Vision экстрактора.
        
        Args:
            pdf_path: Путь к PDF файлу
            config_path: Путь к конфигурационному файлу
        """
        self.logger = get_logger(__name__)
        
        # Загружаем конфигурацию
        self.config = load_config(config_path)
        
        # Инициализируем компоненты
        self.pdf_processor = PDFProcessor(pdf_path)
        self.vision_client = VisionClient(self.config.api)
        self.data_extractor = DataExtractor()
        
        # Загружаем PDF
        self.pdf_processor.load_pdf()
        
        self.logger.info(f"Pure Vision extractor initialized: {pdf_path}")
        
        # Проверяем доступность API
        try:
            api_available = self.vision_client.test_api_connection()
            self.logger.info(f"GPT-4 Vision API status: {'✅ Available' if api_available else '❌ Unavailable'}")
            self.api_available = api_available
        except Exception as e:
            self.logger.warning(f"GPT-4 Vision API test failed: {e}")
            self.api_available = False
    
    def extract_tasks_from_page(self, page_number: int) -> Dict[str, Any]:
        """
        Извлекает задачи со страницы используя только GPT-4 Vision.
        
        Args:
            page_number: Номер страницы для обработки (1-based)
            
        Returns:
            Словарь с результатами извлечения
        """
        start_time = time.time()
        
        try:
            if not self.api_available:
                return {
                    "page_number": page_number,
                    "tasks": [],
                    "processing_time": time.time() - start_time,
                    "method": "pure_vision_api_unavailable",
                    "error": "GPT-4 Vision API не доступен"
                }
            
            # Получаем изображение страницы
            page_image = self.pdf_processor.get_page_image(page_number - 1)  # 0-based index
            
            if not page_image:
                return {
                    "page_number": page_number,
                    "tasks": [],
                    "processing_time": time.time() - start_time,
                    "method": "pure_vision_no_image",
                    "error": f"Не удалось получить изображение страницы {page_number}"
                }
            
            # Создаём оптимизированный промпт для математических задач
            math_prompt = self._create_math_prompt()
            
            # Анализируем через GPT-4 Vision
            self.logger.debug(f"Analyzing page {page_number} with Pure GPT-4 Vision")
            
            api_result = self.vision_client.extract_tasks_from_page(
                page_image=page_image,
                page_number=page_number,
                custom_prompt=math_prompt
            )
            
            if not api_result.get('success', False):
                return {
                    "page_number": page_number,
                    "tasks": [],
                    "processing_time": time.time() - start_time,
                    "method": "pure_vision_api_failed",
                    "error": f"Vision API failed: {api_result.get('error', 'Unknown error')}"
                }
            
            # Извлекаем задачи из ответа GPT
            tasks = self.data_extractor.extract_tasks_from_response(
                api_result.get('response', {}),
                page_number
            )
            
            # Обогащаем задачи метаданными Pure Vision
            for i, task in enumerate(tasks, 1):
                task.update({
                    'task_number': f"vision-{page_number}-{i}",
                    'extraction_method': 'pure_vision_gpt4',
                    'vision_api_used': True,
                    'api_model': self.config.api.model_name,
                    'processing_confidence': self._calculate_vision_confidence(task, api_result),
                    'pure_vision': True
                })
            
            processing_time = time.time() - start_time
            
            self.logger.debug(f"Pure Vision extracted {len(tasks)} tasks from page {page_number}")
            
            return {
                "page_number": page_number,
                "tasks": tasks,
                "processing_time": processing_time,
                "method": "pure_vision_success",
                "api_model": self.config.api.model_name,
                "image_processed": True,
                "json_valid": api_result.get('json_valid', False),
                "api_response_time": api_result.get('processing_time', 0)
            }
            
        except Exception as e:
            self.logger.error(f"Error extracting tasks from page {page_number}: {e}")
            return {
                "page_number": page_number,
                "tasks": [],
                "processing_time": time.time() - start_time,
                "method": "pure_vision_error",
                "error": str(e)
            }
    
    def _create_math_prompt(self) -> str:
        """Создаёт оптимизированный промпт для математических задач."""
        
        return """Проанализируй эту страницу математического учебника для 1 класса и извлеки ВСЕ математические задачи и упражнения.

🎯 ТВОЯ ЗАДАЧА:
Найди и извлеки каждую математическую задачу, вопрос или упражнение на странице.

📝 ЧТО ИСКАТЬ:
• Вопросы: "Сколько...?", "Где...?", "Что...?", "Как...?"
• Команды: "Покажи...", "Найди...", "Реши...", "Положи...", "Нарисуй..."
• Примеры: математические выражения (2+3, 5-1)
• Сравнения: "больше/меньше", "длиннее/короче"
• Счёт: "посчитай...", "сосчитай..."
• Задачи со словами: текстовые математические задачи

🔍 ИНСТРУКЦИИ:
1. Читай ВСЁ на странице внимательно
2. Каждая отдельная задача = отдельный элемент
3. Включай полный текст задачи
4. Если видишь рисунки/схемы к задаче - отметь has_image: true

📊 ФОРМАТ ОТВЕТА (строго JSON):
{
  "tasks": [
    {
      "task_number": "1",
      "task_text": "полный текст задачи или вопроса",
      "has_image": true/false
    },
    {
      "task_number": "2", 
      "task_text": "следующая задача...",
      "has_image": true/false
    }
  ]
}

✨ ВАЖНО: Даже если задача кажется простой (например, "Сколько яблок?"), всё равно включай её в результат!"""
    
    def _calculate_vision_confidence(self, task: Dict[str, Any], api_result: Dict[str, Any]) -> float:
        """Вычисляет confidence score для Pure Vision."""
        
        confidence = 0.7  # Базовый confidence для Vision API
        
        # Бонус за успешный JSON парсинг
        if api_result.get('json_valid', False):
            confidence += 0.15
        
        # Бонус за математические ключевые слова
        task_text = task.get('task_text', '').lower()
        math_keywords = ['сколько', 'найди', 'реши', 'покажи', 'положи', 'посчитай', '?', '+', '-', '=']
        keyword_count = sum(1 for keyword in math_keywords if keyword in task_text)
        confidence += min(keyword_count * 0.03, 0.15)
        
        # Штраф за очень короткие тексты
        if len(task_text) < 10:
            confidence -= 0.1
        
        return min(max(confidence, 0.0), 1.0)


class PureVisionStorage:
    """Управление промежуточным сохранением для Pure Vision."""
    
    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
    def save_page_result(self, page_number: int, page_data: Dict[str, Any]) -> None:
        """Сохраняет результат Pure Vision обработки страницы."""
        file_path = self.storage_dir / f"pure_vision_page_{page_number:03d}.json"
        
        # Добавляем метаданные Pure Vision
        page_data.update({
            'processed_at': datetime.now().isoformat(),
            'page_number': page_number,
            'storage_version': '4.0-pure-vision',
            'architecture': 'pure_gpt4_vision'
        })
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(page_data, f, ensure_ascii=False, indent=2)
    
    def load_page_result(self, page_number: int) -> Optional[Dict[str, Any]]:
        """Загружает результат Pure Vision обработки страницы."""
        file_path = self.storage_dir / f"pure_vision_page_{page_number:03d}.json"
        
        if not file_path.exists():
            return None
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Ошибка загрузки Pure Vision страницы {page_number}: {e}")
            return None
    
    def get_processed_pages(self) -> List[int]:
        """Возвращает список номеров уже обработанных страниц."""
        processed = []
        
        for file_path in sorted(self.storage_dir.glob("pure_vision_page_*.json")):
            try:
                page_num = int(file_path.stem.split('_')[3])
                processed.append(page_num)
            except (ValueError, IndexError):
                continue
                
        return sorted(processed)
    
    def load_all_results(self) -> List[Dict[str, Any]]:
        """Загружает все сохранённые Pure Vision результаты."""
        results = []
        
        for page_num in self.get_processed_pages():
            page_data = self.load_page_result(page_num)
            if page_data:
                results.append(page_data)
        
        return results
    
    def clear_storage(self) -> None:
        """Очищает все промежуточные файлы Pure Vision."""
        for file_path in self.storage_dir.glob("pure_vision_page_*.json"):
            file_path.unlink()


@click.command()
@click.argument('pdf_file', type=click.Path(exists=True))
@click.argument('output_csv', type=click.Path())
@click.option('--force', is_flag=True, help='Принудительно переобработать все страницы')
@click.option('--start-page', type=int, default=1, help='Начальная страница для обработки')
@click.option('--end-page', type=int, default=None, help='Конечная страница для обработки')
@click.option('--production', is_flag=True, help='Production режим логирования')
@click.option('--verbose', is_flag=True, help='Подробный вывод')
@click.option('--config', type=click.Path(exists=True), help='Путь к конфигурационному файлу')
def process_textbook_pure_vision(pdf_file, output_csv, force, start_page, end_page, production, verbose, config):
    """
    OCR-OCD Pure Vision: Только GPT-4 Vision анализ.
    
    Простая и эффективная система:
    - PDF → изображения страниц → GPT-4 Vision → CSV
    """
    
    print("🚀🖼️ OCR-OCD Pure Vision: GPT-4 Vision Only")
    print("=" * 50)
    print(f"📖 PDF файл: {pdf_file}")
    print(f"📊 Вывод: {output_csv}")
    print(f"🔄 Force режим: {'✅' if force else '❌'}")
    print(f"🎯 Чистый подход: только GPT-4 Vision")
    print(f"✨ Без внешних зависимостей")
    
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
        'storage': Path("temp/processed_pages_pure_vision")
    }
    
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    
    # Инициализация Pure Vision хранилища
    storage = PureVisionStorage(paths['storage'])
    
    if force:
        print("🗑️  Force режим: очистка промежуточных результатов...")
        storage.clear_storage()
    
    start_time = datetime.now()
    
    try:
        # Инициализация Pure Vision экстрактора
        print(f"🖼️ Инициализация Pure Vision экстрактора...")
        extractor = PureVisionExtractor(pdf_file, config)
        
        # Получаем информацию о PDF
        total_pages = extractor.pdf_processor.get_page_count()
        
        if end_page is None:
            end_page = total_pages
        else:
            end_page = min(end_page, total_pages)
        
        print(f"✅ Pure Vision система инициализирована")
        print(f"📚 PDF: {total_pages} страниц")
        print(f"🎯 Обработка: страницы {start_page}-{end_page}")
        print(f"🖼️ GPT-4 Vision API: {'✅ Available' if extractor.api_available else '❌ Unavailable'}")
        
        if not extractor.api_available:
            print("❌ GPT-4 Vision API недоступен! Проверьте API ключ и подключение.")
            return False
        
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
        api_calls = 0
        total_api_time = 0
        
        print(f"\n🚀 Начинаем Pure Vision обработку...")
        
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
                
                # Pure Vision обработка
                if verbose:
                    print(f"  🖼️ Pure Vision анализ...")
                
                result = extractor.extract_tasks_from_page(page_num)
                
                if 'error' in result:
                    error_count += 1
                    print(f"     ❌ Ошибка: {result['error']}")
                    continue
                
                tasks = result['tasks']
                method = result.get('method', 'unknown')
                api_time = result.get('api_response_time', 0)
                json_valid = result.get('json_valid', False)
                
                # Обновляем счётчики
                if result.get('image_processed', False):
                    api_calls += 1
                    total_api_time += api_time
                
                if verbose:
                    print(f"  ✅ Pure Vision анализ завершён")
                    print(f"  🎯 Метод: {method}")
                    print(f"  📊 JSON валидный: {'✅' if json_valid else '❌'}")
                    print(f"  ⏱️ API время: {api_time:.2f}s")
                
                # Сохранение промежуточного результата
                page_result = {
                    'page_number': page_num,
                    'tasks': tasks,
                    'processing_time': result['processing_time'],
                    'method': method,
                    'api_model': result.get('api_model', 'unknown'),
                    'json_valid': json_valid,
                    'api_response_time': api_time,
                    'task_count': len(tasks)
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
                time.sleep(0.5)  # Разумная пауза между запросами
                
            except Exception as e:
                logger.error(f"Error processing page {page_num}: {e}")
                print(f"     ❌ Ошибка на странице {page_num}: {e}")
                error_count += 1
                continue
        
        # Финальный сбор результатов
        print(f"\n💾 Сбор финальных Pure Vision результатов...")
        all_results = storage.load_all_results()
        
        # Создание итогового CSV
        if all_results:
            print(f"📊 Создание Pure Vision CSV файла...")
            create_pure_vision_csv(all_results, output_csv)
        
        # Детальная статистика
        total_time = (datetime.now() - start_time).total_seconds()
        avg_api_time = total_api_time / api_calls if api_calls > 0 else 0
        
        print(f"\n🎉 PURE VISION ОБРАБОТКА ЗАВЕРШЕНА!")
        print(f"=" * 50)
        print(f"📊 Общая статистика:")
        print(f"   📚 Страниц обработано: {processed_count}")
        print(f"   ⏭️  Страниц пропущено: {skipped_count}")
        print(f"   ❌ Ошибок: {error_count}")
        print(f"   📝 Задач извлечено: {total_tasks}")
        print(f"   🔥 API вызовов: {api_calls}")
        print(f"   ⏱️  Общее время: {total_time:.1f}s ({total_time/60:.1f} минут)")
        print(f"   ⚡ Среднее API время: {avg_api_time:.2f}s")
        if processed_count > 0:
            print(f"   📈 Среднее задач/страница: {total_tasks/processed_count:.1f}")
            print(f"   💰 Примерная стоимость: ${api_calls * 0.01:.2f}")
        
        print(f"\n📁 Pure Vision CSV: {output_csv}")
        print(f"🎯 Метод: Только GPT-4 Vision")
        print(f"✨ Чистый подход без внешних зависимостей")
        
        return True
        
    except Exception as e:
        logger.error(f"Critical Pure Vision error: {e}")
        print(f"❌ Критическая ошибка Pure Vision: {e}")
        return False


def create_pure_vision_csv(results: List[Dict], output_path: str) -> None:
    """Создаёт Pure Vision CSV файл из результатов."""
    
    all_tasks = []
    
    for page_result in results:
        page_num = page_result['page_number']
        processing_time = page_result.get('processing_time', 0)
        method = page_result.get('method', 'unknown')
        api_model = page_result.get('api_model', 'unknown')
        json_valid = page_result.get('json_valid', False)
        api_response_time = page_result.get('api_response_time', 0)
        
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
                'extraction_method': task_data.get('extraction_method', 'pure_vision_gpt4'),
                'vision_api_used': task_data.get('vision_api_used', True),
                'pure_vision': task_data.get('pure_vision', True),
                'json_valid': json_valid,
                'api_response_time': api_response_time,
                'extracted_at': page_result.get('processed_at', ''),
                'word_count': len(task_data.get('task_text', '').split()),
                'system_type': 'pure_gpt4_vision',
                'architecture': 'pdf_to_image_to_gpt4_vision'
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
    
    print(f"✅ Pure Vision CSV создан: {len(all_tasks)} задач сохранено")
    print(f"📊 Поля: pure_vision, processing_confidence, api_model, json_valid")


if __name__ == "__main__":
    process_textbook_pure_vision() 