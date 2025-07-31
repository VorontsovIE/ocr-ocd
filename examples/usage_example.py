#!/usr/bin/env python3
"""
OCR-OCD Usage Examples
======================

Этот файл содержит примеры использования OCR-OCD для различных сценариев.
"""

import os
import sys
from pathlib import Path

# Добавляем src в Python path для импорта модулей
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.utils.config import load_config
from src.core.pdf_processor import PDFProcessor
from src.core.vision_client import VisionClient
from src.core.data_extractor import DataExtractor
from src.core.csv_writer import CSVWriter
from src.utils.logger import setup_development_logger, get_logger


def example_basic_usage():
    """
    Пример 1: Базовое использование через CLI
    
    Это самый простой способ использования OCR-OCD.
    """
    print("=== Пример 1: Базовое использование ===")
    
    # Команды CLI для копирования в терминал:
    commands = [
        "# Простая обработка одного файла:",
        "python -m src.main textbook.pdf output.csv",
        "",
        "# С подробным выводом:",
        "python -m src.main textbook.pdf output.csv --verbose",
        "",
        "# Возобновление прерванной обработки:",
        "python -m src.main textbook.pdf output.csv --resume",
        "",
        "# Production режим с JSON логированием:",
        "python -m src.main textbook.pdf output.csv --production"
    ]
    
    for cmd in commands:
        print(cmd)


def example_batch_processing():
    """
    Пример 2: Batch обработка нескольких файлов
    
    Как обработать множество PDF файлов автоматически.
    """
    print("\n=== Пример 2: Batch обработка ===")
    
    batch_script = '''#!/bin/bash
# Скрипт для обработки всех PDF файлов в директории

INPUT_DIR="./textbooks"
OUTPUT_DIR="./results"

# Создаём выходную директорию
mkdir -p "$OUTPUT_DIR"

# Обрабатываем каждый PDF файл
for pdf_file in "$INPUT_DIR"/*.pdf; do
    if [ -f "$pdf_file" ]; then
        filename=$(basename "$pdf_file" .pdf)
        output_file="$OUTPUT_DIR/${filename}_tasks.csv"
        
        echo "Обрабатываем: $pdf_file -> $output_file"
        
        python -m src.main "$pdf_file" "$output_file" --verbose --resume
        
        # Проверяем успешность обработки
        if [ $? -eq 0 ]; then
            echo "✅ Успешно обработан: $filename"
        else
            echo "❌ Ошибка при обработке: $filename"
        fi
        
        echo "---"
    fi
done

echo "Batch обработка завершена!"
'''
    
    print("Сохраните следующий скрипт как process_all.sh:")
    print(batch_script)


def example_python_api():
    """
    Пример 3: Использование через Python API
    
    Для интеграции в другие Python приложения.
    """
    print("\n=== Пример 3: Python API ===")
    
    # Настройка логирования
    setup_development_logger()
    logger = get_logger(__name__)
    
    print("# Пример кода для интеграции:")
    
    example_code = '''
import sys
from pathlib import Path

# Добавляем src в path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.main import OCROCDOrchestrator
from src.utils.config import load_config
from src.utils.logger import setup_development_logger

def process_textbook(pdf_path: str, csv_path: str) -> bool:
    """Обработка одного учебника через Python API."""
    
    try:
        # Настройка
        config = load_config()
        setup_development_logger()
        
        # Создание оркестратора
        orchestrator = OCROCDOrchestrator(config)
        
        # Настройка компонентов
        if not orchestrator.setup_components(pdf_path, csv_path):
            print("❌ Ошибка настройки компонентов")
            return False
        
        # Обработка
        print(f"🚀 Начинаем обработку {pdf_path}")
        result = orchestrator.process_pdf(resume=True)
        
        # Результаты
        summary = result["summary"]
        print(f"✅ Обработано страниц: {summary['successful_pages']}/{summary['total_pages']}")
        print(f"📊 Извлечено задач: {summary['total_tasks']}")
        print(f"⏱️ Время обработки: {summary['processing_duration_seconds']:.1f}s")
        
        # Cleanup
        orchestrator.cleanup()
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

# Использование
if __name__ == "__main__":
    success = process_textbook("textbook.pdf", "output.csv")
    if success:
        print("🎉 Обработка завершена успешно!")
    else:
        print("💥 Произошла ошибка")
'''
    
    print(example_code)


def example_advanced_configuration():
    """
    Пример 4: Продвинутая конфигурация
    
    Настройка параметров для specific use cases.
    """
    print("\n=== Пример 4: Продвинутая конфигурация ===")
    
    env_example = '''
# .env файл с продвинутыми настройками

# Обязательные настройки
OPENAI_API_KEY=your_api_key_here

# API конфигурация
OPENAI_MODEL=gpt-4-vision-preview
OPENAI_MAX_TOKENS=4096
OPENAI_TEMPERATURE=0.1          # Для стабильности ответов
OPENAI_TIMEOUT=120              # Увеличенный timeout для сложных страниц
OPENAI_MAX_RETRIES=5            # Больше попыток для reliability

# Директории
OUTPUT_DIR=./results
TEMP_DIR=./temp                 # SSD для быстрой обработки
LOGS_DIR=./logs

# Логирование
LOG_LEVEL=INFO                  # DEBUG для отладки
LOG_MAX_FILE_SIZE=50MB
LOG_RETENTION_DAYS=30

# Performance настройки
PDF_DPI=300                     # Качество изображений
PDF_MAX_DIMENSION=2048          # Баланс качества/скорости
VISION_BATCH_SIZE=1             # Количество одновременных API calls
'''
    
    print("Пример .env файла с продвинутыми настройками:")
    print(env_example)


def example_quality_analysis():
    """
    Пример 5: Анализ качества результатов
    
    Как анализировать и улучшать качество извлечения.
    """
    print("\n=== Пример 5: Анализ качества ===")
    
    analysis_code = '''
import pandas as pd
import matplotlib.pyplot as plt

def analyze_extraction_quality(csv_path: str):
    """Анализ качества извлеченных данных."""
    
    # Загрузка данных
    df = pd.read_csv(csv_path)
    
    print(f"📊 Общая статистика:")
    print(f"   Всего задач: {len(df)}")
    print(f"   Страниц: {df['page_number'].nunique()}")
    print(f"   Задач на страницу: {len(df) / df['page_number'].nunique():.1f}")
    
    # Анализ confidence scores
    if 'confidence_score' in df.columns:
        avg_confidence = df['confidence_score'].mean()
        high_confidence = (df['confidence_score'] > 0.8).sum()
        
        print(f"\\n🎯 Качество распознавания:")
        print(f"   Средний confidence: {avg_confidence:.3f}")
        print(f"   Высокий confidence (>0.8): {high_confidence}/{len(df)} ({high_confidence/len(df)*100:.1f}%)")
    
    # Анализ номеров задач
    unknown_tasks = df['task_number'].str.startswith('unknown-').sum()
    print(f"\\n🔢 Анализ нумерации:")
    print(f"   Unknown номера: {unknown_tasks}/{len(df)} ({unknown_tasks/len(df)*100:.1f}%)")
    
    # Анализ изображений
    with_images = df['has_image'].sum()
    print(f"\\n🖼️ Изображения:")
    print(f"   Задач с изображениями: {with_images}/{len(df)} ({with_images/len(df)*100:.1f}%)")
    
    # Анализ длины текста
    if 'word_count' in df.columns:
        avg_words = df['word_count'].mean()
        print(f"\\n📝 Текст:")
        print(f"   Среднее количество слов: {avg_words:.1f}")
        
        # Поиск потенциально проблемных задач
        short_tasks = (df['word_count'] < 3).sum()
        long_tasks = (df['word_count'] > 50).sum()
        
        print(f"   Короткие задачи (<3 слов): {short_tasks}")
        print(f"   Длинные задачи (>50 слов): {long_tasks}")
    
    return df

# Использование
df = analyze_extraction_quality("output.csv")

# Дополнительный анализ по страницам
page_stats = df.groupby('page_number').agg({
    'task_number': 'count',
    'confidence_score': 'mean',
    'has_image': 'sum'
}).round(3)

print("\\n📄 Статистика по страницам:")
print(page_stats.head(10))
'''
    
    print("Пример кода для анализа качества:")
    print(analysis_code)


def example_troubleshooting():
    """
    Пример 6: Решение проблем
    
    Частые проблемы и их решения.
    """
    print("\n=== Пример 6: Решение проблем ===")
    
    troubleshooting = '''
🔧 Частые проблемы и решения:

1. "ModuleNotFoundError: No module named 'src'"
   Решение: Запускайте из корневой директории проекта
   ✅ python -m src.main input.pdf output.csv

2. "OpenAI API key not found"
   Решение: Проверьте .env файл
   ✅ echo "OPENAI_API_KEY=your_key" > .env

3. "Rate limit exceeded"
   Решение: Система автоматически повторяет запросы
   ✅ Используйте --resume для продолжения

4. "PDF processing failed"
   Решение: Проверьте формат и права доступа
   ✅ file textbook.pdf  # Проверка формата
   ✅ ls -la textbook.pdf  # Права доступа

5. Низкое качество распознавания
   Решение: Проверьте качество исходного PDF
   ✅ Увеличьте DPI: PDF_DPI=400 в .env
   ✅ Проверьте логи: tail -f logs/ocr_ocd.log

6. Медленная обработка
   Решение: Оптимизация настроек
   ✅ Уменьшите разрешение: PDF_MAX_DIMENSION=1500
   ✅ Используйте SSD для TEMP_DIR
   ✅ Проверьте интернет-соединение

🚨 Экстренное восстановление:
   # Если обработка прервалась, можно продолжить:
   python -m src.main input.pdf output.csv --resume
   
   # Если состояние повреждено, очистите и начните заново:
   rm -f temp/processing_state.json
   python -m src.main input.pdf output.csv

📊 Мониторинг прогресса:
   # В отдельном терминале:
   tail -f logs/ocr_ocd.log | grep "Page.*processed"
   
   # Проверка размера выходного файла:
   watch -n 5 'wc -l output.csv'
'''
    
    print(troubleshooting)


def main():
    """Главная функция с примерами использования."""
    
    print("🔍📚 OCR-OCD Usage Examples")
    print("=" * 50)
    print("Примеры использования OCR-OCD для извлечения задач из PDF учебников")
    print()
    
    # Выполняем все примеры
    example_basic_usage()
    example_batch_processing()
    example_python_api()
    example_advanced_configuration()
    example_quality_analysis()
    example_troubleshooting()
    
    print("\n" + "=" * 50)
    print("🎉 Все примеры показаны!")
    print("💡 Начните с простого: python -m src.main input.pdf output.csv")
    print("📚 Полная документация в README.md")


if __name__ == "__main__":
    main() 