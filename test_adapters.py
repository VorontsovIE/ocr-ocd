#!/usr/bin/env python3
"""
Тестовый скрипт для проверки мультимодальных адаптеров
"""

import sys
from pathlib import Path
from PIL import Image
import io

# Добавляем src в Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.core.vision_adapters import VisionAdapterFactory, VisionProvider
from src.utils.config import load_config, get_available_providers
from src.utils.logger import setup_development_logger


def create_test_image():
    """Создает тестовое изображение с текстом"""
    # Создаем простое изображение с текстом
    img = Image.new('RGB', (400, 200), color='white')
    
    # Добавляем текст (в реальном приложении это будет математическая задача)
    from PIL import ImageDraw, ImageFont
    
    draw = ImageDraw.Draw(img)
    try:
        # Попробуем использовать системный шрифт
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
    except:
        # Fallback на стандартный шрифт
        font = ImageFont.load_default()
    
    text = "Задача 1: Решите уравнение 2x + 5 = 13"
    draw.text((20, 50), text, fill='black', font=font)
    
    text2 = "Задача 2: Найдите площадь круга радиусом 5 см"
    draw.text((20, 100), text2, fill='black', font=font)
    
    # Сохраняем в bytes
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()


def test_provider(provider: VisionProvider, config):
    """Тестирует конкретного провайдера"""
    print(f"\n🧪 Тестирование {provider.value.upper()}...")
    
    try:
        # Создаем адаптер
        adapter = VisionAdapterFactory.create_adapter(provider, config.api)
        
        # Тестируем подключение
        test_result = adapter.test_connection()
        
        if test_result.get("status") == "success":
            print(f"✅ {provider.value.upper()} подключение успешно")
            print(f"   Модель: {test_result.get('model_used')}")
            print(f"   Время ответа: {test_result.get('processing_time', 0):.2f}с")
            
            # Тестируем анализ изображения
            test_image = create_test_image()
            prompt = """
            Анализируй это изображение и найди математические задачи.
            
            Структурируй ответ в JSON формате:
            {
                "tasks": [
                    {
                        "number": "номер задачи",
                        "text": "полный текст задачи",
                        "type": "тип задачи",
                        "difficulty": "уровень сложности"
                    }
                ]
            }
            """
            
            result = adapter.extract_tasks_from_page(
                image_data=test_image,
                page_number=1,
                prompt=prompt
            )
            
            if result.get("tasks"):
                print(f"✅ Найдено {len(result['tasks'])} задач")
                for task in result["tasks"]:
                    print(f"   📝 {task.get('number', 'N/A')}: {task.get('text', 'N/A')[:50]}...")
            else:
                print("⚠️  Задачи не найдены")
                
        else:
            print(f"❌ {provider.value.upper()} ошибка подключения: {test_result.get('error')}")
            
    except Exception as e:
        print(f"❌ {provider.value.upper()} ошибка: {e}")


def main():
    """Основная функция тестирования"""
    print("🚀 Тестирование мультимодальных адаптеров")
    print("=" * 50)
    
    # Настройка логирования
    setup_development_logger()
    
    try:
        # Загружаем конфигурацию
        config = load_config()
        
        # Показываем доступные провайдеры
        available_providers = get_available_providers()
        print(f"📋 Доступные провайдеры: {[p.value for p in available_providers]}")
        print(f"🎯 Провайдер по умолчанию: {config.api.provider.value}")
        print(f"🔧 Модель: {config.api.model_name}")
        
        # Тестируем каждого доступного провайдера
        for provider in available_providers:
            test_provider(provider, config)
        
        print("\n" + "=" * 50)
        print("✅ Тестирование завершено!")
        
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main()) 