# OCR-OCD: PDF to CSV Converter

Преобразование PDF задачников по математике в CSV формат с использованием ChatGPT-4 Vision API.

## Описание

OCR-OCD - это Python-скрипт для автоматического извлечения математических задач из отсканированных PDF задачников и сохранения их в структурированном CSV формате. Проект использует ChatGPT-4 Vision API для точного распознавания текста, игнорируя встроенный OCR-слой PDF из-за высокого уровня ошибок.

## Возможности

- ✅ Обработка PDF файлов со сканами задачников
- ✅ Использование ChatGPT-4 Vision для точного распознавания
- ✅ Постраничная обработка для оптимального использования API
- ✅ Автоматическая нумерация задач (оригинальная или unknown-X)
- ✅ Определение наличия изображений в задачах
- ✅ Сохранение в CSV с кодировкой UTF-8
- ✅ Восстановление после сбоев
- ✅ Подробное логирование процесса

## Требования

- Python 3.9+
- API ключ для одного из провайдеров:
  - OpenAI GPT-4 Vision API
  - Google Gemini API
  - Anthropic Claude API
- 2GB+ RAM
- 1GB+ свободного места на диске
- Стабильное интернет-соединение

## Установка

1. Клонируйте репозиторий:
```bash
git clone <repository_url>
cd ocr-ocd
```

2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. Проверьте установку зависимостей:
```bash
python check_dependencies.py
```

4. Создайте файл конфигурации:
```bash
cp env.example .env
```

5. Добавьте ваш API ключ в файл `.env`:
```
# OpenAI GPT-4 Vision
OPENAI_API_KEY=your_openai_api_key_here

# Google Gemini (альтернатива)
GEMINI_API_KEY=your_gemini_api_key_here

# Anthropic Claude (альтернатива)
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

## Использование

### Базовое использование

```bash
python -m src.main input.pdf
```

### С указанием выходного файла

```bash
python -m src.main input.pdf --output results.csv
```

### С подробным логированием

```bash
python -m src.main input.pdf --verbose
```

### Все параметры

```bash
python -m src.main input.pdf \
  --output results.csv \
  --config custom.env \
  --verbose
```

## Структура выходного CSV

| Колонка | Описание |
|---------|----------|
| `page_number` | Номер страницы в PDF |
| `task_number` | Номер задачи (оригинальный или unknown-X) |
| `task_text` | Полный текст задачи |
| `has_image` | Наличие изображения (true/false) |

### Пример выходных данных

```csv
page_number,task_number,task_text,has_image
1,1,"Сложи числа 2 + 3",false
1,2,"Реши пример: 5 - 2 = ?",false
1,unknown-1,"Найди лишнее число в ряду",true
2,3,"Вычисли площадь прямоугольника",true
```

## Конфигурация

Основные параметры в файле `.env`:

```env
# Обязательные
OPENAI_API_KEY=your_api_key

# Опциональные (со значениями по умолчанию)
MODEL_NAME=gpt-4-vision-preview
MAX_TOKENS=4096
TEMPERATURE=0.1
TIMEOUT=60
MAX_RETRIES=3
RETRY_DELAY=5
LOG_LEVEL=INFO
```

## Структура проекта

```
ocr-ocd/
├── src/                 # Исходный код
│   ├── core/           # Основная логика
│   ├── utils/          # Утилиты
│   └── models/         # Модели данных
├── tests/              # Тесты
├── docs/               # Документация
├── logs/               # Файлы логов
├── output/             # Выходные CSV файлы
├── temp/               # Временные файлы
└── requirements.txt    # Зависимости
```

## Разработка

### Запуск тестов

```bash
pytest tests/
```

### Проверка типов

```bash
mypy src/
```

### Форматирование кода

```bash
black src/ tests/
```

### Линтинг

```bash
flake8 src/ tests/
```

## Лицензия

[Укажите лицензию]

## Поддержка

Если у вас возникли вопросы или проблемы, пожалуйста:

1. Проверьте логи в папке `logs/`
2. Убедитесь, что API ключ корректный
3. Проверьте интернет-соединение
4. Создайте issue в репозитории

## Ограничения

- Поддерживает только PDF файлы
- Работает только с русскоязычными задачниками
- Требует стабильного интернет-соединения
- Ограничен лимитами OpenAI API 