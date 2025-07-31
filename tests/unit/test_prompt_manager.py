"""Tests for PromptManager module."""

import json
import pytest
from src.core.prompt_manager import PromptManager, PromptType, PromptTemplate


class TestPromptManager:
    """Tests for PromptManager class."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.prompt_manager = PromptManager()
    
    def test_prompt_manager_initialization(self):
        """Test PromptManager initialization."""
        assert len(self.prompt_manager.templates) == 5  # All prompt types
        assert PromptType.STANDARD in self.prompt_manager.templates
        assert PromptType.MIXED_CONTENT in self.prompt_manager.templates
        assert PromptType.EXERCISE_LIST in self.prompt_manager.templates
        assert PromptType.WORD_PROBLEMS in self.prompt_manager.templates
        assert PromptType.FALLBACK in self.prompt_manager.templates
    
    def test_get_prompt_standard(self):
        """Test getting standard prompt."""
        prompt = self.prompt_manager.get_prompt(PromptType.STANDARD, 5)
        
        assert "страницу 5" in prompt
        assert "JSON" in prompt
        assert "task_number" in prompt
        assert "task_text" in prompt
        assert "has_image" in prompt
        assert "confidence" in prompt
        assert "начальной школы" in prompt
    
    def test_get_prompt_mixed_content(self):
        """Test getting mixed content prompt."""
        prompt = self.prompt_manager.get_prompt(PromptType.MIXED_CONTENT, 10)
        
        assert "страницу 10" in prompt
        assert "диаграммами" in prompt
        assert "схемами" in prompt
        assert "visual_elements" in prompt
        assert "изображений" in prompt
    
    def test_get_prompt_exercise_list(self):
        """Test getting exercise list prompt."""
        prompt = self.prompt_manager.get_prompt(PromptType.EXERCISE_LIST, 3)
        
        assert "страницу 3" in prompt
        assert "упражнений" in prompt
        assert "примеры" in prompt
        assert "1а" in prompt
        assert "1б" in prompt
        assert "exercise_list" in prompt
    
    def test_get_prompt_word_problems(self):
        """Test getting word problems prompt."""
        prompt = self.prompt_manager.get_prompt(PromptType.WORD_PROBLEMS, 7)
        
        assert "страницу 7" in prompt
        assert "текстовые" in prompt
        assert "развернутым условием" in prompt
        assert "word_problems" in prompt
        assert "магазине" in prompt
    
    def test_get_prompt_fallback(self):
        """Test getting fallback prompt."""
        prompt = self.prompt_manager.get_prompt(PromptType.FALLBACK, 2)
        
        assert "страницу 2" in prompt
        assert "JSON" in prompt
        # Fallback should be simpler
        assert len(prompt) < 1000  # Much shorter than other prompts
    
    def test_get_prompt_unknown_type(self):
        """Test getting prompt with unknown type falls back."""
        # This should use fallback
        prompt = self.prompt_manager.get_prompt("invalid_type", 1)
        
        # Should get fallback prompt
        assert "страницу 1" in prompt
        assert len(prompt) < 1000  # Fallback is shorter
    
    def test_get_prompt_with_kwargs(self):
        """Test getting prompt with additional kwargs."""
        # This tests the formatting mechanism
        prompt = self.prompt_manager.get_prompt(PromptType.STANDARD, 1)
        
        # Should work without errors and include page number
        assert "страницу 1" in prompt
    
    def test_get_prompt_auto_no_hints(self):
        """Test auto prompt selection without hints."""
        prompt = self.prompt_manager.get_prompt_auto(5)
        
        # Should default to standard
        assert "страницу 5" in prompt
        assert "начальной школы" in prompt  # Standard prompt marker
    
    def test_get_prompt_auto_with_images(self):
        """Test auto prompt selection with image hints."""
        hints = {
            "has_images": True,
            "has_diagrams": True,
            "text_density": "medium"
        }
        
        prompt = self.prompt_manager.get_prompt_auto(5, hints)
        
        # Should select mixed content
        assert "страницу 5" in prompt
        assert "диаграммами" in prompt  # Mixed content prompt marker
    
    def test_get_prompt_auto_exercise_list(self):
        """Test auto prompt selection for exercise lists."""
        hints = {
            "has_images": False,
            "estimated_problems": 8,
            "text_density": "low"
        }
        
        prompt = self.prompt_manager.get_prompt_auto(3, hints)
        
        # Should select exercise list
        assert "страницу 3" in prompt
        assert "упражнений" in prompt  # Exercise list prompt marker
    
    def test_get_prompt_auto_word_problems(self):
        """Test auto prompt selection for word problems."""
        hints = {
            "has_images": False,
            "text_density": "high",
            "estimated_problems": 2
        }
        
        prompt = self.prompt_manager.get_prompt_auto(7, hints)
        
        # Should select word problems
        assert "страницу 7" in prompt
        assert "текстовые" in prompt  # Word problems prompt marker
    
    def test_get_template_info(self):
        """Test getting template information."""
        info = self.prompt_manager.get_template_info(PromptType.STANDARD)
        
        assert info["type"] == "standard"
        assert "description" in info
        assert "expected_tokens" in info
        assert "confidence_threshold" in info
        assert "template_length" in info
        assert info["expected_tokens"] > 0
        assert info["template_length"] > 0
    
    def test_get_template_info_unknown(self):
        """Test getting template info for unknown type."""
        info = self.prompt_manager.get_template_info("invalid_type")
        
        assert info == {}
    
    def test_list_available_types(self):
        """Test listing available prompt types."""
        types = self.prompt_manager.list_available_types()
        
        assert len(types) == 5
        assert "standard" in types
        assert "mixed_content" in types
        assert "exercise_list" in types
        assert "word_problems" in types
        assert "fallback" in types
    
    def test_validate_response_json_valid(self):
        """Test JSON response validation with valid JSON."""
        valid_json = '''
        {
          "page_number": 1,
          "tasks": [
            {
              "task_number": "1",
              "task_text": "Test task",
              "has_image": false,
              "confidence": 0.9
            }
          ],
          "page_info": {
            "total_tasks": 1
          }
        }
        '''
        
        result = self.prompt_manager.validate_response_json(valid_json)
        
        assert result["page_number"] == 1
        assert len(result["tasks"]) == 1
        assert result["tasks"][0]["task_number"] == "1"
        assert result["tasks"][0]["task_text"] == "Test task"
        assert result["tasks"][0]["has_image"] is False
    
    def test_validate_response_json_with_markdown(self):
        """Test JSON validation with markdown formatting."""
        json_with_markdown = '''
        ```json
        {
          "page_number": 2,
          "tasks": [
            {
              "task_number": "1",
              "task_text": "Another test",
              "has_image": true,
              "confidence": 0.8
            }
          ]
        }
        ```
        '''
        
        result = self.prompt_manager.validate_response_json(json_with_markdown)
        
        assert result["page_number"] == 2
        assert result["tasks"][0]["has_image"] is True
    
    def test_validate_response_json_with_extra_text(self):
        """Test JSON validation with extra text around JSON."""
        response_with_text = '''
        Here is the analysis:
        
        {
          "page_number": 3,
          "tasks": [
            {
              "task_number": "unknown",
              "task_text": "Math problem",
              "has_image": false,
              "confidence": 0.7
            }
          ]
        }
        
        This completes the analysis.
        '''
        
        result = self.prompt_manager.validate_response_json(response_with_text)
        
        assert result["page_number"] == 3
        assert result["tasks"][0]["task_number"] == "unknown"
    
    def test_validate_response_json_invalid_json(self):
        """Test JSON validation with invalid JSON."""
        invalid_json = '''
        {
          "page_number": 1,
          "tasks": [
            {
              "task_number": "1"
              "task_text": "Missing comma"
            }
          ]
        }
        '''
        
        with pytest.raises(ValueError, match="Invalid JSON response"):
            self.prompt_manager.validate_response_json(invalid_json)
    
    def test_validate_response_json_missing_required_fields(self):
        """Test JSON validation with missing required fields."""
        missing_fields_json = '''
        {
          "page_number": 1
        }
        '''
        
        with pytest.raises(ValueError, match="Missing required field"):
            self.prompt_manager.validate_response_json(missing_fields_json)
    
    def test_validate_response_json_invalid_task_structure(self):
        """Test JSON validation with invalid task structure."""
        invalid_task_json = '''
        {
          "page_number": 1,
          "tasks": [
            {
              "task_number": "1"
            }
          ]
        }
        '''
        
        with pytest.raises(ValueError, match="missing field"):
            self.prompt_manager.validate_response_json(invalid_task_json)
    
    def test_validate_response_json_tasks_not_list(self):
        """Test JSON validation when tasks is not a list."""
        invalid_tasks_json = '''
        {
          "page_number": 1,
          "tasks": "not a list"
        }
        '''
        
        with pytest.raises(ValueError, match="must be a list"):
            self.prompt_manager.validate_response_json(invalid_tasks_json)
    
    def test_get_statistics(self):
        """Test getting prompt manager statistics."""
        stats = self.prompt_manager.get_statistics()
        
        assert stats["total_templates"] == 5
        assert len(stats["template_types"]) == 5
        assert "avg_template_length" in stats
        assert "total_expected_tokens" in stats
        assert "templates_info" in stats
        assert stats["avg_template_length"] > 0
        assert stats["total_expected_tokens"] > 0
        
        # Check that all template types are in info
        for template_type in stats["template_types"]:
            assert template_type in stats["templates_info"]


class TestPromptType:
    """Tests for PromptType enum."""
    
    def test_prompt_type_values(self):
        """Test PromptType enum values."""
        assert PromptType.STANDARD.value == "standard"
        assert PromptType.MIXED_CONTENT.value == "mixed_content"
        assert PromptType.EXERCISE_LIST.value == "exercise_list"
        assert PromptType.WORD_PROBLEMS.value == "word_problems"
        assert PromptType.FALLBACK.value == "fallback"


class TestPromptTemplate:
    """Tests for PromptTemplate dataclass."""
    
    def test_prompt_template_creation(self):
        """Test creating PromptTemplate."""
        template = PromptTemplate(
            type=PromptType.STANDARD,
            template="Test template {page_number}",
            description="Test description",
            expected_tokens=100,
            confidence_threshold=0.8
        )
        
        assert template.type == PromptType.STANDARD
        assert template.template == "Test template {page_number}"
        assert template.description == "Test description"
        assert template.expected_tokens == 100
        assert template.confidence_threshold == 0.8
    
    def test_prompt_template_defaults(self):
        """Test PromptTemplate with default values."""
        template = PromptTemplate(
            type=PromptType.FALLBACK,
            template="Simple template",
            description="Simple description",
            expected_tokens=50
        )
        
        # confidence_threshold should have default value
        assert template.confidence_threshold == 0.8 