# Устранение проблем

## Ошибка: "Google Generative AI library not available"

### Проблема
```
Критическая ошибка: Google Generative AI library not available. Install with: pip install google-generativeai
```

### Решение
1. Установите недостающую библиотеку:
```bash
pip install google-generativeai
```

2. Или переустановите все зависимости:
```bash
pip install -r requirements.txt
```

3. Проверьте установку:
```bash
python check_dependencies.py
```

## Ошибка: "Anthropic library not available"

### Проблема
```
Критическая ошибка: Anthropic library not available. Install with: pip install anthropic
```

### Решение
1. Установите недостающую библиотеку:
```bash
pip install anthropic
```

2. Или переустановите все зависимости:
```bash
pip install -r requirements.txt
```

## Проверка установки

Запустите скрипт проверки зависимостей:
```bash
python check_dependencies.py
```

Этот скрипт проверит:
- ✅ Все необходимые библиотеки
- ✅ Доступность мультимодальных API провайдеров
- ✅ Корректность импортов

## Частые проблемы

### 1. Отсутствующие зависимости
Если при запуске появляются ошибки импорта, выполните:
```bash
pip install -r requirements.txt
```

### 2. Проблемы с API ключами
Убедитесь, что в файле `.env` указан хотя бы один API ключ:
```
OPENAI_API_KEY=your_key_here
# или
GEMINI_API_KEY=your_key_here
# или
ANTHROPIC_API_KEY=your_key_here
```

### 3. Проблемы с правами доступа
Если возникают ошибки доступа к файлам:
```bash
chmod +x *.py
```

### 4. Проблемы с Python path
Если модули не находятся, убедитесь, что вы запускаете скрипты из корневой директории проекта.

## Ошибка OpenSSL/urllib3

### Проблема
```
ImportError: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl' module is compiled with 'OpenSSL 1.0.2n  7 Dec 2017'
```

### Решение для старых серверов
1. Используйте специальный файл requirements:
```bash
pip install -r requirements_legacy.txt
```

2. Или установите совместимые версии вручную:
```bash
pip install urllib3==1.26.18 requests==2.31.0
pip install -r requirements.txt
```

3. Проверьте установку:
```bash
python check_dependencies.py
```

## Получение API ключей

### OpenAI GPT-4 Vision
1. Перейдите на [OpenAI Platform](https://platform.openai.com/)
2. Создайте аккаунт или войдите
3. Перейдите в раздел API Keys
4. Создайте новый ключ
5. Добавьте в `.env`: `OPENAI_API_KEY=your_key_here`

### Google Gemini
1. Перейдите на [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Войдите с Google аккаунтом
3. Создайте API ключ
4. Добавьте в `.env`: `GEMINI_API_KEY=your_key_here`

### Anthropic Claude
1. Перейдите на [Anthropic Console](https://console.anthropic.com/)
2. Создайте аккаунт
3. Перейдите в раздел API Keys
4. Создайте новый ключ
5. Добавьте в `.env`: `ANTHROPIC_API_KEY=your_key_here` 