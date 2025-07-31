# Реализация уникальных папок временных файлов

## 📋 Описание изменений

Система OCR-OCD теперь создает уникальные папки временных файлов для каждого PDF файла на основе:
- **Basename** PDF файла (имя без расширения)
- **MD5 хэш** содержимого файла (первые 8 символов)

**Формат имени папки:** `{basename}_{md5_hash_8chars}`

## 🎯 Преимущества

### 1. **Уникальность**
- Разные PDF файлы всегда получают разные папки
- Одинаковые файлы (дубликаты) используют одну папку
- Исключаются конфликты при параллельной обработке

### 2. **Читаемость**
- Имя папки содержит читаемую часть (имя файла)
- MD5 хэш обеспечивает уникальность
- Легко понять, какой файл обрабатывался

### 3. **Безопасность**
- Изолированные рабочие среды для каждого PDF
- Нет пересечений временных файлов
- Возможность сохранения промежуточных результатов

## 🔧 Реализованные компоненты

### 1. Новый модуль `src/utils/pdf_utils.py`

```python
def generate_unique_temp_dir(pdf_path: Path, base_temp_dir: Path) -> Path
def calculate_file_md5(file_path: Path) -> str
def get_pdf_unique_identifier(pdf_path: Path) -> str
def cleanup_temp_dir(temp_dir: Path, keep_processed_files: bool) -> None
def validate_pdf_file(pdf_path: Path) -> bool
```

### 2. Обновленный `src/main.py`

**Изменения в классе `OCROCDOrchestrator`:**
- Добавлено поле `unique_temp_dir: Optional[Path]`
- Метод `setup_components()` теперь создает уникальную папку
- Метод `cleanup()` очищает уникальную папку
- Добавлена валидация PDF перед обработкой

### 3. Comprehensive тесты `tests/unit/test_pdf_utils.py`

**17 тестов покрывают:**
- ✅ Расчет MD5 хэшей
- ✅ Генерацию уникальных папок
- ✅ Валидацию PDF файлов
- ✅ Очистку временных файлов
- ✅ Интеграционные сценарии

## 📁 Структура папок

### До изменений:
```
temp/
├── page_001.png
├── page_002.png
├── processing_state.json
└── ... (файлы разных PDF смешаны)
```

### После изменений:
```
temp/
├── textbook_chapter1_a1b2c3d4/
│   ├── page_001.png
│   ├── page_001.json
│   └── processing_state.json
├── textbook_chapter2_e5f6g7h8/
│   ├── page_001.png
│   ├── page_001.json
│   └── processing_state.json
└── homework_exercises_i9j0k1l2/
    ├── page_001.png
    ├── page_001.json
    └── processing_state.json
```

## 🚀 Примеры использования

### Базовое использование (как раньше):
```bash
python -m src.main textbook.pdf tasks.csv
```

**Результат:** Создается папка `temp/textbook_a1b2c3d4/`

### Множественная обработка:
```bash
python -m src.main chapter1.pdf chapter1_tasks.csv &
python -m src.main chapter2.pdf chapter2_tasks.csv &
```

**Результат:**
- `temp/chapter1_e5f6g7h8/` для первого файла
- `temp/chapter2_i9j0k1l2/` для второго файла

### Обработка дубликатов:
```bash
python -m src.main textbook.pdf tasks1.csv
python -m src.main textbook_copy.pdf tasks2.csv  # Если содержимое идентично
```

**Результат:** Обе команды используют одну папку (если содержимое файлов идентично)

## ⚙️ Конфигурация

Система использует существующую конфигурацию `temp_dir` из `config.py`:

```python
class Config(BaseModel):
    temp_dir: Path = Field(default=Path("temp"))
```

Уникальные папки создаются внутри `temp_dir`:
- Базовая папка: `temp/`
- Уникальные папки: `temp/{basename}_{md5_hash}/`

## 🧹 Управление очисткой

### Автоматическая очистка при завершении:
```python
orchestrator.cleanup()  # Сохраняет JSON файлы, удаляет изображения
```

### Ручная очистка:
```python
from src.utils.pdf_utils import cleanup_temp_dir

# Удалить все файлы
cleanup_temp_dir(temp_dir, keep_processed_files=False)

# Сохранить JSON файлы
cleanup_temp_dir(temp_dir, keep_processed_files=True)
```

## 🔒 Обратная совместимость

- ✅ Существующие скрипты работают без изменений
- ✅ CLI интерфейс остался прежним
- ✅ Конфигурация осталась совместимой
- ✅ Все существующие тесты проходят

## 📊 Тестирование

```bash
# Запуск тестов новой функциональности
python -m pytest tests/unit/test_pdf_utils.py -v

# Результат: 17 passed ✅
```

### Покрытие тестами:
- **MD5 вычисления:** 3 теста
- **Генерация уникальных папок:** 3 теста  
- **Получение идентификаторов:** 2 теста
- **Очистка папок:** 3 теста
- **Валидация PDF:** 5 тестов
- **Интеграционные сценарии:** 1 тест

## 🎉 Результат

Система OCR-OCD теперь обеспечивает:

1. **Изолированную обработку** каждого PDF файла
2. **Предотвращение конфликтов** при параллельной работе  
3. **Читаемые имена** временных папок
4. **Автоматическую очистку** с гибкими настройками
5. **Полную обратную совместимость** с существующим кодом

**Готово к production использованию!** 🚀 