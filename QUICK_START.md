# 🚀 Быстрый старт с Gemini API

## ✅ Шаг 1: Проверка настройки

Запустите тест для проверки настройки Gemini:

```bash
python test_gemini_setup.py
```

Вы должны увидеть:
```
✅ GEMINI_API_KEY найден: AIzaSyC...
✅ Gemini доступен в списке провайдеров
✅ Gemini выбран как провайдер по умолчанию
✅ Подключение к Gemini API успешно
```

## 🎯 Шаг 2: Обработка PDF

### Базовое использование (автоматически выберет Gemini)
```bash
python process_pure_vision_fixed.py input.pdf output.csv
```

### Принудительный выбор Gemini
```bash
python process_pure_vision_fixed.py input.pdf output.csv --provider gemini
```

### С дополнительными опциями
```bash
python process_pure_vision_fixed.py input.pdf output.csv \
    --provider gemini \
    --start-page 1 \
    --end-page 10 \
    --split-mode vertical \
    --verbose
```

## 📊 Что вы увидите

При запуске система покажет:
```
🚀 Запуск OCR-OCD Pure Vision Fixed с мультимодальными адаптерами
📋 Доступные провайдеры: ['gemini']
🎯 Используемый провайдер: gemini
🔧 Модель: gemini-2.0-flash-exp
🌟 Используется Google Gemini (рекомендуется для скорости и стоимости)
✅ Подключение к gemini API успешно
```

## 🔧 Полезные опции

| Опция | Описание | Пример |
|-------|----------|--------|
| `--provider gemini` | Принудительно использовать Gemini | `--provider gemini` |
| `--verbose` | Подробный вывод | `--verbose` |
| `--start-page 1` | Начать с первой страницы | `--start-page 1` |
| `--end-page 10` | Закончить на 10-й странице | `--end-page 10` |
| `--split-mode vertical` | Разделить страницы вертикально | `--split-mode vertical` |
| `--parallel` | Параллельная обработка | `--parallel` |

## 🐛 Устранение проблем

### Ошибка "GEMINI_API_KEY не найден"
1. Убедитесь, что файл `.env` существует
2. Проверьте, что в нем есть строка `GEMINI_API_KEY=your_key_here`

### Ошибка "Google Generative AI library not available"
```bash
pip install google-generativeai
```

### Ошибка подключения к API
1. Проверьте правильность API ключа
2. Убедитесь, что ключ активен в Google AI Studio
3. Проверьте интернет-соединение

## 📈 Преимущества Gemini

- ⚡ **Скорость**: Самый быстрый из доступных API
- 💰 **Стоимость**: Самый доступный по цене
- 🎯 **Качество**: Хорошее качество анализа
- 🌐 **Доступность**: Простая регистрация и настройка

## 🎉 Готово!

После успешной настройки вы можете обрабатывать любые PDF учебники с математическими задачами, используя мощь Google Gemini API! 