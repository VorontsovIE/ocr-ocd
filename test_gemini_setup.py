#!/usr/bin/env python3
"""
Тестовый скрипт для проверки настройки Gemini API
"""

import sys
import os
from pathlib import Path

# Добавляем src в Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv
from src.utils.config import load_config, get_available_providers
from src.core.vision_adapters import VisionAdapterFactory, VisionProvider
from src.utils.logger import setup_development_logger


def test_gemini_setup():
    """Тестирует настройку Gemini API"""
    print("🔍 Проверка настройки Gemini API")
    print("=" * 40)
    
    # Загружаем переменные окружения
    load_dotenv()
    
    # Проверяем наличие API ключа
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        print("❌ GEMINI_API_KEY не найден в .env файле")
        return False
    
    print(f"✅ GEMINI_API_KEY найден: {gemini_key[:10]}...")
    
    # Проверяем доступные провайдеры
    try:
        available_providers = get_available_providers()
        print(f"📋 Доступные провайдеры: {[p.value for p in available_providers]}")
        
        if VisionProvider.GEMINI in available_providers:
            print("✅ Gemini доступен в списке провайдеров")
        else:
            print("❌ Gemini НЕ доступен в списке провайдеров")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка при проверке провайдеров: {e}")
        return False
    
    # Загружаем конфигурацию
    try:
        config = load_config()
        print(f"🎯 Провайдер по умолчанию: {config.api.provider.value}")
        print(f"🔧 Модель: {config.api.model_name}")
        
        if config.api.provider == VisionProvider.GEMINI:
            print("✅ Gemini выбран как провайдер по умолчанию")
        else:
            print(f"⚠️  Провайдер по умолчанию: {config.api.provider.value}")
            
    except Exception as e:
        print(f"❌ Ошибка при загрузке конфигурации: {e}")
        return False
    
    # Тестируем создание адаптера
    try:
        adapter = VisionAdapterFactory.create_adapter(VisionProvider.GEMINI, config.api)
        print("✅ Адаптер Gemini создан успешно")
        
        # Тестируем подключение
        test_result = adapter.test_connection()
        
        if test_result.get("status") == "success":
            print("✅ Подключение к Gemini API успешно")
            print(f"   Модель: {test_result.get('model_used')}")
            print(f"   Время ответа: {test_result.get('processing_time', 0):.2f}с")
            return True
        else:
            print(f"❌ Ошибка подключения к Gemini API: {test_result.get('error')}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка при создании/тестировании адаптера: {e}")
        return False


def main():
    """Основная функция"""
    # Настройка логирования
    setup_development_logger()
    
    print("🚀 Тестирование настройки Gemini API")
    print("=" * 50)
    
    success = test_gemini_setup()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ Все тесты пройдены! Gemini API готов к использованию.")
        print("\n💡 Теперь вы можете запустить:")
        print("   python process_pure_vision_fixed.py input.pdf output.csv")
        print("   или")
        print("   python process_pure_vision_fixed.py input.pdf output.csv --provider gemini")
    else:
        print("❌ Обнаружены проблемы с настройкой Gemini API.")
        print("\n🔧 Проверьте:")
        print("   1. Файл .env содержит GEMINI_API_KEY")
        print("   2. API ключ действителен")
        print("   3. Установлены все зависимости: pip install google-generativeai")
    
    return 0 if success else 1


if __name__ == "__main__":
    exit(main()) 