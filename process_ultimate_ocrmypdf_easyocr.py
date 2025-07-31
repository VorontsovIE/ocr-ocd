#!/usr/bin/env python3
"""
OCR-OCD Ultimate: OCRmyPDF-EasyOCR Optimized
============================================

Максимально оптимизированная версия для обработки
математических задач из OCRmyPDF-EasyOCR структуры.

Использует все преимущества:
- EasyOCR через GPU (высокая точность)
- Иерархическая PDF структура
- Блочная организация текста
- Confidence 100% для всех слов
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
from src.utils.ocrmypdf_easyocr_parser import OCRmyPDFEasyOCRParser, OCRTextBlock


class UltimateTaskExtractor:
    """Максимально точная извлечение математических задач из OCRmyPDF-EasyOCR данных."""
    
    def __init__(self, ocr_file_path: str):
        self.ocr_parser = OCRmyPDFEasyOCRParser(ocr_file_path)
        
        # Усовершенствованные паттерны для математических задач
        self.question_patterns = [
            r'сколько\s+.*?\?',          # Сколько ... ?
            r'где\s+.*?\?',              # Где ... ?
            r'что\s+.*?\?',              # Что ... ?
            r'как\s+.*?\?',              # Как ... ?
            r'какой\s+.*?\?',            # Какой ... ?
            r'какая\s+.*?\?',            # Какая ... ?
            r'какие\s+.*?\?',            # Какие ... ?
        ]
        
        self.task_command_patterns = [
            r'реши.*',
            r'найди.*',
            r'вычисли.*',
            r'посчитай.*',
            r'покажи.*',
            r'положи.*',
            r'нарисуй.*',
            r'отметь.*',
            r'обведи.*',
            r'подчеркни.*'
        ]
        
        self.comparison_patterns = [
            r'больше.*меньше',
            r'длиннее.*короче',
            r'выше.*ниже',
            r'шире.*уже',
            r'толще.*тоньше'
        ]
        
        # Ключевые слова для определения has_image
        self.visual_keywords = [
            'рисун', 'картин', 'схем', 'диаграмм', 'график', 'чертёж', 
            'покажи', 'нарисовано', 'изображ', 'видишь', 'нарисуй',
            'палочк', 'кружков', 'точек', 'линий', 'фигур'
        ]
        
    def extract_tasks_from_page(self, page_number: int) -> Dict[str, Any]:
        """Извлекает задачи со страницы используя OCRmyPDF-EasyOCR структуру."""
        
        try:
            start_time = time.time()
            
            # Получаем структурированные OCR данные
            ocr_page = self.ocr_parser.parse_page(page_number)
            
            if not ocr_page:
                return {
                    "page_number": page_number,
                    "tasks": [],
                    "processing_time": time.time() - start_time,
                    "method": "ultimate_ocrmypdf_easyocr",
                    "error": "No OCRmyPDF-EasyOCR data found"
                }
            
            # Многоуровневая извлечение задач
            tasks = []
            
            # Метод 1: Анализ математических блоков
            math_block_tasks = self._extract_from_math_blocks(ocr_page)
            tasks.extend(math_block_tasks)
            
            # Метод 2: Анализ блоков с вопросами
            question_block_tasks = self._extract_from_question_blocks(ocr_page)
            tasks.extend(question_block_tasks)
            
            # Метод 3: Поиск по шаблонам команд
            command_tasks = self._extract_command_tasks(ocr_page)
            tasks.extend(command_tasks)
            
            # Метод 4: Анализ сравнений и отношений
            comparison_tasks = self._extract_comparison_tasks(ocr_page)
            tasks.extend(comparison_tasks)
            
            # Метод 5: Комбинированный анализ блоков
            combined_tasks = self._extract_combined_block_tasks(ocr_page)
            tasks.extend(combined_tasks)
            
            # Очистка и оптимизация задач
            tasks = self._optimize_and_clean_tasks(tasks, ocr_page)
            
            processing_time = time.time() - start_time
            
            return {
                "page_number": page_number,
                "tasks": tasks,
                "processing_time": processing_time,
                "method": "ultimate_ocrmypdf_easyocr",
                "ocr_stats": {
                    "total_words": ocr_page.word_count,
                    "total_blocks": ocr_page.block_count,
                    "avg_confidence": ocr_page.avg_confidence,
                    "math_blocks": len(ocr_page.get_math_blocks()),
                    "question_blocks": len(ocr_page.get_question_blocks()),
                    "numbers_found": ocr_page.get_numbers_and_operators()[:10]
                },
                "extraction_methods": {
                    "math_blocks": len(math_block_tasks),
                    "question_blocks": len(question_block_tasks),
                    "command_tasks": len(command_tasks),
                    "comparison_tasks": len(comparison_tasks),
                    "combined_tasks": len(combined_tasks)
                },
                "full_text": ocr_page.text,
                "ocr_engine": "OCRmyPDF-EasyOCR-GPU"
            }
            
        except Exception as e:
            return {
                "page_number": page_number,
                "tasks": [],
                "processing_time": 0,
                "method": "ultimate_ocrmypdf_easyocr",
                "error": str(e)
            }
    
    def _extract_from_math_blocks(self, ocr_page) -> List[Dict[str, Any]]:
        """Извлекает задачи из математических блоков."""
        tasks = []
        math_blocks = ocr_page.get_math_blocks()
        
        for i, block in enumerate(math_blocks, 1):
            block_text = block.text.strip()
            if len(block_text) > 5:
                tasks.append({
                    "task_number": f"math-{i}",
                    "task_text": block_text,
                    "has_image": self._has_visual_indicators(block_text),
                    "confidence_score": 0.9,
                    "extraction_method": "math_block_analysis",
                    "block_info": {
                        "par_num": block.par_num,
                        "block_num": block.block_num,
                        "word_count": block.word_count,
                        "line_count": block.line_count,
                        "bbox": block.bbox
                    }
                })
        
        return tasks
    
    def _extract_from_question_blocks(self, ocr_page) -> List[Dict[str, Any]]:
        """Извлекает задачи из блоков с вопросами."""
        tasks = []
        question_blocks = ocr_page.get_question_blocks()
        
        for i, block in enumerate(question_blocks, 1):
            block_text = block.text.strip()
            
            # Разбиваем блок на отдельные вопросы
            questions = self._split_into_questions(block_text)
            
            for j, question in enumerate(questions, 1):
                if len(question.strip()) > 5:
                    tasks.append({
                        "task_number": f"question-{i}-{j}",
                        "task_text": question.strip(),
                        "has_image": self._has_visual_indicators(question),
                        "confidence_score": 0.95,  # Высокая уверенность для вопросов
                        "extraction_method": "question_block_analysis",
                        "block_info": {
                            "par_num": block.par_num,
                            "block_num": block.block_num,
                            "question_index": j
                        }
                    })
        
        return tasks
    
    def _extract_command_tasks(self, ocr_page) -> List[Dict[str, Any]]:
        """Извлекает задачи по командным шаблонам."""
        tasks = []
        task_num = 1
        
        for block in ocr_page.text_blocks:
            block_text = block.text.lower()
            
            for pattern in self.task_command_patterns:
                matches = re.finditer(pattern, block_text, re.IGNORECASE)
                for match in matches:
                    # Ищем полное предложение с командой
                    full_sentence = self._extract_full_sentence(block.text, match.start())
                    
                    if len(full_sentence.strip()) > 10:
                        tasks.append({
                            "task_number": f"command-{task_num}",
                            "task_text": full_sentence.strip(),
                            "has_image": self._has_visual_indicators(full_sentence),
                            "confidence_score": 0.85,
                            "extraction_method": f"command_pattern_{pattern[:10]}",
                            "match_info": {
                                "pattern": pattern,
                                "start_pos": match.start(),
                                "matched_text": match.group()
                            }
                        })
                        task_num += 1
        
        return tasks
    
    def _extract_comparison_tasks(self, ocr_page) -> List[Dict[str, Any]]:
        """Извлекает задачи со сравнениями."""
        tasks = []
        task_num = 1
        
        for block in ocr_page.text_blocks:
            block_text = block.text.lower()
            
            for pattern in self.comparison_patterns:
                if re.search(pattern, block_text, re.IGNORECASE):
                    tasks.append({
                        "task_number": f"comparison-{task_num}",
                        "task_text": block.text.strip(),
                        "has_image": True,  # Сравнения обычно визуальные
                        "confidence_score": 0.8,
                        "extraction_method": "comparison_analysis",
                        "comparison_type": pattern
                    })
                    task_num += 1
        
        return tasks
    
    def _extract_combined_block_tasks(self, ocr_page) -> List[Dict[str, Any]]:
        """Комбинированный анализ смежных блоков."""
        tasks = []
        task_num = 1
        
        # Анализируем соседние блоки для составных задач
        for i in range(len(ocr_page.text_blocks) - 1):
            current_block = ocr_page.text_blocks[i]
            next_block = ocr_page.text_blocks[i + 1]
            
            # Проверяем если текущий блок - вопрос, а следующий - ответ или продолжение
            current_text = current_block.text.strip()
            next_text = next_block.text.strip()
            
            if (len(current_text) > 5 and len(next_text) > 5 and
                ('?' in current_text or any(cmd in current_text.lower() for cmd in ['покажи', 'положи', 'найди']))):
                
                combined_text = f"{current_text}\n{next_text}"
                
                tasks.append({
                    "task_number": f"combined-{task_num}",
                    "task_text": combined_text,
                    "has_image": self._has_visual_indicators(combined_text),
                    "confidence_score": 0.75,
                    "extraction_method": "combined_block_analysis",
                    "blocks_combined": [
                        {"par_num": current_block.par_num, "block_num": current_block.block_num},
                        {"par_num": next_block.par_num, "block_num": next_block.block_num}
                    ]
                })
                task_num += 1
        
        return tasks
    
    def _split_into_questions(self, text: str) -> List[str]:
        """Разбивает текст на отдельные вопросы."""
        # Разбиваем по знакам вопроса
        questions = re.split(r'\?+', text)
        
        # Восстанавливаем знаки вопроса и очищаем
        result = []
        for i, q in enumerate(questions[:-1]):  # Последний элемент обычно пустой
            q = q.strip()
            if q:
                result.append(q + '?')
        
        return result
    
    def _extract_full_sentence(self, text: str, start_pos: int) -> str:
        """Извлекает полное предложение от позиции."""
        # Ищем начало предложения (идём назад до точки или начала)
        sentence_start = start_pos
        while sentence_start > 0 and text[sentence_start - 1] not in '.!?\n':
            sentence_start -= 1
        
        # Ищем конец предложения (идём вперёд до точки, вопроса, восклицания)
        sentence_end = start_pos
        while sentence_end < len(text) and text[sentence_end] not in '.!?':
            sentence_end += 1
        
        if sentence_end < len(text):
            sentence_end += 1  # Включаем знак препинания
        
        return text[sentence_start:sentence_end].strip()
    
    def _has_visual_indicators(self, text: str) -> bool:
        """Проверяет есть ли визуальные индикаторы в тексте."""
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in self.visual_keywords)
    
    def _optimize_and_clean_tasks(self, tasks: List[Dict], ocr_page) -> List[Dict]:
        """Оптимизирует и очищает найденные задачи."""
        
        if not tasks:
            # Если задач не найдено, создаём общую задачу из содержимого страницы
            page_text = ocr_page.text.strip()
            if page_text and len(page_text) > 10:
                return [{
                    "task_number": "page-content-1",
                    "task_text": page_text[:500],  # Ограничиваем длину
                    "has_image": self._has_visual_indicators(page_text),
                    "confidence_score": 0.6,
                    "extraction_method": "page_content_fallback",
                    "page_info": {
                        "total_blocks": ocr_page.block_count,
                        "total_words": ocr_page.word_count
                    }
                }]
            else:
                return []
        
        # Удаляем дубликаты по тексту
        seen_texts = set()
        unique_tasks = []
        
        for task in tasks:
            text_normalized = re.sub(r'\s+', ' ', task['task_text'].strip().lower())
            if text_normalized and text_normalized not in seen_texts:
                seen_texts.add(text_normalized)
                unique_tasks.append(task)
        
        # Сортируем по уверенности и качеству
        unique_tasks.sort(key=lambda t: t.get('confidence_score', 0), reverse=True)
        
        # Перенумеровываем задачи
        for i, task in enumerate(unique_tasks, 1):
            task['task_number'] = f"ultimate-{i}"
            
            # Добавляем метаданные OCR
            task.update({
                "page_ocr_confidence": ocr_page.avg_confidence,
                "page_word_count": ocr_page.word_count,
                "page_block_count": ocr_page.block_count,
                "extraction_source": "ocrmypdf_easyocr_gpu",
                "ocr_engine_details": "EasyOCR через OCRmyPDF плагин"
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
            'storage_version': '2.4-ultimate-ocrmypdf-easyocr'
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
def process_textbook_ultimate(ocr_file, output_csv, force, start_page, end_page, production, verbose):
    """
    OCR-OCD Ultimate: Максимально оптимизированная обработка OCRmyPDF-EasyOCR.
    
    Извлекает математические задачи с максимальной точностью и скоростью.
    """
    
    print("🚀📚 OCR-OCD Ultimate: OCRmyPDF-EasyOCR Optimized")
    print("=" * 60)
    print(f"🔍 OCRmyPDF-EasyOCR файл: {ocr_file}")
    print(f"📊 Вывод: {output_csv}")
    print(f"🔄 Force режим: {'✅' if force else '❌'}")
    print(f"⚡ Ultimate Performance: ✅")
    print(f"🎯 EasyOCR через GPU: ✅")
    
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
        'storage': Path("temp/processed_pages_ultimate")
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
        # Инициализация Ultimate экстрактора
        print(f"⚡ Инициализация Ultimate экстрактора...")
        extractor = UltimateTaskExtractor(ocr_file)
        
        # Получаем доступные страницы
        available_pages = extractor.ocr_parser.get_available_pages()
        
        if end_page is None:
            end_page = max(available_pages) if available_pages else start_page
        else:
            end_page = min(end_page, max(available_pages) if available_pages else end_page)
        
        print(f"✅ OCRmyPDF-EasyOCR данные загружены: {len(available_pages)} страниц доступно")
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
        total_extraction_methods = {
            "math_blocks": 0,
            "question_blocks": 0,
            "command_tasks": 0,
            "comparison_tasks": 0,
            "combined_tasks": 0
        }
        
        print(f"\n🚀 Начинаем Ultimate обработку...")
        
        for page_num in range(start_page, end_page + 1):
            page_start_time = time.time()
            
            # Проверяем доступность страницы
            if page_num not in available_pages:
                if verbose:
                    print(f"⏭️  Страница {page_num}: нет OCRmyPDF данных")
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
                
                # Обработка через Ultimate экстрактор
                if verbose:
                    print(f"  ⚡ Ultimate анализ...")
                
                result = extractor.extract_tasks_from_page(page_num)
                
                if 'error' in result:
                    error_count += 1
                    print(f"     ❌ Ошибка: {result['error']}")
                    continue
                
                tasks = result['tasks']
                ocr_stats = result.get('ocr_stats', {})
                extraction_methods = result.get('extraction_methods', {})
                
                # Обновляем статистику методов извлечения
                for method, count in extraction_methods.items():
                    total_extraction_methods[method] += count
                
                if verbose:
                    print(f"  ✅ Ultimate анализ завершён")
                    print(f"  📊 Блоков: {ocr_stats.get('total_blocks', 0)}, "
                          f"Слов: {ocr_stats.get('total_words', 0)}, "
                          f"Confidence: {ocr_stats.get('avg_confidence', 0)}%")
                    print(f"  🔍 Методы: Math={extraction_methods.get('math_blocks', 0)}, "
                          f"Q={extraction_methods.get('question_blocks', 0)}, "
                          f"Cmd={extraction_methods.get('command_tasks', 0)}")
                
                # Сохранение промежуточного результата
                page_result = {
                    'page_number': page_num,
                    'tasks': tasks,
                    'processing_time': result['processing_time'],
                    'ocr_stats': ocr_stats,
                    'extraction_methods': extraction_methods,
                    'api_method': 'ultimate_ocrmypdf_easyocr',
                    'task_count': len(tasks),
                    'full_text': result.get('full_text', '')
                }
                
                storage.save_page_result(page_num, page_result)
                
                processed_count += 1
                total_tasks += len(tasks)
                
                processing_time = time.time() - page_start_time
                print(f"     ✅ Задач: {len(tasks)}, Время: {processing_time:.2f}s")
                
                if verbose and tasks:
                    for i, task in enumerate(tasks[:3], 1):  # Показываем первые 3
                        method = task.get('extraction_method', 'unknown')
                        print(f"       {i}. [{method}] {task['task_number']}: {task['task_text'][:50]}...")
                
                # Оптимальная пауза
                time.sleep(0.05)
                
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
            print(f"📊 Создание Ultimate CSV файла...")
            create_ultimate_csv(all_results, output_csv)
        
        # Детальная статистика
        total_time = (datetime.now() - start_time).total_seconds()
        
        print(f"\n🎉 ULTIMATE ОБРАБОТКА ЗАВЕРШЕНА!")
        print(f"=" * 50)
        print(f"📊 Общая статистика:")
        print(f"   📚 Страниц обработано: {processed_count}")
        print(f"   ⏭️  Страниц пропущено: {skipped_count}")
        print(f"   ❌ Ошибок: {error_count}")
        print(f"   📝 Задач извлечено: {total_tasks}")
        print(f"   💰 Стоимость: $0.00 (бесплатно!)")
        print(f"   ⏱️  Общее время: {total_time:.1f}s ({total_time/60:.1f} минут)")
        if processed_count > 0:
            print(f"   ⚡ Скорость: {processed_count/total_time*60:.1f} страниц/минуту")
            print(f"   📈 Среднее задач/страница: {total_tasks/processed_count:.1f}")
        
        print(f"\n🔍 Статистика методов извлечения:")
        for method, count in total_extraction_methods.items():
            print(f"   • {method}: {count} задач")
        
        print(f"\n📁 Ultimate CSV: {output_csv}")
        print(f"🎯 Качество: OCRmyPDF-EasyOCR через GPU")
        
        return True
        
    except Exception as e:
        logger.error(f"Critical error: {e}")
        print(f"❌ Критическая ошибка: {e}")
        return False


def create_ultimate_csv(results: List[Dict], output_path: str) -> None:
    """Создаёт Ultimate CSV файл из результатов."""
    
    all_tasks = []
    
    for page_result in results:
        page_num = page_result['page_number']
        processing_time = page_result.get('processing_time', 0)
        ocr_stats = page_result.get('ocr_stats', {})
        extraction_methods = page_result.get('extraction_methods', {})
        
        for task_data in page_result.get('tasks', []):
            task_row = {
                'page_number': page_num,
                'task_number': task_data.get('task_number', 'unknown'),
                'task_text': task_data.get('task_text', ''),
                'has_image': task_data.get('has_image', False),
                'confidence_score': task_data.get('confidence_score', 0.0),
                'processing_time': processing_time,
                'api_method': 'ultimate_ocrmypdf_easyocr',
                'extraction_method': task_data.get('extraction_method', 'unknown'),
                'page_ocr_confidence': task_data.get('page_ocr_confidence', 100),
                'page_word_count': task_data.get('page_word_count', 0),
                'page_block_count': task_data.get('page_block_count', 0),
                'extraction_source': task_data.get('extraction_source', 'ocrmypdf_easyocr_gpu'),
                'ocr_engine_details': task_data.get('ocr_engine_details', 'EasyOCR через OCRmyPDF плагин'),
                'extracted_at': page_result.get('processed_at', ''),
                'word_count': len(task_data.get('task_text', '').split()),
                'system_type': 'ultimate_ocrmypdf_easyocr_gpu'
            }
            all_tasks.append(task_row)
    
    # Сортируем по номеру страницы и уверенности
    all_tasks.sort(key=lambda x: (x['page_number'], -x['confidence_score']))
    
    # Записываем CSV
    import csv
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        if all_tasks:
            fieldnames = list(all_tasks[0].keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_tasks)
    
    print(f"✅ Ultimate CSV создан: {len(all_tasks)} задач сохранено")
    print(f"📊 Поля: extraction_method, ocr_engine_details, system_type")


if __name__ == "__main__":
    process_textbook_ultimate() 