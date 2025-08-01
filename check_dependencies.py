#!/usr/bin/env python3
"""
Скрипт для проверки установки всех зависимостей
"""

import sys
from pathlib import Path

# Добавляем src в Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def check_dependencies():
    """Проверяет установку всех зависимостей"""
    print("🔍 Проверка зависимостей")
    print("=" * 40)
    
    dependencies = {
        "PyMuPDF": "fitz",
        "openai": "openai", 
        "Pillow": "PIL",
        "python-dotenv": "dotenv",
        "pandas": "pandas",
        "tenacity": "tenacity",
        "click": "click",
        "loguru": "loguru",
        "pydantic": "pydantic",
        "tqdm": "tqdm",
        "requests": "requests",
        "google-generativeai": "google.generativeai",
        "anthropic": "anthropic"
    }
    
    missing_deps = []
    available_deps = []
    
    for dep_name, import_name in dependencies.items():
        try:
            __import__(import_name)
            print(f"✅ {dep_name}")
            available_deps.append(dep_name)
        except ImportError:
            print(f"❌ {dep_name}")
            missing_deps.append(dep_name)
    
    print("\n" + "=" * 40)
    print(f"📊 Результат: {len(available_deps)}/{len(dependencies)} зависимостей установлено")
    
    if missing_deps:
        print(f"\n❌ Отсутствующие зависимости: {', '.join(missing_deps)}")
        print("\n💡 Установите их командой:")
        print("pip install -r requirements.txt")
        return False
    else:
        print("\n✅ Все зависимости установлены!")
        return True

def check_vision_adapters():
    """Проверяет доступность адаптеров для мультимодальных API"""
    print("\n🔍 Проверка адаптеров мультимодальных API")
    print("=" * 40)
    
    try:
        from src.core.vision_adapters import VisionAdapterFactory, VisionProvider
        
        available_providers = VisionAdapterFactory.get_available_providers()
        print(f"📋 Доступные провайдеры: {[p.value for p in available_providers]}")
        
        if VisionProvider.OPENAI in available_providers:
            print("✅ OpenAI доступен")
        else:
            print("❌ OpenAI недоступен")
            
        if VisionProvider.GEMINI in available_providers:
            print("✅ Gemini доступен")
        else:
            print("❌ Gemini недоступен")
            
        if VisionProvider.CLAUDE in available_providers:
            print("✅ Claude доступен")
        else:
            print("❌ Claude недоступен")
            
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при проверке адаптеров: {e}")
        return False

if __name__ == "__main__":
    deps_ok = check_dependencies()
    adapters_ok = check_vision_adapters()
    
    print("\n" + "=" * 40)
    if deps_ok and adapters_ok:
        print("🎉 Все проверки пройдены! Система готова к работе.")
    else:
        print("⚠️  Обнаружены проблемы. Исправьте их перед использованием.")
        sys.exit(1) 