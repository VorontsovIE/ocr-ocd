#!/usr/bin/env python3
"""
OCR-OCD v2: Полная обработка учебника с промежуточным сохранением
================================================================

Новые функции:
- Промежуточное сохранение результатов каждой страницы
- Resume capability - продолжение с места остановки
- --force флаг для принудительной переобработки
- Поддержка реального OpenAI API
- Robust error handling и recovery
"""

import sys
import json
import time
import random
import click
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import csv

# Добавляем src в Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.core.pdf_processor import PDFProcessor
from src.core.data_extractor import DataExtractor
from src.core.csv_writer import CSVWriter
from src.core.vision_client import VisionClient
from src.core.prompt_manager import PromptManager
from src.utils.config import load_config
from src.utils.logger import setup_development_logger, setup_production_logger, get_logger
from src.utils.state_manager import StateManager


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
            'storage_version': '2.0'
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


def generate_realistic_task_v2(page_number: int) -> Dict[str, Any]:
    """Генерирует более реалистичные задачи для страниц."""
    
    task_templates = {
        "counting": [
            "Сосчитай сколько {} на рисунке",
            "Покажи число {} на счётных палочках", 
            "Обведи все цифры {}",
            "Найди и раскрась {} предмета",
            "Сколько {} ты видишь?"
        ],
        "addition": [
            "{} + {} = ?",
            "К {} прибавить {} получится ?",
            "Сколько будет {} да {}?",
            "Реши пример: {} + {} = □",
            "Найди сумму чисел {} и {}"
        ],
        "subtraction": [
            "{} - {} = ?",
            "От {} отнять {} получится ?",
            "Сколько останется если от {} убрать {}?",
            "Реши пример: {} - {} = □",
            "На сколько {} больше чем {}?"
        ],
        "comparison": [
            "Сравни числа {} и {} (поставь знак)",
            "Что больше: {} или {}?",
            "Расставь по порядку: {}, {}, {}",
            "Какое число больше: {} или {}?",
            "Поставь знак >, < или =: {} ○ {}"
        ],
        "word_problems": [
            "У Маши было {} яблока. Она дала брату {}. Сколько яблок у неё осталось?",
            "В вазе лежало {} конфет. Положили ещё {}. Сколько конфет стало в вазе?",
            "На ветке сидело {} птичек. {} улетели. Сколько птичек осталось?",
            "В классе {} мальчиков и {} девочек. Сколько всего детей в классе?",
            "Мама испекла {} пирожков. За обедом съели {}. Сколько пирожков осталось?"
        ],
        "geometry": [
            "Сколько углов у треугольника?",
            "Нарисуй квадрат со стороной {} клетки",
            "Найди все круги на рисунке и сосчитай их", 
            "Сколько сторон у четырёхугольника?",
            "Начерти отрезок длиной {} см"
        ]
    }
    
    # Определяем тип задачи по странице
    if page_number <= 30:
        task_type = "counting"
        nums = [random.randint(1, 5), random.randint(1, 3)]
    elif page_number <= 60:
        task_type = "addition" 
        nums = [random.randint(1, 5), random.randint(1, 4)]
    elif page_number <= 90:
        task_type = "subtraction"
        nums = [random.randint(3, 8), random.randint(1, 3)]
    elif page_number <= 110:
        task_type = "comparison"
        nums = [random.randint(1, 10), random.randint(1, 10)]
    elif page_number <= 130:
        task_type = "word_problems"
        nums = [random.randint(5, 15), random.randint(2, 7)]
    else:
        task_type = "geometry"
        nums = [random.randint(3, 6), random.randint(2, 4)]
    
    template = random.choice(task_templates[task_type])
    
    try:
        if task_type == "comparison":
            task_text = template.format(nums[0], nums[1], random.randint(1, 10))
        else:
            task_text = template.format(nums[0], nums[1])
    except:
        task_text = template.format(nums[0])
    
    return {
        "task_number": str(random.randint(1, 6)) if random.random() > 0.12 else f"unknown-{random.randint(1, 3)}",
        "task_text": task_text,
        "has_image": random.choice([True, False]) if task_type in ["counting", "geometry", "word_problems"] else False,
        "confidence": round(random.uniform(0.78, 0.97), 2),
        "task_type": task_type,
        "page_section": random.choice(["top", "middle", "bottom"]),
        "difficulty": random.choice(["easy", "medium", "hard"])
    }


@click.command()
@click.argument('pdf_path', type=click.Path(exists=True))
@click.argument('output_csv', type=click.Path())
@click.option('--force', is_flag=True, help='Принудительно переобработать все страницы')
@click.option('--start-page', type=int, default=1, help='Начальная страница для обработки')
@click.option('--end-page', type=int, default=None, help='Конечная страница для обработки')
@click.option('--use-real-api', is_flag=True, help='Использовать реальный OpenAI API')
@click.option('--production', is_flag=True, help='Production режим логирования')
@click.option('--verbose', is_flag=True, help='Подробный вывод')
def process_textbook_v2(pdf_path, output_csv, force, start_page, end_page, use_real_api, production, verbose):
    """
    OCR-OCD v2: Обработка учебника с промежуточным сохранением.
    
    Новые возможности:
    - Автоматическое продолжение с места остановки
    - --force для полной переобработки  
    - --use-real-api для настоящего OpenAI API
    - Промежуточное сохранение результатов
    """
    
    print("🚀📚 OCR-OCD v2: Расширенная обработка учебника")
    print("=" * 60)
    print(f"📄 PDF: {pdf_path}")
    print(f"📊 Вывод: {output_csv}")
    print(f"🔄 Force режим: {'✅' if force else '❌'}")
    print(f"🤖 Реальный API: {'✅' if use_real_api else '❌ (Mock)'}")
    print(f"📝 Production логи: {'✅' if production else '❌'}")
    
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
        'storage': Path("temp/processed_pages")
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
        # Загрузка конфигурации
        config = load_config()
        
        # Инициализация PDF процессора
        print(f"📄 Инициализация PDF процессора...")
        pdf_processor = PDFProcessor(
            pdf_path=pdf_path,
            temp_dir=paths['temp'],
            dpi=200,  # Баланс качества и скорости
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
            
            if use_real_api:
                print(f"🤖 Инициализация реального OpenAI API...")
                vision_client = VisionClient(config.api)
                
                # Тестируем API соединение
                try:
                    vision_client.test_api_connection()
                    print(f"✅ OpenAI API подключён успешно")
                except Exception as e:
                    print(f"❌ Ошибка OpenAI API: {e}")
                    print(f"🔄 Переключение на Mock API...")
                    use_real_api = False
            
            # Счётчики
            processed_count = 0
            skipped_count = 0 
            error_count = 0
            total_tasks = 0
            
            print(f"\n🚀 Начинаем обработку...")
            
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
                    
                    # Обработка через API
                    if verbose:
                        print(f"  🤖 {'Реальный' if use_real_api else 'Mock'} API запрос...")
                    
                    if use_real_api:
                        # Реальный OpenAI API
                        try:
                            page_hints = {
                                'has_images': random.choice([True, False]),
                                'text_density': random.choice(['low', 'medium', 'high']),
                                'problem_count': random.randint(1, 4)
                            }
                            
                            api_response = vision_client.extract_tasks_from_page(
                                image_data, page_num, page_hints
                            )
                            
                            if verbose:
                                print(f"  ✅ API ответ получен")
                                
                        except Exception as e:
                            logger.error(f"API error for page {page_num}: {e}")
                            print(f"  ❌ API ошибка: {e}")
                            error_count += 1
                            continue
                    else:
                        # Mock API
                        num_tasks = random.choice([1, 2, 2, 3, 3, 4])
                        tasks = []
                        
                        for i in range(num_tasks):
                            task = generate_realistic_task_v2(page_num)
                            tasks.append(task)
                        
                        api_response = {
                            "page_number": page_num,
                            "tasks": tasks,
                            "page_info": {
                                "total_tasks": len(tasks),
                                "content_type": "arithmetic_exercises",
                                "processing_notes": f"Mock API response for page {page_num}"
                            }
                        }
                    
                    # Извлечение данных
                    if verbose:
                        print(f"  📋 Извлечение задач...")
                    
                    image_info = {
                        "size_bytes": len(image_data),
                        "format": "PNG",
                        "page_number": page_num
                    }
                    
                    page = data_extractor.parse_api_response(
                        api_response,
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
                        'api_method': 'real' if use_real_api else 'mock',
                        'task_count': len(page.tasks)
                    }
                    
                    storage.save_page_result(page_num, page_result)
                    
                    processed_count += 1
                    total_tasks += len(page.tasks)
                    
                    processing_time = time.time() - page_start_time
                    print(f"     ✅ Задач: {len(page.tasks)}, Время: {processing_time:.1f}s")
                    
                    if verbose:
                        for i, task in enumerate(page.tasks, 1):
                            print(f"       {i}. {task.task_number}: {task.task_text[:40]}...")
                    
                    # Короткая пауза для стабильности
                    time.sleep(0.1)
                    
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
            
            # Создание детального отчёта
            create_processing_report_v2(all_results, {
                'processed_count': processed_count,
                'skipped_count': skipped_count,
                'error_count': error_count,
                'total_tasks': total_tasks,
                'total_time': total_time,
                'use_real_api': use_real_api,
                'force_mode': force
            })
            
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
                'task_type': task_data.get('extraction_metadata', {}).get('task_type', 'unknown'),
                'extracted_at': page_result.get('processed_at', ''),
                'word_count': len(task_data.get('task_text', '').split())
            }
            all_tasks.append(task_row)
    
    # Сортируем по номеру страницы
    all_tasks.sort(key=lambda x: x['page_number'])
    
    # Записываем CSV
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        if all_tasks:
            fieldnames = list(all_tasks[0].keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_tasks)
    
    print(f"✅ CSV создан: {len(all_tasks)} задач сохранено")


def create_processing_report_v2(results: List[Dict], stats: Dict) -> None:
    """Создаёт детальный отчёт об обработке v2."""
    
    report_path = Path("output/processing_report_v2.txt")
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("🔍 OCR-OCD v2: ОТЧЁТ О ОБРАБОТКЕ УЧЕБНИКА\n")
        f.write("=" * 60 + "\n\n")
        
        f.write(f"📅 Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"🎯 Система: OCR-OCD v2 с промежуточным сохранением\n")
        f.write(f"🤖 API: {'Реальный OpenAI' if stats['use_real_api'] else 'Mock API'}\n")
        f.write(f"🔄 Force режим: {'Включён' if stats['force_mode'] else 'Выключен'}\n\n")
        
        f.write("📊 РЕЗУЛЬТАТЫ ОБРАБОТКИ:\n")
        f.write("-" * 30 + "\n")
        f.write(f"✅ Страниц обработано: {stats['processed_count']}\n")
        f.write(f"⏭️  Страниц пропущено: {stats['skipped_count']}\n") 
        f.write(f"❌ Ошибок: {stats['error_count']}\n")
        f.write(f"📝 Задач извлечено: {stats['total_tasks']}\n")
        f.write(f"⏱️  Время обработки: {stats['total_time']:.1f}s\n")
        
        if stats['processed_count'] > 0:
            f.write(f"⚡ Скорость: {stats['processed_count']/stats['total_time']*60:.1f} стр/мин\n")
            f.write(f"📄 Среднее задач/страница: {stats['total_tasks']/stats['processed_count']:.1f}\n")
        
        f.write(f"\n🎯 НОВЫЕ ВОЗМОЖНОСТИ v2:\n")
        f.write("-" * 30 + "\n")
        f.write(f"✅ Промежуточное сохранение результатов\n")
        f.write(f"✅ Resume capability (продолжение работы)\n")
        f.write(f"✅ Force режим для полной переобработки\n")
        f.write(f"✅ Поддержка реального OpenAI API\n")
        f.write(f"✅ Robust error handling\n")
        
        if results:
            f.write(f"\n📋 ДЕТАЛИЗАЦИЯ ПО СТРАНИЦАМ:\n")
            f.write("-" * 30 + "\n")
            
            for result in results[:10]:  # Первые 10 для примера
                page_num = result['page_number']
                task_count = len(result.get('tasks', []))
                proc_time = result.get('processing_time', 0)
                api_method = result.get('api_method', 'unknown')
                
                f.write(f"📖 Страница {page_num}: {task_count} задач, "
                       f"{proc_time:.1f}s, {api_method} API\n")
            
            if len(results) > 10:
                f.write(f"... и ещё {len(results) - 10} страниц\n")
    
    print(f"📋 Детальный отчёт v2 создан: {report_path}")


if __name__ == "__main__":
    process_textbook_v2() 