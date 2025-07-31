#!/usr/bin/env python3
"""
OCR-OCD EasyOCR-Only Version
============================

Обработка математических задач используя только EasyOCR данные
Работает без API ограничений и блокировок
"""

import sys
import json
import time
import click
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import re

# Добавляем src в Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.utils.logger import setup_development_logger, setup_production_logger, get_logger
from src.utils.easyocr_parser import EasyOCRParser


class EasyOCRTaskExtractor:
    """Извлечение математических задач из EasyOCR данных."""
    
    def __init__(self, ocr_file_path: str):
        self.ocr_parser = EasyOCRParser(ocr_file_path)
        
        # Паттерны для поиска математических задач
        self.task_patterns = [
            r'сколько.*\?',
            r'реши.*',
            r'найди.*',
            r'вычисли.*',
            r'посчитай.*',
            r'\d+\s*[+\-×÷]\s*\d+',
            r'больше.*меньше',
            r'длиннее.*короче',
            r'задач[аи].*',
            r'пример.*',
            r'упражнение.*'
        ]
        
        # Ключевые слова для определения has_image
        self.image_keywords = [
            'рисун', 'картин', 'схем', 'диаграмм', 'график', 'чертёж', 
            'покажи', 'нарисовано', 'изображ', 'видишь'
        ]
        
    def extract_tasks_from_page(self, page_number: int) -> Dict[str, Any]:
        """Извлекает задачи со страницы используя только EasyOCR."""
        
        try:
            start_time = time.time()
            
            # Получаем OCR данные страницы
            ocr_page = self.ocr_parser.parse_page(page_number)
            
            if not ocr_page:
                return {
                    "page_number": page_number,
                    "tasks": [],
                    "processing_time": time.time() - start_time,
                    "method": "easyocr_only",
                    "error": "No OCR data found"
                }
            
            # Извлекаем задачи
            tasks = self._extract_math_tasks(ocr_page)
            
            processing_time = time.time() - start_time
            
            return {
                "page_number": page_number,
                "tasks": tasks,
                "processing_time": processing_time,
                "method": "easyocr_only",
                "ocr_stats": {
                    "total_words": ocr_page.word_count,
                    "total_lines": len(ocr_page.lines),
                    "avg_confidence": round(ocr_page.avg_confidence, 1),
                    "numbers_found": ocr_page.get_numbers_and_operators()[:10]
                },
                "full_text": ocr_page.text
            }
            
        except Exception as e:
            return {
                "page_number": page_number,
                "tasks": [],
                "processing_time": 0,
                "method": "easyocr_only",
                "error": str(e)
            }
    
    def _extract_math_tasks(self, ocr_page) -> List[Dict[str, Any]]:
        """Извлекает математические задачи из OCR данных."""
        
        tasks = []
        full_text = ocr_page.text.lower()
        lines = ocr_page.text.split('\n')
        
        # Метод 1: Поиск по паттернам
        pattern_tasks = self._find_pattern_tasks(lines)
        tasks.extend(pattern_tasks)
        
        # Метод 2: Поиск строк с числами и операциями
        number_tasks = self._find_number_tasks(lines, ocr_page)
        tasks.extend(number_tasks)
        
        # Метод 3: Анализ контекста (длинные осмысленные фразы)
        context_tasks = self._find_context_tasks(lines)
        tasks.extend(context_tasks)
        
        # Если задач не найдено, создаём общую задачу из высокоточного текста
        if not tasks:
            high_conf_text = ocr_page.get_high_confidence_text()
            if high_conf_text and len(high_conf_text.strip()) > 10:
                tasks.append({
                    "task_number": "page-content-1",
                    "task_text": high_conf_text[:300],
                    "has_image": self._has_image_indicators(high_conf_text),
                    "confidence_score": ocr_page.avg_confidence / 100,
                    "extraction_method": "high_confidence_content"
                })
        
        # Убираем дубликаты и улучшаем задачи
        tasks = self._clean_and_improve_tasks(tasks, ocr_page)
        
        return tasks
    
    def _find_pattern_tasks(self, lines: List[str]) -> List[Dict[str, Any]]:
        """Поиск задач по паттернам."""
        tasks = []
        task_num = 1
        
        for line in lines:
            line_clean = line.strip()
            if len(line_clean) < 5:
                continue
            
            line_lower = line_clean.lower()
            
            # Проверяем паттерны
            for pattern in self.task_patterns:
                if re.search(pattern, line_lower):
                    tasks.append({
                        "task_number": f"pattern-{task_num}",
                        "task_text": line_clean,
                        "has_image": self._has_image_indicators(line_lower),
                        "confidence_score": 0.8,
                        "extraction_method": f"pattern_match_{pattern[:10]}"
                    })
                    task_num += 1
                    break
        
        return tasks
    
    def _find_number_tasks(self, lines: List[str], ocr_page) -> List[Dict[str, Any]]:
        """Поиск задач с числами и операциями."""
        tasks = []
        numbers = ocr_page.get_numbers_and_operators()
        
        if not numbers:
            return tasks
        
        # Ищем строки содержащие числа
        number_lines = []
        for line in lines:
            line_clean = line.strip()
            if len(line_clean) < 3:
                continue
                
            # Проверяем есть ли числа в строке
            has_numbers = any(num in line_clean for num in numbers if num.isdigit())
            has_operators = any(op in line_clean for op in ['+', '-', '=', '>', '<', '×', '÷'])
            
            if has_numbers or has_operators:
                number_lines.append(line_clean)
        
        # Группируем близкие строки в задачи
        task_num = 1
        for line in number_lines:
            if len(line) > 5:
                tasks.append({
                    "task_number": f"math-{task_num}",
                    "task_text": line,
                    "has_image": self._has_image_indicators(line.lower()),
                    "confidence_score": 0.7,
                    "extraction_method": "number_analysis"
                })
                task_num += 1
        
        return tasks
    
    def _find_context_tasks(self, lines: List[str]) -> List[Dict[str, Any]]:
        """Поиск по контексту (осмысленные фразы)."""
        tasks = []
        
        # Ищем длинные осмысленные строки
        meaningful_lines = []
        for line in lines:
            line_clean = line.strip()
            
            # Фильтры для осмысленного содержимого
            if (len(line_clean) > 15 and 
                not line_clean.isupper() and  # Не только заглавные
                ' ' in line_clean and  # Есть пробелы
                any(char.isalpha() for char in line_clean)):  # Есть буквы
                
                meaningful_lines.append(line_clean)
        
        # Создаём задачи из осмысленных строк
        task_num = 1
        for line in meaningful_lines[:3]:  # Максимум 3 контекстных задачи
            # Проверяем что это не служебная информация
            line_lower = line.lower()
            if not any(skip in line_lower for skip in ['издание', 'министерство', 'учпедгиз', 'страница']):
                tasks.append({
                    "task_number": f"context-{task_num}",
                    "task_text": line,
                    "has_image": self._has_image_indicators(line_lower),
                    "confidence_score": 0.6,
                    "extraction_method": "context_analysis"
                })
                task_num += 1
        
        return tasks
    
    def _has_image_indicators(self, text: str) -> bool:
        """Проверяет есть ли индикаторы изображений в тексте."""
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in self.image_keywords)
    
    def _clean_and_improve_tasks(self, tasks: List[Dict], ocr_page) -> List[Dict]:
        """Очищает и улучшает найденные задачи."""
        
        if not tasks:
            return tasks
        
        # Убираем дубликаты по тексту
        seen_texts = set()
        unique_tasks = []
        
        for task in tasks:
            text = task['task_text'].strip()
            if text and text not in seen_texts:
                seen_texts.add(text)
                unique_tasks.append(task)
        
        # Перенумеровываем задачи
        for i, task in enumerate(unique_tasks, 1):
            if task['task_number'].startswith(('pattern-', 'math-', 'context-')):
                task['task_number'] = f"easyocr-{i}"
        
        # Добавляем метаданные OCR
        for task in unique_tasks:
            task.update({
                "page_ocr_confidence": round(ocr_page.avg_confidence, 1),
                "page_word_count": ocr_page.word_count,
                "extraction_source": "easyocr_analysis"
            })
        
        return unique_tasks


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
            'storage_version': '2.3-easyocr-only'
        })
        
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


@click.command()
@click.argument('ocr_file', type=click.Path(exists=True))
@click.argument('output_csv', type=click.Path())
@click.option('--force', is_flag=True, help='Принудительно переобработать все страницы')
@click.option('--start-page', type=int, default=1, help='Начальная страница для обработки')
@click.option('--end-page', type=int, default=None, help='Конечная страница для обработки')
@click.option('--production', is_flag=True, help='Production режим логирования')
@click.option('--verbose', is_flag=True, help='Подробный вывод')
def process_textbook_easyocr_only(ocr_file, output_csv, force, start_page, end_page, production, verbose):
    """
    OCR-OCD EasyOCR-Only: Обработка без API ограничений.
    
    Извлекает математические задачи используя только EasyOCR данные.
    """
    
    print("🚀📚 OCR-OCD EasyOCR-Only: Независимая обработка")
    print("=" * 55)
    print(f"🔍 EasyOCR файл: {ocr_file}")
    print(f"📊 Вывод: {output_csv}")
    print(f"🔄 Force режим: {'✅' if force else '❌'}")
    print(f"🚫 Без API зависимостей: ✅")
    
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
        'storage': Path("temp/processed_pages_easyocr_only")
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
        # Инициализация EasyOCR экстрактора
        print(f"🔍 Инициализация EasyOCR экстрактора...")
        extractor = EasyOCRTaskExtractor(ocr_file)
        
        # Получаем доступные страницы
        available_pages = extractor.ocr_parser.get_available_pages()
        
        if end_page is None:
            end_page = max(available_pages) if available_pages else start_page
        else:
            end_page = min(end_page, max(available_pages) if available_pages else end_page)
        
        print(f"✅ EasyOCR данные загружены: {len(available_pages)} страниц доступно")
        print(f"🎯 Обработка: страницы {start_page}-{end_page}")
        
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
        
        print(f"\n🚀 Начинаем EasyOCR-only обработку...")
        
        for page_num in range(start_page, end_page + 1):
            page_start_time = time.time()
            
            # Проверяем доступность страницы
            if page_num not in available_pages:
                if verbose:
                    print(f"⏭️  Страница {page_num}: нет OCR данных")
                continue
            
            # Проверяем, нужно ли обрабатывать страницу
            if not force and page_num in processed_pages:
                skipped_count += 1
                if verbose:
                    print(f"⏭️  Страница {page_num}: пропущена (уже обработана)")
                continue
            
            try:
                progress = (page_num - start_page + 1) / (end_page - start_page + 1) * 100
                print(f"\n📖 Страница {page_num}/{end_page} ({progress:.1f}%)")
                
                # Обработка через EasyOCR экстрактор
                if verbose:
                    print(f"  🔍 EasyOCR анализ...")
                
                result = extractor.extract_tasks_from_page(page_num)
                
                if 'error' in result:
                    error_count += 1
                    print(f"     ❌ Ошибка: {result['error']}")
                    continue
                
                tasks = result['tasks']
                ocr_stats = result.get('ocr_stats', {})
                
                if verbose:
                    print(f"  ✅ OCR анализ завершён")
                    print(f"  📊 Слов: {ocr_stats.get('total_words', 0)}, "
                          f"Строк: {ocr_stats.get('total_lines', 0)}, "
                          f"Confidence: {ocr_stats.get('avg_confidence', 0)}%")
                
                # Сохранение промежуточного результата
                page_result = {
                    'page_number': page_num,
                    'tasks': tasks,
                    'processing_time': result['processing_time'],
                    'ocr_stats': ocr_stats,
                    'api_method': 'easyocr_only',
                    'task_count': len(tasks),
                    'full_text': result.get('full_text', '')
                }
                
                storage.save_page_result(page_num, page_result)
                
                processed_count += 1
                total_tasks += len(tasks)
                
                processing_time = time.time() - page_start_time
                print(f"     ✅ Задач: {len(tasks)}, Время: {processing_time:.1f}s")
                
                if verbose and tasks:
                    for i, task in enumerate(tasks, 1):
                        method = task.get('extraction_method', 'unknown')
                        print(f"       {i}. [{method}] {task['task_number']}: {task['task_text'][:60]}...")
                
                # Небольшая пауза для стабильности
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
            print(f"📊 Создание EasyOCR-only CSV файла...")
            create_easyocr_csv(all_results, output_csv)
        
        # Статистика
        total_time = (datetime.now() - start_time).total_seconds()
        
        print(f"\n🎉 EASYOCR-ONLY ОБРАБОТКА ЗАВЕРШЕНА!")
        print(f"=" * 50)
        print(f"📊 Статистика:")
        print(f"   📚 Страниц обработано: {processed_count}")
        print(f"   ⏭️  Страниц пропущено: {skipped_count}")
        print(f"   ❌ Ошибок: {error_count}")
        print(f"   📝 Задач извлечено: {total_tasks}")
        print(f"   💰 Стоимость: $0.00 (бесплатно!)")
        print(f"   ⏱️  Общее время: {total_time:.1f}s ({total_time/60:.1f} минут)")
        if processed_count > 0:
            print(f"   ⚡ Скорость: {processed_count/total_time*60:.1f} страниц/минуту")
            print(f"   📈 Среднее задач/страница: {total_tasks/processed_count:.1f}")
        print(f"   📁 EasyOCR CSV: {output_csv}")
        
        return True
        
    except Exception as e:
        logger.error(f"Critical error: {e}")
        print(f"❌ Критическая ошибка: {e}")
        return False


def create_easyocr_csv(results: List[Dict], output_path: str) -> None:
    """Создаёт CSV файл из EasyOCR результатов."""
    
    all_tasks = []
    
    for page_result in results:
        page_num = page_result['page_number']
        processing_time = page_result.get('processing_time', 0)
        ocr_stats = page_result.get('ocr_stats', {})
        
        for task_data in page_result.get('tasks', []):
            task_row = {
                'page_number': page_num,
                'task_number': task_data.get('task_number', 'unknown'),
                'task_text': task_data.get('task_text', ''),
                'has_image': task_data.get('has_image', False),
                'confidence_score': task_data.get('confidence_score', 0.0),
                'processing_time': processing_time,
                'api_method': 'easyocr_only',
                'extraction_method': task_data.get('extraction_method', 'unknown'),
                'page_ocr_confidence': task_data.get('page_ocr_confidence', 0),
                'page_word_count': task_data.get('page_word_count', 0),
                'extraction_source': task_data.get('extraction_source', 'easyocr'),
                'extracted_at': page_result.get('processed_at', ''),
                'word_count': len(task_data.get('task_text', '').split()),
                'system_type': 'easyocr_standalone'
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
    
    print(f"✅ EasyOCR CSV создан: {len(all_tasks)} задач сохранено")
    print(f"📊 Поля: extraction_method, page_ocr_confidence, system_type")


if __name__ == "__main__":
    process_textbook_easyocr_only() 