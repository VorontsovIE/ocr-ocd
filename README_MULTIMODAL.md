# OCR-OCD с мультимодальными API адаптерами

Улучшенная система извлечения математических задач из PDF учебников с поддержкой различных мультимодальных API.

## 🚀 Поддерживаемые провайдеры

### 1. Google Gemini (по умолчанию)
- **Модель**: `gemini-2.0-flash-exp`
- **Преимущества**: Быстрый, доступный, хорошее качество
- **API ключ**: `GEMINI_API_KEY`

### 2. OpenAI GPT-4 Vision
- **Модель**: `gpt-4-vision-preview`
- **Преимущества**: Высокое качество анализа
- **API ключ**: `OPENAI_API_KEY`

### 3. Anthropic Claude
- **Модель**: `claude-3-5-sonnet-20241022`
- **Преимущества**: Отличное понимание контекста
- **API ключ**: `ANTHROPIC_API_KEY`

## 📦 Установка

### 1. Клонирование репозитория
```bash
git clone <repository-url>
cd ocr-ocd
```

### 2. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 3. Настройка API ключей
Скопируйте `env.example` в `.env` и заполните API ключи:

```bash
cp env.example .env
```

Отредактируйте `.env` файл:
```env
# Выберите провайдера (опционально)
VISION_PROVIDER=gemini

# Установите хотя бы один API ключ
GEMINI_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

## 🔧 Использование

### Базовое использование (автоматический выбор провайдера)
```bash
python process_pure_vision_fixed.py input.pdf output.csv
```

### Указание конкретного провайдера
```bash
# Использовать Gemini
python process_pure_vision_fixed.py input.pdf output.csv --provider gemini

# Использовать OpenAI
python process_pure_vision_fixed.py input.pdf output.csv --provider openai

# Использовать Claude
python process_pure_vision_fixed.py input.pdf output.csv --provider claude
```

### Дополнительные опции
```bash
python process_pure_vision_fixed.py input.pdf output.csv \
    --provider gemini \
    --start-page 1 \
    --end-page 10 \
    --split-mode vertical \
    --verbose
```

## 📋 Доступные опции

| Опция | Описание | По умолчанию |
|-------|----------|--------------|
| `--provider` | Провайдер API (gemini/openai/claude) | Автоматический выбор |
| `--start-page` | Начальная страница | 1 |
| `--end-page` | Конечная страница | Все страницы |
| `--split-mode` | Режим разделения (original/vertical/horizontal/grid) | vertical |
| `--no-split` | Отключить разделение изображений | False |
| `--parallel` | Включить параллельную обработку | False |
| `--verbose` | Подробный вывод | False |
| `--force` | Принудительно переобработать все страницы | False |

## 🔍 Получение API ключей

### Google Gemini
1. Перейдите на [Google AI Studio](https://aistudio.google.com/)
2. Создайте новый API ключ
3. Скопируйте ключ в `GEMINI_API_KEY`

### OpenAI
1. Перейдите на [OpenAI Platform](https://platform.openai.com/)
2. Создайте новый API ключ
3. Скопируйте ключ в `OPENAI_API_KEY`

### Anthropic Claude
1. Перейдите на [Anthropic Console](https://console.anthropic.com/)
2. Создайте новый API ключ
3. Скопируйте ключ в `ANTHROPIC_API_KEY`

## 🧪 Тестирование подключения

Система автоматически тестирует подключение к API при запуске:

```bash
python process_pure_vision_fixed.py test.pdf output.csv --verbose
```

Вы увидите информацию о:
- Доступных провайдерах
- Используемом провайдере
- Модели
- Времени ответа API

## 📊 Примеры использования

### Обработка с Gemini (рекомендуется)
```bash
python process_pure_vision_fixed.py math_book.pdf tasks.csv --provider gemini
```

### Обработка с OpenAI для сложных задач
```bash
python process_pure_vision_fixed.py math_book.pdf tasks.csv --provider openai
```

### Обработка с Claude для лучшего понимания контекста
```bash
python process_pure_vision_fixed.py math_book.pdf tasks.csv --provider claude
```

### Параллельная обработка
```bash
python process_pure_vision_fixed.py math_book.pdf tasks.csv \
    --provider gemini \
    --parallel \
    --max-concurrent 3 \
    --batch-size 5
```

## 🔧 Настройка моделей

Вы можете указать конкретную модель в `.env` файле:

```env
# Для Gemini
MODEL_NAME=gemini-2.0-flash-exp

# Для OpenAI
MODEL_NAME=gpt-4-vision-preview

# Для Claude
MODEL_NAME=claude-3-5-sonnet-20241022
```

## 📈 Сравнение провайдеров

| Характеристика | Gemini | OpenAI | Claude |
|----------------|--------|--------|--------|
| Скорость | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| Качество | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Стоимость | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| Доступность | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |

## 🛠️ Разработка

### Добавление нового провайдера

1. Создайте новый адаптер в `src/core/vision_adapters.py`
2. Добавьте провайдера в `VisionProvider` enum
3. Обновите `VisionAdapterFactory`
4. Добавьте API ключ в конфигурацию

### Структура адаптера

```python
class NewProviderAdapter(VisionAPIAdapter):
    def _get_provider(self) -> VisionProvider:
        return VisionProvider.NEW_PROVIDER
    
    def _encode_image(self, image_data: bytes) -> Union[str, Dict[str, Any]]:
        # Кодирование изображения для API
        pass
    
    def _build_messages(self, request: VisionRequest) -> List[Dict[str, Any]]:
        # Построение сообщений для API
        pass
    
    def _make_api_call(self, request: VisionRequest) -> VisionResponse:
        # Выполнение запроса к API
        pass
```

## 🐛 Устранение неполадок

### Ошибка "No API key found"
Убедитесь, что установлен хотя бы один API ключ в `.env` файле.

### Ошибка "Provider not available"
Установите необходимые зависимости:
```bash
pip install google-generativeai  # для Gemini
pip install openai              # для OpenAI
pip install anthropic           # для Claude
```

### Медленная обработка
- Используйте `--parallel` для параллельной обработки
- Уменьшите `--max-concurrent` если возникают ошибки
- Попробуйте другой провайдер

## 📝 Лицензия

MIT License 