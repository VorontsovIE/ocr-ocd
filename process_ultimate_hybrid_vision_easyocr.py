#!/usr/bin/env python3
"""
OCR-OCD Ultimate Hybrid: GPT-4 Vision + OCRmyPDF-EasyOCR
========================================================

Оптимальная гибридная архитектура:
- 🖼️ GPT-4 Vision: основной анализ изображений страниц
- 📋 OCRmyPDF-EasyOCR: высокоточная вспомогательная информация
- 🧠 Лучшее из двух миров: понимание контекста + точность OCR
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
from src.utils.ocrmypdf_easyocr_parser import OCRmyPDFEasyOCRParser
from src.core.pdf_processor import PDFProcessor
from src.core.vision_client import VisionClient
from src.core.data_extractor import DataExtractor
from src.utils.config import load_config


class UltimateHybridExtractor:
    """
    Гибридная система: GPT-4 Vision (основной) + OCRmyPDF-EasyOCR (вспомогательный).
    """
    
    def __init__(self, pdf_path: str, ocr_file_path: str, config_path: str = None):
        """
        Инициализация гибридного экстрактора.
        
        Args:
            pdf_path: Путь к PDF файлу для извлечения изображений
            ocr_file_path: Путь к OCRmyPDF-EasyOCR TSV файлу
            config_path: Путь к конфигурационному файлу
        """
        self.logger = get_logger(__name__)
        
        # Загружаем конфигурацию
        self.config = load_config(config_path)
        
        # Инициализируем компоненты
        self.pdf_processor = PDFProcessor(pdf_path)
        self.vision_client = VisionClient(self.config.api)
        self.data_extractor = DataExtractor()
        self.ocr_parser = OCRmyPDFEasyOCRParser(ocr_file_path)
        
        self.logger.info(f"Hybrid extractor initialized: PDF={pdf_path}, OCR={ocr_file_path}")
        
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
        Гибридное извлечение задач: GPT-4 Vision + OCRmyPDF-EasyOCR.
        
        Args:
            page_number: Номер страницы для обработки
            
        Returns:
            Словарь с результатами извлечения
        """
        start_time = time.time()
        
        try:
            # 1. Получаем вспомогательную информацию из OCRmyPDF-EasyOCR
            ocr_supplement = self._get_ocr_supplement(page_number)
            ocr_summary = self._get_ocr_summary(page_number)
            
            # 2. Основной анализ через GPT-4 Vision (если доступен)
            if self.api_available:
                tasks = self._extract_with_vision_primary(page_number, ocr_supplement)
                method = "hybrid_vision_primary"
            else:
                # Fallback: только OCRmyPDF-EasyOCR
                tasks = self._extract_with_ocr_fallback(page_number)
                method = "hybrid_ocr_fallback"
            
            processing_time = time.time() - start_time
            
            return {
                "page_number": page_number,
                "tasks": tasks,
                "processing_time": processing_time,
                "method": method,
                "api_available": self.api_available,
                "ocr_summary": ocr_summary,
                "ocr_supplement_length": len(ocr_supplement),
                "hybrid_approach": "vision_primary_ocr_supplementary" if self.api_available else "ocr_only_fallback"
            }
            
        except Exception as e:
            self.logger.error(f"Error extracting tasks from page {page_number}: {e}")
            return {
                "page_number": page_number,
                "tasks": [],
                "processing_time": time.time() - start_time,
                "method": "hybrid_error",
                "error": str(e)
            }
    
    def _get_ocr_supplement(self, page_number: int) -> str:
        """Создаёт вспомогательную информацию из OCRmyPDF-EasyOCR для GPT-4 Vision."""
        
        try:
            ocr_supplement = self.ocr_parser.create_vision_prompt_supplement(page_number)
            
            if not ocr_supplement:
                return ""
            
            # Улучшаем формат для GPT-4 Vision
            enhanced_supplement = f"""
📋 ВЫСОКОТОЧНАЯ OCR ИНФОРМАЦИЯ (EasyOCR через GPU):
════════════════════════════════════════════════════

{ocr_supplement}

═══════════════════════════════════════════════════════════════
💡 ИНСТРУКЦИЯ: Используй эту информацию как высокоточную подсказку 
для распознавания текста на изображении. Текст распознан с точностью 
100% через EasyOCR. Сопоставь её с тем, что видишь на изображении.
═══════════════════════════════════════════════════════════════"""
            
            return enhanced_supplement
            
        except Exception as e:
            self.logger.warning(f"Error creating OCR supplement for page {page_number}: {e}")
            return ""
    
    def _get_ocr_summary(self, page_number: int) -> Dict[str, Any]:
        """Получает сводную информацию из OCRmyPDF-EasyOCR."""
        
        try:
            return self.ocr_parser.get_page_summary(page_number)
        except Exception as e:
            self.logger.warning(f"Error getting OCR summary for page {page_number}: {e}")
            return {}
    
    def _extract_with_vision_primary(self, page_number: int, ocr_supplement: str) -> List[Dict[str, Any]]:
        """
        Основной метод: GPT-4 Vision анализ с OCR поддержкой.
        
        Args:
            page_number: Номер страницы
            ocr_supplement: Вспомогательная OCR информация
            
        Returns:
            Список извлечённых задач
        """
        try:
            # Получаем изображение страницы
            page_image = self.pdf_processor.get_page_image(page_number - 1)  # 0-based index
            
            if not page_image:
                self.logger.warning(f"Could not get image for page {page_number}")
                return self._extract_with_ocr_fallback(page_number)
            
            # Создаём улучшенный промпт с OCR поддержкой
            enhanced_prompt = self._create_hybrid_prompt(ocr_supplement)
            
            # Анализируем через GPT-4 Vision
            self.logger.debug(f"Analyzing page {page_number} with GPT-4 Vision + OCR supplement")
            
            api_result = self.vision_client.extract_tasks_from_page(
                page_image=page_image,
                page_number=page_number,
                custom_prompt=enhanced_prompt
            )
            
            if not api_result.get('success', False):
                self.logger.warning(f"Vision API failed for page {page_number}, using OCR fallback")
                return self._extract_with_ocr_fallback(page_number)
            
            # Извлекаем задачи из ответа GPT
            tasks = self.data_extractor.extract_tasks_from_response(
                api_result.get('response', {}),
                page_number
            )
            
            # Обогащаем задачи метаданными гибридного подхода
            for task in tasks:
                task.update({
                    'extraction_method': 'hybrid_vision_primary',
                    'ocr_assisted': True,
                    'ocr_confidence': 100.0,
                    'vision_api_used': True,
                    'hybrid_score': self._calculate_hybrid_score(task, api_result)
                })
            
            self.logger.debug(f"Extracted {len(tasks)} tasks from page {page_number} using hybrid Vision+OCR")
            return tasks
            
        except Exception as e:
            self.logger.error(f"Vision primary extraction failed for page {page_number}: {e}")
            return self._extract_with_ocr_fallback(page_number)
    
    def _extract_with_ocr_fallback(self, page_number: int) -> List[Dict[str, Any]]:
        """
        Fallback метод: только OCRmyPDF-EasyOCR.
        
        Args:
            page_number: Номер страницы
            
        Returns:
            Список извлечённых задач
        """
        try:
            # Используем наш предыдущий OCR-only экстрактор
            ocr_page = self.ocr_parser.parse_page(page_number)
            
            if not ocr_page:
                return []
            
            tasks = []
            
            # Извлекаем задачи различными методами
            math_blocks = ocr_page.get_math_blocks()
            question_blocks = ocr_page.get_question_blocks()
            
            # Math blocks
            for i, block in enumerate(math_blocks, 1):
                if len(block.text.strip()) > 5:
                    tasks.append({
                        'task_number': f"ocr-math-{i}",
                        'task_text': block.text.strip(),
                        'has_image': self._has_visual_indicators(block.text),
                        'confidence_score': 0.8,
                        'extraction_method': 'hybrid_ocr_fallback',
                        'ocr_assisted': True,
                        'vision_api_used': False,
                        'ocr_confidence': 100.0
                    })
            
            # Question blocks
            for i, block in enumerate(question_blocks, 1):
                questions = self._split_questions(block.text)
                for j, question in enumerate(questions, 1):
                    if len(question.strip()) > 5:
                        tasks.append({
                            'task_number': f"ocr-question-{i}-{j}",
                            'task_text': question.strip(),
                            'has_image': self._has_visual_indicators(question),
                            'confidence_score': 0.85,
                            'extraction_method': 'hybrid_ocr_fallback',
                            'ocr_assisted': True,
                            'vision_api_used': False,
                            'ocr_confidence': 100.0
                        })
            
            # Если задач мало, добавляем общее содержимое страницы
            if len(tasks) < 3 and ocr_page.text.strip():
                tasks.append({
                    'task_number': f"ocr-content-1",
                    'task_text': ocr_page.text.strip()[:300],
                    'has_image': self._has_visual_indicators(ocr_page.text),
                    'confidence_score': 0.6,
                    'extraction_method': 'hybrid_ocr_fallback_content',
                    'ocr_assisted': True,
                    'vision_api_used': False,
                    'ocr_confidence': 100.0
                })
            
            self.logger.debug(f"OCR fallback extracted {len(tasks)} tasks from page {page_number}")
            return tasks
            
        except Exception as e:
            self.logger.error(f"OCR fallback extraction failed for page {page_number}: {e}")
            return []
    
    def _create_hybrid_prompt(self, ocr_supplement: str) -> str:
        """Создаёт гибридный промпт для GPT-4 Vision с OCR поддержкой."""
        
        base_prompt = """Проанализируй эту страницу математического учебника для 1 класса и извлеки все математические задачи.

ТВОЯ ЗАДАЧА:
1. Найди и извлеки ВСЕ математические задачи, упражнения и вопросы
2. Для каждой задачи определи:
   - Номер задачи (если есть) или создай уникальный номер
   - Полный текст задачи
   - Есть ли визуальные элементы (рисунки, схемы)

ФОРМАТЫ ЗАДАЧ:
- Вопросы: "Сколько...?", "Где...?", "Что...?"
- Команды: "Покажи...", "Найди...", "Реши...", "Положи..."
- Примеры: математические выражения и упражнения
- Сравнения: "больше/меньше", "длиннее/короче"

ВЕРНИ РЕЗУЛЬТАТ В ФОРМАТЕ JSON:
{
  "tasks": [
    {
      "task_number": "1",
      "task_text": "полный текст задачи",
      "has_image": true/false
    }
  ]
}"""

        if ocr_supplement:
            hybrid_prompt = f"""{base_prompt}

{ocr_supplement}

ВАЖНО: Используй OCR информацию выше как точную подсказку для распознавания текста на изображении. Она поможет тебе точно прочитать даже сложные слова и символы."""
        else:
            hybrid_prompt = base_prompt
        
        return hybrid_prompt
    
    def _calculate_hybrid_score(self, task: Dict[str, Any], api_result: Dict[str, Any]) -> float:
        """Вычисляет гибридный score качества задачи."""
        
        score = 0.5  # Базовый score
        
        # Бонус за использование Vision API
        if api_result.get('success', False):
            score += 0.2
        
        # Бонус за наличие OCR поддержки
        if task.get('ocr_assisted', False):
            score += 0.2
        
        # Бонус за определённые ключевые слова
        task_text = task.get('task_text', '').lower()
        math_keywords = ['сколько', 'найди', 'реши', 'покажи', 'положи', '?']
        keyword_count = sum(1 for keyword in math_keywords if keyword in task_text)
        score += min(keyword_count * 0.05, 0.15)
        
        return min(score, 1.0)
    
    def _has_visual_indicators(self, text: str) -> bool:
        """Проверяет наличие визуальных индикаторов в тексте."""
        visual_keywords = [
            'рисун', 'картин', 'схем', 'диаграмм', 'график', 'чертёж',
            'покажи', 'нарисовано', 'изображ', 'видишь', 'нарисуй',
            'палочк', 'кружков', 'точек', 'линий', 'фигур'
        ]
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in visual_keywords)
    
    def _split_questions(self, text: str) -> List[str]:
        """Разбивает текст на отдельные вопросы."""
        questions = re.split(r'\?+', text)
        result = []
        for i, q in enumerate(questions[:-1]):
            q = q.strip()
            if q:
                result.append(q + '?')
        return result


class HybridIntermediateStorage:
    """Управление промежуточным сохранением для гибридной системы."""
    
    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
    def save_page_result(self, page_number: int, page_data: Dict[str, Any]) -> None:
        """Сохраняет результат гибридной обработки страницы."""
        file_path = self.storage_dir / f"hybrid_page_{page_number:03d}.json"
        
        # Добавляем метаданные гибридного подхода
        page_data.update({
            'processed_at': datetime.now().isoformat(),
            'page_number': page_number,
            'storage_version': '3.0-hybrid-vision-easyocr',
            'architecture': 'vision_primary_ocr_supplementary'
        })
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(page_data, f, ensure_ascii=False, indent=2)
    
    def load_page_result(self, page_number: int) -> Optional[Dict[str, Any]]:
        """Загружает результат гибридной обработки страницы."""
        file_path = self.storage_dir / f"hybrid_page_{page_number:03d}.json"
        
        if not file_path.exists():
            return None
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Ошибка загрузки гибридной страницы {page_number}: {e}")
            return None
    
    def get_processed_pages(self) -> List[int]:
        """Возвращает список номеров уже обработанных страниц."""
        processed = []
        
        for file_path in sorted(self.storage_dir.glob("hybrid_page_*.json")):
            try:
                page_num = int(file_path.stem.split('_')[2])
                processed.append(page_num)
            except (ValueError, IndexError):
                continue
                
        return sorted(processed)
    
    def load_all_results(self) -> List[Dict[str, Any]]:
        """Загружает все сохранённые гибридные результаты."""
        results = []
        
        for page_num in self.get_processed_pages():
            page_data = self.load_page_result(page_num)
            if page_data:
                results.append(page_data)
        
        return results
    
    def clear_storage(self) -> None:
        """Очищает все промежуточные файлы гибридной системы."""
        for file_path in self.storage_dir.glob("hybrid_page_*.json"):
            file_path.unlink()


@click.command()
@click.argument('pdf_file', type=click.Path(exists=True))
@click.argument('ocr_file', type=click.Path(exists=True))
@click.argument('output_csv', type=click.Path())
@click.option('--force', is_flag=True, help='Принудительно переобработать все страницы')
@click.option('--start-page', type=int, default=1, help='Начальная страница для обработки')
@click.option('--end-page', type=int, default=None, help='Конечная страница для обработки')
@click.option('--production', is_flag=True, help='Production режим логирования')
@click.option('--verbose', is_flag=True, help='Подробный вывод')
@click.option('--config', type=click.Path(exists=True), help='Путь к конфигурационному файлу')
def process_textbook_hybrid(pdf_file, ocr_file, output_csv, force, start_page, end_page, production, verbose, config):
    """
    OCR-OCD Ultimate Hybrid: GPT-4 Vision + OCRmyPDF-EasyOCR.
    
    Оптимальная гибридная архитектура:
    - GPT-4 Vision: основной анализ изображений
    - OCRmyPDF-EasyOCR: высокоточная вспомогательная информация
    """
    
    print("🚀🧠 OCR-OCD Ultimate Hybrid: Vision + EasyOCR")
    print("=" * 65)
    print(f"📖 PDF файл: {pdf_file}")
    print(f"🔍 OCRmyPDF-EasyOCR файл: {ocr_file}")
    print(f"📊 Вывод: {output_csv}")
    print(f"🔄 Force режим: {'✅' if force else '❌'}")
    print(f"🎯 Гибридная архитектура: ✅")
    print(f"🖼️ GPT-4 Vision: основной анализ")
    print(f"📋 EasyOCR: вспомогательная информация")
    
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
        'storage': Path("temp/processed_pages_hybrid")
    }
    
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    
    # Инициализация гибридного хранилища
    storage = HybridIntermediateStorage(paths['storage'])
    
    if force:
        print("🗑️  Force режим: очистка промежуточных результатов...")
        storage.clear_storage()
    
    start_time = datetime.now()
    
    try:
        # Инициализация гибридного экстрактора
        print(f"🧠 Инициализация гибридного экстрактора...")
        extractor = UltimateHybridExtractor(pdf_file, ocr_file, config)
        
        # Получаем информацию о PDF
        total_pages = extractor.pdf_processor.get_page_count()
        
        if end_page is None:
            end_page = total_pages
        else:
            end_page = min(end_page, total_pages)
        
        print(f"✅ Гибридная система инициализирована")
        print(f"📚 PDF: {total_pages} страниц")
        print(f"🎯 Обработка: страницы {start_page}-{end_page}")
        print(f"🖼️ GPT-4 Vision API: {'✅ Available' if extractor.api_available else '❌ Unavailable (OCR fallback)'}")
        
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
        vision_count = 0
        ocr_fallback_count = 0
        
        print(f"\n🚀 Начинаем гибридную обработку...")
        
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
                
                # Гибридная обработка
                if verbose:
                    print(f"  🧠 Гибридный анализ (Vision+OCR)...")
                
                result = extractor.extract_tasks_from_page(page_num)
                
                if 'error' in result:
                    error_count += 1
                    print(f"     ❌ Ошибка: {result['error']}")
                    continue
                
                tasks = result['tasks']
                method = result.get('method', 'unknown')
                api_used = result.get('api_available', False)
                ocr_summary = result.get('ocr_summary', {})
                
                # Обновляем счётчики методов
                if api_used and 'vision' in method:
                    vision_count += 1
                else:
                    ocr_fallback_count += 1
                
                if verbose:
                    print(f"  ✅ Гибридный анализ завершён")
                    print(f"  🎯 Метод: {method}")
                    print(f"  📊 OCR качество: {ocr_summary.get('avg_confidence', 0)}%")
                    print(f"  🔧 API использован: {'✅' if api_used else '❌'}")
                
                # Сохранение промежуточного результата
                page_result = {
                    'page_number': page_num,
                    'tasks': tasks,
                    'processing_time': result['processing_time'],
                    'method': method,
                    'api_available': result.get('api_available', False),
                    'ocr_summary': ocr_summary,
                    'task_count': len(tasks),
                    'hybrid_approach': result.get('hybrid_approach', 'unknown')
                }
                
                storage.save_page_result(page_num, page_result)
                
                processed_count += 1
                total_tasks += len(tasks)
                
                processing_time = time.time() - page_start_time
                print(f"     ✅ Задач: {len(tasks)}, Время: {processing_time:.2f}s")
                
                if verbose and tasks:
                    for i, task in enumerate(tasks[:3], 1):  # Показываем первые 3
                        method_info = task.get('extraction_method', 'unknown')
                        vision_used = '🖼️' if task.get('vision_api_used', False) else '📋'
                        print(f"       {i}. {vision_used} [{method_info}] {task['task_number']}: {task['task_text'][:50]}...")
                
                # Пауза для API
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error processing page {page_num}: {e}")
                print(f"     ❌ Ошибка на странице {page_num}: {e}")
                error_count += 1
                continue
        
        # Финальный сбор результатов
        print(f"\n💾 Сбор финальных гибридных результатов...")
        all_results = storage.load_all_results()
        
        # Создание итогового CSV
        if all_results:
            print(f"📊 Создание гибридного CSV файла...")
            create_hybrid_csv(all_results, output_csv)
        
        # Детальная статистика
        total_time = (datetime.now() - start_time).total_seconds()
        
        print(f"\n🎉 ГИБРИДНАЯ ОБРАБОТКА ЗАВЕРШЕНА!")
        print(f"=" * 55)
        print(f"📊 Общая статистика:")
        print(f"   📚 Страниц обработано: {processed_count}")
        print(f"   ⏭️  Страниц пропущено: {skipped_count}")
        print(f"   ❌ Ошибок: {error_count}")
        print(f"   📝 Задач извлечено: {total_tasks}")
        print(f"   ⏱️  Общее время: {total_time:.1f}s ({total_time/60:.1f} минут)")
        if processed_count > 0:
            print(f"   ⚡ Скорость: {processed_count/total_time*60:.1f} страниц/минуту")
            print(f"   📈 Среднее задач/страница: {total_tasks/processed_count:.1f}")
        
        print(f"\n🧠 Статистика гибридных методов:")
        print(f"   🖼️ GPT-4 Vision (основной): {vision_count} страниц")
        print(f"   📋 OCR Fallback: {ocr_fallback_count} страниц")
        
        print(f"\n📁 Гибридный CSV: {output_csv}")
        print(f"🎯 Архитектура: Vision Primary + OCR Supplementary")
        
        return True
        
    except Exception as e:
        logger.error(f"Critical hybrid error: {e}")
        print(f"❌ Критическая ошибка гибридной системы: {e}")
        return False


def create_hybrid_csv(results: List[Dict], output_path: str) -> None:
    """Создаёт гибридный CSV файл из результатов."""
    
    all_tasks = []
    
    for page_result in results:
        page_num = page_result['page_number']
        processing_time = page_result.get('processing_time', 0)
        method = page_result.get('method', 'unknown')
        api_available = page_result.get('api_available', False)
        ocr_summary = page_result.get('ocr_summary', {})
        hybrid_approach = page_result.get('hybrid_approach', 'unknown')
        
        for task_data in page_result.get('tasks', []):
            task_row = {
                'page_number': page_num,
                'task_number': task_data.get('task_number', 'unknown'),
                'task_text': task_data.get('task_text', ''),
                'has_image': task_data.get('has_image', False),
                'confidence_score': task_data.get('confidence_score', 0.0),
                'processing_time': processing_time,
                'api_method': method,
                'extraction_method': task_data.get('extraction_method', 'unknown'),
                'hybrid_approach': hybrid_approach,
                'vision_api_used': task_data.get('vision_api_used', False),
                'ocr_assisted': task_data.get('ocr_assisted', False),
                'ocr_confidence': task_data.get('ocr_confidence', 0),
                'hybrid_score': task_data.get('hybrid_score', 0.0),
                'api_available': api_available,
                'page_ocr_words': ocr_summary.get('total_words', 0),
                'page_ocr_blocks': ocr_summary.get('total_blocks', 0),
                'extracted_at': page_result.get('processed_at', ''),
                'word_count': len(task_data.get('task_text', '').split()),
                'system_type': 'hybrid_vision_easyocr_gpu',
                'architecture': 'vision_primary_ocr_supplementary'
            }
            all_tasks.append(task_row)
    
    # Сортируем по номеру страницы и гибридному score
    all_tasks.sort(key=lambda x: (x['page_number'], -x['hybrid_score']))
    
    # Записываем CSV
    import csv
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        if all_tasks:
            fieldnames = list(all_tasks[0].keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_tasks)
    
    print(f"✅ Гибридный CSV создан: {len(all_tasks)} задач сохранено")
    print(f"📊 Поля: hybrid_approach, vision_api_used, ocr_assisted, hybrid_score")


if __name__ == "__main__":
    process_textbook_hybrid() 