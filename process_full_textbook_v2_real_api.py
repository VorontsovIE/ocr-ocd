#!/usr/bin/env python3
"""
OCR-OCD v2 с реальным GPT-4 Vision API
=====================================

Версия с прямой интеграцией OpenAI API, обходящая проблемы VisionClient
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
from src.core.data_extractor import DataExtractor
from src.core.csv_writer import CSVWriter
from src.utils.logger import setup_development_logger, setup_production_logger, get_logger
from src.utils.state_manager import StateManager


class SimpleVisionAPI:
    """Простой клиент для GPT-4 Vision API."""
    
    def __init__(self):
        load_dotenv()
        self.client = openai.OpenAI()
        
    def extract_tasks_from_page(self, image_data: bytes, page_number: int) -> Dict[str, Any]:
        """Извлекает задачи со страницы используя GPT-4 Vision."""
        
        # Кодируем изображение
        b64_image = base64.b64encode(image_data).decode('utf-8')
        
        # Простой промпт
        prompt = f"""Посмотри на эту страницу {page_number} из учебника математики для 1 класса.

Найди все математические задачи и упражнения на этой странице.
Для каждой задачи верни информацию в JSON формате:

{{
  "page_number": {page_number},
  "tasks": [
    {{
      "task_number": "1",
      "task_text": "текст задачи",
      "has_image": true
    }}
  ]
}}

Если номер задачи не видно, используй "unknown-1", "unknown-2" и т.д.
Ответь ТОЛЬКО JSON, без дополнительного текста."""

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
            
            # Попытка парсинга JSON
            try:
                parsed_data = json.loads(content)
                json_valid = True
            except json.JSONDecodeError:
                # Если не JSON, создаём структуру вручную
                json_valid = False
                parsed_data = {
                    "page_number": page_number,
                    "tasks": [
                        {
                            "task_number": "unknown-1",
                            "task_text": content[:200] + "..." if len(content) > 200 else content,
                            "has_image": False
                        }
                    ]
                }
            
            return {
                "content": content,
                "parsed_data": parsed_data,
                "json_valid": json_valid,
                "usage": response.usage.model_dump() if response.usage else {},
                "model": response.model,
                "processing_time": processing_time,
                "image_info": {"size_bytes": len(image_data)},
                "prompt_type": "real_api"
            }
            
        except Exception as e:
            print(f"❌ API ошибка на странице {page_number}: {e}")
            # Возвращаем пустой результат
            return {
                "content": f"Ошибка API: {e}",
                "parsed_data": {"page_number": page_number, "tasks": []},
                "json_valid": False,
                "usage": {},
                "model": "error",
                "processing_time": 0,
                "image_info": {"size_bytes": len(image_data)},
                "prompt_type": "error"
            }


class IntermediateStorage:
    """Управление промежуточным сохранением результатов."""
    
    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
    def save_page_result(self, page_number: int, page_data: Dict[str, Any]) -> None:
        """Сохраняет результат обработки страницы."""
        file_path = self.storage_dir / f"page_{page_number:03d}.json"
        
        # Добавляем метаданные
        page_data.update({
            'processed_at': datetime.now().isoformat(),
            'page_number': page_number,
            'storage_version': '2.1'
        })
        
        # Конвертируем datetime объекты в строки
        page_data = self._serialize_datetime(page_data)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(page_data, f, ensure_ascii=False, indent=2)
    
    def load_page_result(self, page_number: int) -> Optional[Dict[str, Any]]:
        """Загружает результат обработки страницы."""
        file_path = self.storage_dir / f"page_{page_number:03d}.json"
        
        if not file_path.exists():
            return None
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Ошибка загрузки страницы {page_number}: {e}")
            return None
    
    def get_processed_pages(self) -> List[int]:
        """Возвращает список номеров уже обработанных страниц."""
        processed = []
        
        for file_path in sorted(self.storage_dir.glob("page_*.json")):
            try:
                page_num = int(file_path.stem.split('_')[1])
                processed.append(page_num)
            except (ValueError, IndexError):
                continue
                
        return sorted(processed)
    
    def load_all_results(self) -> List[Dict[str, Any]]:
        """Загружает все сохранённые результаты."""
        results = []
        
        for page_num in self.get_processed_pages():
            page_data = self.load_page_result(page_num)
            if page_data:
                results.append(page_data)
        
        return results
    
    def clear_storage(self) -> None:
        """Очищает все промежуточные файлы."""
        for file_path in self.storage_dir.glob("page_*.json"):
            file_path.unlink()
    
    def _serialize_datetime(self, obj):
        """Рекурсивно преобразует datetime объекты в строки."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {key: self._serialize_datetime(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._serialize_datetime(item) for item in obj]
        else:
            return obj


@click.command()
@click.argument('pdf_path', type=click.Path(exists=True))
@click.argument('output_csv', type=click.Path())
@click.option('--force', is_flag=True, help='Принудительно переобработать все страницы')
@click.option('--start-page', type=int, default=1, help='Начальная страница для обработки')
@click.option('--end-page', type=int, default=None, help='Конечная страница для обработки')
@click.option('--production', is_flag=True, help='Production режим логирования')
@click.option('--verbose', is_flag=True, help='Подробный вывод')
def process_textbook_real_api(pdf_path, output_csv, force, start_page, end_page, production, verbose):
    """
    OCR-OCD v2 с реальным GPT-4 Vision API.
    """
    
    print("🚀📚 OCR-OCD v2: Реальный GPT-4 Vision API")
    print("=" * 50)
    print(f"📄 PDF: {pdf_path}")
    print(f"📊 Вывод: {output_csv}")
    print(f"🔄 Force режим: {'✅' if force else '❌'}")
    print(f"🤖 Реальный GPT-4 Vision API: ✅")
    
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
        'storage': Path("temp/processed_pages_real_api")
    }
    
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    
    # Инициализация промежуточного хранилища
    storage = IntermediateStorage(paths['storage'])
    
    if force:
        print("🗑️  Force режим: очистка промежуточных результатов...")
        storage.clear_storage()
    
    start_time = datetime.now()
    
    try:
        # Инициализация PDF процессора
        print(f"📄 Инициализация PDF процессора...")
        pdf_processor = PDFProcessor(
            pdf_path=pdf_path,
            temp_dir=paths['temp'],
            dpi=150,  # Оптимальное качество для Vision API
            image_format="PNG"
        )
        
        with pdf_processor:
            pdf_processor.load_pdf()
            total_pages = pdf_processor.get_page_count()
            
            if end_page is None:
                end_page = total_pages
            else:
                end_page = min(end_page, total_pages)
            
            print(f"✅ PDF загружен: {total_pages} страниц")
            print(f"🎯 Обработка: страницы {start_page}-{end_page}")
            
            # Проверяем уже обработанные страницы
            processed_pages = set(storage.get_processed_pages())
            
            if processed_pages and not force:
                print(f"📋 Найдено {len(processed_pages)} уже обработанных страниц")
                print(f"📊 Последняя: {max(processed_pages) if processed_pages else 'none'}")
            
            # Инициализация компонентов
            data_extractor = DataExtractor()
            vision_api = SimpleVisionAPI()
            
            print(f"🤖 Реальный GPT-4 Vision API инициализирован")
            
            # Счётчики
            processed_count = 0
            skipped_count = 0 
            error_count = 0
            total_tasks = 0
            
            print(f"\n🚀 Начинаем обработку с реальным API...")
            
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
                    
                    # Конвертация в изображение
                    if verbose:
                        print(f"  🖼️  Конвертация в изображение...")
                    image_data = pdf_processor.convert_page_to_image(page_num - 1, save_to_file=False)
                    
                    # Обработка через реальный API
                    if verbose:
                        print(f"  🤖 GPT-4 Vision API запрос...")
                    
                    api_response = vision_api.extract_tasks_from_page(image_data, page_num)
                    
                    if verbose:
                        print(f"  ✅ API ответ получен ({api_response['model']})")
                        print(f"  📊 Tokens: {api_response['usage'].get('total_tokens', 0)}")
                    
                    # Извлечение данных
                    if verbose:
                        print(f"  📋 Извлечение задач...")
                    
                    image_info = {
                        "size_bytes": len(image_data),
                        "format": "PNG",
                        "page_number": page_num
                    }
                    
                    page = data_extractor.parse_api_response(
                        api_response['parsed_data'],
                        page_num,
                        page_start_time,
                        image_info
                    )
                    
                    # Сохранение промежуточного результата
                    page_result = {
                        'page_number': page_num,
                        'tasks': [task.model_dump() for task in page.tasks],
                        'processing_time': time.time() - page_start_time,
                        'image_info': image_info,
                        'api_method': 'real_gpt4_vision',
                        'task_count': len(page.tasks),
                        'api_response': api_response
                    }
                    
                    storage.save_page_result(page_num, page_result)
                    
                    processed_count += 1
                    total_tasks += len(page.tasks)
                    
                    processing_time = time.time() - page_start_time
                    print(f"     ✅ Задач: {len(page.tasks)}, Время: {processing_time:.1f}s")
                    
                    if verbose:
                        for i, task in enumerate(page.tasks, 1):
                            print(f"       {i}. {task.task_number}: {task.task_text[:40]}...")
                    
                    # Пауза для вежливости к API
                    time.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Error processing page {page_num}: {e}")
                    print(f"     ❌ Ошибка на странице {page_num}: {e}")
                    error_count += 1
                    continue
            
            # Финальный сбор результатов
            print(f"\n💾 Сбор финальных результатов...")
            all_results = storage.load_all_results()
            
            # Создание итогового CSV
            if all_results:
                print(f"📊 Создание CSV файла...")
                create_final_csv(all_results, output_csv)
            
            # Статистика
            total_time = (datetime.now() - start_time).total_seconds()
            
            print(f"\n🎉 ОБРАБОТКА ЗАВЕРШЕНА!")
            print(f"=" * 40)
            print(f"📊 Статистика:")
            print(f"   📚 Страниц обработано: {processed_count}")
            print(f"   ⏭️  Страниц пропущено: {skipped_count}")
            print(f"   ❌ Ошибок: {error_count}")
            print(f"   📝 Задач извлечено: {total_tasks}")
            print(f"   ⏱️  Общее время: {total_time:.1f}s ({total_time/60:.1f} минут)")
            if processed_count > 0:
                print(f"   ⚡ Скорость: {processed_count/total_time*60:.1f} страниц/минуту")
            print(f"   📁 CSV файл: {output_csv}")
            
            return True
            
    except Exception as e:
        logger.error(f"Critical error: {e}")
        print(f"❌ Критическая ошибка: {e}")
        return False


def create_final_csv(results: List[Dict], output_path: str) -> None:
    """Создаёт финальный CSV файл из промежуточных результатов."""
    
    all_tasks = []
    
    for page_result in results:
        page_num = page_result['page_number']
        processing_time = page_result.get('processing_time', 0)
        api_method = page_result.get('api_method', 'unknown')
        
        for task_data in page_result.get('tasks', []):
            task_row = {
                'page_number': page_num,
                'task_number': task_data.get('task_number', 'unknown'),
                'task_text': task_data.get('task_text', ''),
                'has_image': task_data.get('has_image', False),
                'confidence_score': task_data.get('confidence_score', 0.0),
                'processing_time': processing_time,
                'api_method': api_method,
                'extracted_at': page_result.get('processed_at', ''),
                'word_count': len(task_data.get('task_text', '').split())
            }
            all_tasks.append(task_row)
    
    # Сортируем по номеру страницы
    all_tasks.sort(key=lambda x: x['page_number'])
    
    # Записываем CSV
    import csv
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        if all_tasks:
            fieldnames = list(all_tasks[0].keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_tasks)
    
    print(f"✅ CSV создан: {len(all_tasks)} задач сохранено")


if __name__ == "__main__":
    process_textbook_real_api() 