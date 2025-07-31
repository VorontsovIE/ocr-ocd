#!/usr/bin/env python3
"""
OCR-OCD v2 Enhanced: GPT-4 Vision + EasyOCR Integration
=====================================================

Максимальное качество распознавания: GPT-4 Vision + EasyOCR данные
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
from src.utils.easyocr_parser import EasyOCRParser


class EnhancedVisionAPI:
    """Улучшенный клиент для GPT-4 Vision API с интеграцией EasyOCR."""
    
    def __init__(self, ocr_file_path: Optional[str] = None):
        load_dotenv()
        self.client = openai.OpenAI()
        
        # Инициализация EasyOCR парсера (опционально)
        self.ocr_parser = None
        if ocr_file_path and Path(ocr_file_path).exists():
            try:
                self.ocr_parser = EasyOCRParser(ocr_file_path)
                print(f"✅ EasyOCR интеграция активна: {len(self.ocr_parser.get_available_pages())} страниц")
            except Exception as e:
                print(f"⚠️  EasyOCR недоступен: {e}")
                self.ocr_parser = None
        else:
            print("📋 Работаем только с GPT-4 Vision (без EasyOCR)")
        
    def extract_tasks_from_page(self, image_data: bytes, page_number: int) -> Dict[str, Any]:
        """Извлекает задачи со страницы используя GPT-4 Vision + EasyOCR."""
        
        # Кодируем изображение
        b64_image = base64.b64encode(image_data).decode('utf-8')
        
        # Базовый промпт
        base_prompt = f"""Проанализируй страницу {page_number} из учебника математики для 1 класса (1959 год).

Найди все математические задачи и упражнения на этой странице.
Для каждой задачи верни информацию в JSON формате:

{{
  "page_number": {page_number},
  "tasks": [
    {{
      "task_number": "1",
      "task_text": "полный текст задачи",
      "has_image": true
    }}
  ]
}}

ВАЖНО:
- Если номер задачи не видно, используй "unknown-1", "unknown-2" и т.д.
- В task_text включай ВЕСЬ текст задачи включая числа и условия
- has_image = true если есть рисунки, схемы, диаграммы к задаче
- Игнорируй номера страниц, заголовки, название учебника
- Ответь ТОЛЬКО JSON, без дополнительного текста"""

        # Дополняем промпт данными EasyOCR если доступны
        ocr_supplement = ""
        if self.ocr_parser:
            ocr_supplement = self.ocr_parser.create_vision_prompt_supplement(page_number)
            if ocr_supplement:
                base_prompt += f"\n\n{ocr_supplement}"

        try:
            start_time = time.time()
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user", 
                        "content": [
                            {"type": "text", "text": base_prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_image}"}}
                        ]
                    }
                ],
                max_tokens=2500,  # Увеличиваем лимит для более детального анализа
                temperature=0.05   # Очень низкая температура для точности
            )
            
            processing_time = time.time() - start_time
            content = response.choices[0].message.content
            
            # Продвинутый парсинг JSON
            try:
                # Попытка прямого парсинга
                parsed_data = json.loads(content)
                json_valid = True
            except json.JSONDecodeError:
                # Попытка извлечь JSON из текста
                json_valid = False
                try:
                    # Ищем JSON блок в ответе
                    import re
                    json_match = re.search(r'\{.*\}', content, re.DOTALL)
                    if json_match:
                        parsed_data = json.loads(json_match.group())
                        json_valid = True
                    else:
                        raise ValueError("No JSON found")
                except:
                    # Если всё плохо, создаём структуру вручную из текста
                    parsed_data = self._parse_fallback_response(content, page_number)
            
            # Обогащение данных OCR информацией
            if self.ocr_parser and json_valid:
                parsed_data = self._enrich_with_ocr_data(parsed_data, page_number)
            
            return {
                "content": content,
                "parsed_data": parsed_data,
                "json_valid": json_valid,
                "usage": response.usage.model_dump() if response.usage else {},
                "model": response.model,
                "processing_time": processing_time,
                "image_info": {"size_bytes": len(image_data)},
                "prompt_type": "enhanced_vision_ocr" if self.ocr_parser else "vision_only",
                "ocr_supplement_length": len(ocr_supplement) if ocr_supplement else 0
            }
            
        except Exception as e:
            print(f"❌ API ошибка на странице {page_number}: {e}")
            # Возвращаем fallback результат с OCR если доступно
            fallback_data = self._create_ocr_fallback(page_number) if self.ocr_parser else {
                "page_number": page_number, 
                "tasks": []
            }
            
            return {
                "content": f"Ошибка API: {e}",
                "parsed_data": fallback_data,
                "json_valid": False,
                "usage": {},
                "model": "error",
                "processing_time": 0,
                "image_info": {"size_bytes": len(image_data)},
                "prompt_type": "error_fallback"
            }
    
    def _parse_fallback_response(self, content: str, page_number: int) -> Dict[str, Any]:
        """Парсит ответ если JSON не удался."""
        lines = content.split('\n')
        tasks = []
        
        current_task = None
        task_counter = 1
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Простая эвристика для поиска задач
            if any(keyword in line.lower() for keyword in ['задач', 'пример', 'реши', 'найди', 'сколько']):
                if current_task:
                    tasks.append(current_task)
                current_task = {
                    "task_number": f"unknown-{task_counter}",
                    "task_text": line,
                    "has_image": "рисун" in line.lower() or "схем" in line.lower()
                }
                task_counter += 1
            elif current_task and len(line) > 10:
                # Продолжение текста задачи
                current_task["task_text"] += " " + line
        
        if current_task:
            tasks.append(current_task)
        
        return {
            "page_number": page_number,
            "tasks": tasks if tasks else [
                {
                    "task_number": "unknown-1",
                    "task_text": content[:200] + "..." if len(content) > 200 else content,
                    "has_image": False
                }
            ]
        }
    
    def _enrich_with_ocr_data(self, parsed_data: Dict[str, Any], page_number: int) -> Dict[str, Any]:
        """Обогащает данные GPT-4 с помощью OCR информации."""
        if not self.ocr_parser:
            return parsed_data
        
        try:
            ocr_page = self.ocr_parser.parse_page(page_number)
            if not ocr_page:
                return parsed_data
            
            # Добавляем метаданные OCR
            if "page_info" not in parsed_data:
                parsed_data["page_info"] = {}
            
            parsed_data["page_info"].update({
                "ocr_word_count": ocr_page.word_count,
                "ocr_confidence": round(ocr_page.avg_confidence, 1),
                "ocr_numbers": ocr_page.get_numbers_and_operators()[:10],
                "ocr_integration": "enhanced"
            })
            
            # Улучшаем task_text если есть совпадения с OCR
            ocr_text_lower = ocr_page.text.lower()
            for task in parsed_data.get("tasks", []):
                task_text = task.get("task_text", "")
                
                # Проверяем есть ли числа из OCR в тексте задачи
                ocr_numbers = ocr_page.get_numbers_and_operators()
                task_numbers = [char for char in task_text if char.isdigit()]
                
                if ocr_numbers and not task_numbers:
                    # Если в задаче нет чисел, но в OCR есть, добавляем примечание
                    task["task_text"] += f" [Числа на странице: {', '.join(ocr_numbers[:5])}]"
            
            return parsed_data
            
        except Exception as e:
            print(f"⚠️  Ошибка обогащения OCR для страницы {page_number}: {e}")
            return parsed_data
    
    def _create_ocr_fallback(self, page_number: int) -> Dict[str, Any]:
        """Создаёт fallback результат используя только OCR данные."""
        if not self.ocr_parser:
            return {"page_number": page_number, "tasks": []}
        
        try:
            ocr_page = self.ocr_parser.parse_page(page_number)
            if not ocr_page:
                return {"page_number": page_number, "tasks": []}
            
            # Создаём простую задачу из OCR данных
            ocr_text = ocr_page.get_high_confidence_text()[:200]
            numbers = ocr_page.get_numbers_and_operators()
            
            return {
                "page_number": page_number,
                "tasks": [
                    {
                        "task_number": "ocr-fallback-1",
                        "task_text": f"OCR восстановление: {ocr_text}",
                        "has_image": len(numbers) > 0,
                        "fallback_source": "easyocr"
                    }
                ]
            }
            
        except Exception as e:
            return {"page_number": page_number, "tasks": []}


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
            'storage_version': '2.2-enhanced'
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
@click.option('--ocr-file', type=click.Path(), help='Путь к файлу EasyOCR TSV данных')
@click.option('--force', is_flag=True, help='Принудительно переобработать все страницы')
@click.option('--start-page', type=int, default=1, help='Начальная страница для обработки')
@click.option('--end-page', type=int, default=None, help='Конечная страница для обработки')
@click.option('--production', is_flag=True, help='Production режим логирования')
@click.option('--verbose', is_flag=True, help='Подробный вывод')
def process_textbook_enhanced(pdf_path, output_csv, ocr_file, force, start_page, end_page, production, verbose):
    """
    OCR-OCD v2 Enhanced: GPT-4 Vision + EasyOCR Integration.
    
    Максимальное качество распознавания математических задач.
    """
    
    print("🚀📚 OCR-OCD v2 Enhanced: GPT-4 Vision + EasyOCR")
    print("=" * 60)
    print(f"📄 PDF: {pdf_path}")
    print(f"📊 Вывод: {output_csv}")
    print(f"🔍 EasyOCR файл: {ocr_file if ocr_file else 'Не указан'}")
    print(f"🔄 Force режим: {'✅' if force else '❌'}")
    print(f"🤖 Enhanced AI Pipeline: ✅")
    
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
        'storage': Path("temp/processed_pages_enhanced")
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
            dpi=200,  # Высокое качество для максимальной точности
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
            enhanced_api = EnhancedVisionAPI(ocr_file)
            
            print(f"🤖 Enhanced Vision API инициализирован")
            
            # Счётчики
            processed_count = 0
            skipped_count = 0 
            error_count = 0
            total_tasks = 0
            total_tokens = 0
            
            print(f"\n🚀 Начинаем enhanced обработку...")
            
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
                    
                    # Обработка через Enhanced API
                    if verbose:
                        print(f"  🤖 Enhanced GPT-4 Vision + OCR запрос...")
                    
                    api_response = enhanced_api.extract_tasks_from_page(image_data, page_num)
                    
                    if verbose:
                        print(f"  ✅ API ответ получен ({api_response['model']})")
                        tokens_used = api_response['usage'].get('total_tokens', 0)
                        print(f"  📊 Tokens: {tokens_used}")
                        print(f"  🔍 OCR дополнение: {api_response.get('ocr_supplement_length', 0)} символов")
                        total_tokens += tokens_used
                    
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
                        'api_method': 'enhanced_gpt4_vision_ocr',
                        'task_count': len(page.tasks),
                        'api_response': api_response,
                        'tokens_used': api_response['usage'].get('total_tokens', 0)
                    }
                    
                    storage.save_page_result(page_num, page_result)
                    
                    processed_count += 1
                    total_tasks += len(page.tasks)
                    
                    processing_time = time.time() - page_start_time
                    print(f"     ✅ Задач: {len(page.tasks)}, Время: {processing_time:.1f}s")
                    
                    if verbose:
                        for i, task in enumerate(page.tasks, 1):
                            print(f"       {i}. {task.task_number}: {task.task_text[:50]}...")
                    
                    # Умная пауза (больше для сложных страниц)
                    pause = 2 if len(page.tasks) > 2 else 1
                    time.sleep(pause)
                    
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
                print(f"📊 Создание enhanced CSV файла...")
                create_enhanced_csv(all_results, output_csv)
            
            # Статистика
            total_time = (datetime.now() - start_time).total_seconds()
            
            print(f"\n🎉 ENHANCED ОБРАБОТКА ЗАВЕРШЕНА!")
            print(f"=" * 50)
            print(f"📊 Статистика:")
            print(f"   📚 Страниц обработано: {processed_count}")
            print(f"   ⏭️  Страниц пропущено: {skipped_count}")
            print(f"   ❌ Ошибок: {error_count}")
            print(f"   📝 Задач извлечено: {total_tasks}")
            print(f"   🎯 Общие токены: {total_tokens:,}")
            print(f"   💰 Примерная стоимость: ${total_tokens * 0.01 / 1000:.2f}")
            print(f"   ⏱️  Общее время: {total_time:.1f}s ({total_time/60:.1f} минут)")
            if processed_count > 0:
                print(f"   ⚡ Скорость: {processed_count/total_time*60:.1f} страниц/минуту")
                print(f"   📈 Среднее задач/страница: {total_tasks/processed_count:.1f}")
            print(f"   📁 Enhanced CSV: {output_csv}")
            
            return True
            
    except Exception as e:
        logger.error(f"Critical error: {e}")
        print(f"❌ Критическая ошибка: {e}")
        return False


def create_enhanced_csv(results: List[Dict], output_path: str) -> None:
    """Создаёт enhanced CSV файл из промежуточных результатов."""
    
    all_tasks = []
    
    for page_result in results:
        page_num = page_result['page_number']
        processing_time = page_result.get('processing_time', 0)
        api_method = page_result.get('api_method', 'unknown')
        tokens_used = page_result.get('tokens_used', 0)
        
        # Извлекаем OCR метаданные если есть
        api_response = page_result.get('api_response', {})
        ocr_supplement_length = api_response.get('ocr_supplement_length', 0)
        
        for task_data in page_result.get('tasks', []):
            task_row = {
                'page_number': page_num,
                'task_number': task_data.get('task_number', 'unknown'),
                'task_text': task_data.get('task_text', ''),
                'has_image': task_data.get('has_image', False),
                'confidence_score': task_data.get('confidence_score', 0.0),
                'processing_time': processing_time,
                'api_method': api_method,
                'tokens_used': tokens_used,
                'ocr_supplement_used': ocr_supplement_length > 0,
                'ocr_supplement_length': ocr_supplement_length,
                'extracted_at': page_result.get('processed_at', ''),
                'word_count': len(task_data.get('task_text', '').split()),
                'enhanced_features': 'gpt4_vision_easyocr_integration'
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
    
    print(f"✅ Enhanced CSV создан: {len(all_tasks)} задач сохранено")
    print(f"📊 Дополнительные поля: tokens_used, ocr_supplement_used, enhanced_features")


if __name__ == "__main__":
    process_textbook_enhanced() 