"""Prompt management module for Vision API."""

import json
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass
from src.utils.logger import get_logger

logger = get_logger(__name__)


class PromptType(Enum):
    """Types of prompts for different page content."""
    BASIC = "basic"  # Regular math problems
    DETAILED = "detailed"  # Text + images/diagrams
    STRUCTURED = "structured"  # Lists of exercises
    WORD_PROBLEMS = "word_problems"  # Text-heavy word problems
    FALLBACK = "fallback"  # Simple fallback when JSON parsing fails
    EXPERIMENTAL = "experimental" # Experimental prompt


@dataclass
class PromptTemplate:
    """Template for a prompt with metadata."""
    type: PromptType
    template: str
    description: str
    expected_tokens: int
    confidence_threshold: float = 0.8


class PromptManager:
    """Manages prompts for different types of mathematical content."""
    
    def __init__(self) -> None:
        """Initialize prompt manager with templates."""
        # Define prompt templates
        self.prompts = {
            PromptType.BASIC: """Посмотри на эту страницу из учебника математики для 1 класса.

Найди все математические задачи и упражнения на этой странице. 
Для каждой задачи опиши:
- Номер задачи (если видно)
- Текст задачи
- Есть ли картинка к задаче

Напиши результат в простом формате.""",

            PromptType.DETAILED: """Это страница из учебника арифметики для первого класса 1959 года.

Внимательно рассмотри страницу и найди все математические задания.
Для каждого задания укажи:
1. Номер (если написан)
2. Полный текст задания
3. Есть ли иллюстрация

Опиши каждое задание отдельно.""",

            PromptType.STRUCTURED: """Анализируй эту страницу учебника математики.

Найди математические задачи и для каждой скажи:
- task_number: номер задачи
- task_text: текст задачи  
- has_image: есть ли картинка

Если номер не видно, напиши "unknown".""",

            PromptType.FALLBACK: """Опиши что видишь на этой странице из учебника математики. 
Какие есть задачи и упражнения?""",

            PromptType.EXPERIMENTAL: """Рассмотри страницу учебника. Найди задачи по математике и опиши их простыми словами."""
        }
        logger.info(f"PromptManager initialized with {len(self.prompts)} templates")
    
    def _load_prompt_templates(self) -> Dict[PromptType, PromptTemplate]:
        """Load all prompt templates.
        
        Returns:
            Dictionary mapping prompt types to templates
        """
        templates = {}
        
        # Standard mathematical problems prompt
        standard_prompt = """Проанализируй страницу {page_number} математического задачника для начальной школы и извлеки все задачи.

ВАЖНЫЕ ТРЕБОВАНИЯ:
1. Найди ВСЕ математические задачи на странице (примеры, уравнения, текстовые задачи)
2. Для каждой задачи определи её номер (если есть) или отметь как "unknown"
3. Извлеки ПОЛНЫЙ текст каждой задачи включая все числа и математические выражения
4. Определи, есть ли в задаче изображения, схемы, диаграммы или таблицы

ФОРМАТ ОТВЕТА - строго JSON:
{{
  "page_number": {page_number},
  "tasks": [
    {{
      "task_number": "1",
      "task_text": "Полный текст задачи с сохранением всех чисел и операций...",
      "has_image": false,
      "confidence": 0.95
    }}
  ],
  "page_info": {{
    "total_tasks": 1,
    "processing_notes": "Дополнительные заметки если нужно"
  }}
}}

ПРАВИЛА:
- Если номер задачи не виден четко, используй "unknown"
- В task_text включай ВЕСЬ текст: условие, данные, вопрос
- has_image = true если есть рисунки, схемы, диаграммы, таблицы, графики
- confidence - твоя уверенность в правильности извлечения (0-1)
- Игнорируй заголовки страниц, номера страниц, название учебника
- Каждая задача должна быть полной и самостоятельной

Отвечай ТОЛЬКО валидным JSON, без комментариев до или после."""

        templates[PromptType.STANDARD] = PromptTemplate(
            type=PromptType.STANDARD,
            template=standard_prompt,
            description="Standard prompt for mathematical problems",
            expected_tokens=600
        )
        
        # Mixed content prompt (text + images)
        mixed_content_prompt = """Проанализируй страницу {page_number} учебника математики, которая содержит текст и визуальные элементы.

ОСОБОЕ ВНИМАНИЕ к:
1. Задачам с диаграммами, схемами, рисунками
2. Геометрическим задачам с фигурами
3. Задачам с таблицами и графиками
4. Текстовым задачам с иллюстрациями

ФОРМАТ ОТВЕТА - строго JSON:
{{
  "page_number": {page_number},
  "tasks": [
    {{
      "task_number": "1",
      "task_text": "Полное описание задачи включая описание изображений...",
      "has_image": true,
      "confidence": 0.90
    }}
  ],
  "page_info": {{
    "total_tasks": 1,
    "visual_elements": ["диаграмма", "схема", "таблица"],
    "processing_notes": "Страница содержит визуальные элементы"
  }}
}}

ВАЖНО:
- Описывай визуальные элементы в task_text если они важны для понимания
- has_image = true для любых визуальных элементов
- Сохраняй связь между текстом и изображением
- Если изображение ключевое для задачи, опиши его

Отвечай ТОЛЬКО валидным JSON."""

        templates[PromptType.MIXED_CONTENT] = PromptTemplate(
            type=PromptType.MIXED_CONTENT,
            template=mixed_content_prompt,
            description="Prompt for pages with text and visual elements",
            expected_tokens=700
        )
        
        # Exercise list prompt
        exercise_list_prompt = """Проанализируй страницу {page_number} со списком упражнений и примеров.

ФОКУС на:
1. Числовые примеры и уравнения
2. Списки заданий с номерами
3. Серии однотипных упражнений
4. Краткие математические выражения

ФОРМАТ ОТВЕТА - строго JSON:
{{
  "page_number": {page_number},
  "tasks": [
    {{
      "task_number": "1а",
      "task_text": "2 + 3 = ?",
      "has_image": false,
      "confidence": 0.98
    }},
    {{
      "task_number": "1б", 
      "task_text": "5 - 2 = ?",
      "has_image": false,
      "confidence": 0.98
    }}
  ],
  "page_info": {{
    "total_tasks": 2,
    "content_type": "exercise_list",
    "processing_notes": "Список кратких упражнений"
  }}
}}

ВАЖНО:
- Каждый пример или упражнение = отдельная задача
- Сохраняй буквенные обозначения (а, б, в) в номерах
- Точно передавай математические выражения
- Для коротких примеров confidence может быть выше

Отвечай ТОЛЬКО валидным JSON."""

        templates[PromptType.EXERCISE_LIST] = PromptTemplate(
            type=PromptType.EXERCISE_LIST,
            template=exercise_list_prompt,
            description="Prompt for pages with exercise lists",
            expected_tokens=500
        )
        
        # Word problems prompt  
        word_problems_prompt = """Проанализируй страницу {page_number} с текстовыми математическими задачами.

СПЕЦИАЛИЗАЦИЯ на:
1. Текстовые задачи с развернутым условием
2. Задачи на логику и рассуждения
3. Многоступенчатые задачи
4. Задачи с контекстом (магазин, школа, дом и т.д.)

ФОРМАТ ОТВЕТА - строго JSON:
{{
  "page_number": {page_number},
  "tasks": [
    {{
      "task_number": "1",
      "task_text": "В магазине было 50 яблок. Утром продали 18 яблок, а вечером ещё 12. Сколько яблок осталось в магазине?",
      "has_image": false,
      "confidence": 0.92
    }}
  ],
  "page_info": {{
    "total_tasks": 1,
    "content_type": "word_problems",
    "processing_notes": "Текстовые задачи с развернутым условием"
  }}
}}

ВАЖНО:
- Сохраняй ВЕСЬ текст задачи без сокращений
- Включай все числовые данные и единицы измерения
- Передавай логическую структуру задачи
- Сохраняй вопросительные предложения полностью

Отвечай ТОЛЬКО валидным JSON."""

        templates[PromptType.WORD_PROBLEMS] = PromptTemplate(
            type=PromptType.WORD_PROBLEMS,
            template=word_problems_prompt,
            description="Prompt for word problems with extended conditions",
            expected_tokens=550
        )
        
        # Fallback prompt (simplified)
        fallback_prompt = """Посмотри на страницу {page_number} и найди математические задачи.

Извлеки каждую задачу в простом JSON формате:

{{
  "page_number": {page_number},
  "tasks": [
    {{
      "task_number": "1",
      "task_text": "текст задачи",
      "has_image": false,
      "confidence": 0.7
    }}
  ],
  "page_info": {{
    "total_tasks": 1
  }}
}}

Ответ только JSON, ничего больше."""

        templates[PromptType.FALLBACK] = PromptTemplate(
            type=PromptType.FALLBACK,
            template=fallback_prompt,
            description="Simple fallback prompt when parsing fails",
            expected_tokens=300,
            confidence_threshold=0.5
        )
        
        return templates
    
    def get_prompt(
        self, 
        prompt_type: PromptType, 
        page_number: int,
        **kwargs
    ) -> str:
        """Get formatted prompt for given type and page.
        
        Args:
            prompt_type: Type of prompt to use
            page_number: Page number to include in prompt
            **kwargs: Additional variables for prompt formatting
            
        Returns:
            Formatted prompt string
        """
        if prompt_type not in self.prompts:
            logger.warning(f"Unknown prompt type {prompt_type}, using fallback")
            prompt_type = PromptType.FALLBACK
        
        template = self.prompts[prompt_type]
        
        try:
            # Format the prompt with page number and any additional kwargs
            formatted_prompt = template.format(
                page_number=page_number,
                **kwargs
            )
            
            logger.debug(
                "Prompt generated",
                type=prompt_type.value,
                page_number=page_number,
                length=len(formatted_prompt)
            )
            
            return formatted_prompt
            
        except KeyError as e:
            logger.error(f"Missing variable in prompt template: {e}")
            # Fallback to simple replacement
            return template.replace("{page_number}", str(page_number))
    
    def get_prompt_auto(
        self, 
        page_number: int,
        page_hints: Optional[Dict[str, Any]] = None
    ) -> str:
        """Automatically select best prompt type based on page hints.
        
        Args:
            page_number: Page number
            page_hints: Optional hints about page content
            
        Returns:
            Formatted prompt string
        """
        if not page_hints:
            return self.get_prompt(PromptType.STANDARD, page_number)
        
        # Analyze hints to select best prompt type
        has_images = page_hints.get("has_images", False)
        has_diagrams = page_hints.get("has_diagrams", False)
        text_density = page_hints.get("text_density", "medium")
        problem_count = page_hints.get("estimated_problems", 0)
        
        # Decision logic for prompt selection
        if has_images or has_diagrams:
            selected_type = PromptType.DETAILED
        elif problem_count > 5 and text_density == "low":
            selected_type = PromptType.STRUCTURED
        elif text_density == "high":
            selected_type = PromptType.WORD_PROBLEMS
        else:
            selected_type = PromptType.BASIC
        
        logger.info(
            "Auto-selected prompt type",
            type=selected_type.value,
            page_number=page_number,
            hints=page_hints
        )
        
        return self.get_prompt(selected_type, page_number)
    
    def get_template_info(self, prompt_type: PromptType) -> Dict[str, Any]:
        """Get information about a prompt template.
        
        Args:
            prompt_type: Type of prompt
            
        Returns:
            Template information
        """
        if prompt_type not in self.prompts:
            return {}
        
        template = self.prompts[prompt_type]
        return {
            "type": template.type.value,
            "description": template.description,
            "expected_tokens": template.expected_tokens,
            "confidence_threshold": template.confidence_threshold,
            "template_length": len(template)
        }
    
    def list_available_types(self) -> List[str]:
        """List all available prompt types.
        
        Returns:
            List of prompt type names
        """
        return [prompt_type.value for prompt_type in self.prompts.keys()]
    
    def validate_response_json(self, response_text: str) -> Dict[str, Any]:
        """Validate and parse JSON response from API.
        
        Args:
            response_text: Raw response text from API
            
        Returns:
            Parsed JSON data
            
        Raises:
            ValueError: If JSON is invalid
        """
        try:
            # Try to extract JSON from response
            response_text = response_text.strip()
            
            # Handle cases where response might have extra text
            if response_text.startswith("```json"):
                response_text = response_text.replace("```json", "").replace("```", "").strip()
            elif response_text.startswith("```"):
                response_text = response_text.replace("```", "").strip()
            
            # Find JSON content if wrapped in other text
            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}") + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_text = response_text[start_idx:end_idx]
            else:
                json_text = response_text
            
            # Parse JSON
            parsed_data = json.loads(json_text)
            
            # Validate required structure
            self._validate_json_structure(parsed_data)
            
            logger.debug("JSON response validated successfully")
            return parsed_data
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {e}")
            raise ValueError(f"Invalid JSON response: {e}")
        except Exception as e:
            logger.error(f"JSON validation failed: {e}")
            raise ValueError(f"Response validation failed: {e}")
    
    def _validate_json_structure(self, data: Dict[str, Any]) -> None:
        """Validate JSON structure matches expected format.
        
        Args:
            data: Parsed JSON data
            
        Raises:
            ValueError: If structure is invalid
        """
        required_fields = ["page_number", "tasks"]
        
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        
        if not isinstance(data["tasks"], list):
            raise ValueError("'tasks' must be a list")
        
        # Validate each task
        for i, task in enumerate(data["tasks"]):
            if not isinstance(task, dict):
                raise ValueError(f"Task {i} must be a dictionary")
            
            task_required = ["task_number", "task_text", "has_image"]
            for field in task_required:
                if field not in task:
                    raise ValueError(f"Task {i} missing field: {field}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get prompt manager statistics.
        
        Returns:
            Statistics about available prompts
        """
        return {
            "total_templates": len(self.prompts),
            "template_types": [t.value for t in self.prompts.keys()],
            "avg_template_length": sum(len(t) for t in self.prompts.values()) // len(self.prompts),
            "total_expected_tokens": sum(t.expected_tokens for t in self.prompts.values()),
            "templates_info": {
                t.type.value: self.get_template_info(t.type) 
                for t in self.prompts.values()
            }
        } 