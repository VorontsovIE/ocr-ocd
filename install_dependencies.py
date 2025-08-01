#!/usr/bin/env python3
"""
Скрипт для автоматической установки зависимостей с учетом совместимости OpenSSL
"""

import sys
import subprocess
import ssl
from pathlib import Path

def check_openssl_version():
    """Проверяет версию OpenSSL"""
    try:
        openssl_version = ssl.OPENSSL_VERSION
        print(f"🔍 Обнаружена версия OpenSSL: {openssl_version}")
        
        # Проверяем, является ли это старой версией
        if "1.0.2" in openssl_version or "1.0.1" in openssl_version:
            print("⚠️  Обнаружена старая версия OpenSSL (< 1.1.1)")
            return "legacy"
        else:
            print("✅ Современная версия OpenSSL (>= 1.1.1)")
            return "modern"
    except Exception as e:
        print(f"❌ Ошибка при проверке OpenSSL: {e}")
        return "unknown"

def install_legacy_dependencies():
    """Устанавливает зависимости для старых серверов"""
    print("\n🔧 Установка зависимостей для старых серверов...")
    
    # Сначала устанавливаем совместимые версии urllib3 и requests
    try:
        subprocess.run([
            sys.executable, "-m", "pip", "install", 
            "urllib3==1.26.18", "requests==2.31.0"
        ], check=True)
        print("✅ urllib3 и requests установлены")
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка при установке urllib3/requests: {e}")
        return False
    
    # Затем устанавливаем остальные зависимости
    try:
        subprocess.run([
            sys.executable, "-m", "pip", "install", "-r", "requirements_legacy.txt"
        ], check=True)
        print("✅ Все зависимости установлены")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка при установке зависимостей: {e}")
        return False

def install_modern_dependencies():
    """Устанавливает зависимости для современных серверов"""
    print("\n🔧 Установка зависимостей для современных серверов...")
    
    try:
        subprocess.run([
            sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
        ], check=True)
        print("✅ Все зависимости установлены")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка при установке зависимостей: {e}")
        return False

def main():
    """Основная функция"""
    print("🚀 Автоматическая установка зависимостей")
    print("=" * 50)
    
    # Проверяем версию OpenSSL
    openssl_type = check_openssl_version()
    
    if openssl_type == "legacy":
        print("\n📋 Используем совместимые версии для старого OpenSSL")
        success = install_legacy_dependencies()
    elif openssl_type == "modern":
        print("\n📋 Используем современные версии зависимостей")
        success = install_modern_dependencies()
    else:
        print("\n⚠️  Не удалось определить версию OpenSSL")
        print("Попробуем установить совместимые версии...")
        success = install_legacy_dependencies()
    
    if success:
        print("\n✅ Установка завершена успешно!")
        print("\n🔍 Проверяем установку...")
        
        # Запускаем проверку зависимостей
        try:
            subprocess.run([sys.executable, "check_dependencies.py"], check=True)
        except subprocess.CalledProcessError:
            print("⚠️  Проверка зависимостей не прошла, но установка завершена")
    else:
        print("\n❌ Установка не удалась!")
        print("\n💡 Попробуйте установить зависимости вручную:")
        if openssl_type == "legacy":
            print("pip install -r requirements_legacy.txt")
        else:
            print("pip install -r requirements.txt")
        sys.exit(1)

if __name__ == "__main__":
    main() 