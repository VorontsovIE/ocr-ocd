"""Tests for DataExtractor module."""

import time
from unittest.mock import Mock, patch
import pytest
from src.core.data_extractor import DataExtractor, DataExtractionError
from src.models.task import Task
from src.models.page import Page, ProcessingStatus


class TestDataExtractor:
    """Tests for DataExtractor class."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.extractor = DataExtractor()
    
    def test_data_extractor_initialization(self):
        """Test DataExtractor initialization."""
        assert self.extractor.unknown_task_counter == 0
        assert self.extractor.session_stats["total_tasks_processed"] == 0
        assert self.extractor.session_stats["unknown_tasks_generated"] == 0
        assert self.extractor.session_stats["validation_errors"] == 0
        assert self.extractor.session_stats["text_cleanups_performed"] == 0
    
    def create_valid_api_response(self, page_number: int = 1) -> dict:
        """Create valid API response for testing."""
        return {
            "page_number": page_number,
            "tasks": [
                {
                    "task_number": "1",
                    "task_text": "Сложи 2 + 3",
                    "has_image": False,
                    "confidence": 0.95
                },
                {
                    "task_number": "2",
                    "task_text": "Реши уравнение x + 5 = 10",
                    "has_image": True,
                    "confidence": 0.87
                }
            ],
            "page_info": {
                "total_tasks": 2,
                "processing_notes": "Test page"
            }
        }
    
    def test_parse_api_response_success(self):
        """Test successful API response parsing."""
        response_data = self.create_valid_api_response(5)
        start_time = time.time() - 1.5  # Simulate 1.5 second processing
        
        page = self.extractor.parse_api_response(response_data, 5, start_time)
        
        assert page.page_number == 5
        assert len(page.tasks) == 2
        assert page.processing_status == ProcessingStatus.COMPLETED
        assert page.processing_time >= 1.0  # Should be around 1.5 seconds
        assert not page.has_errors()
        
        # Check first task
        task1 = page.tasks[0]
        assert task1.task_number == "1"
        assert task1.task_text == "Сложи 2 + 3"
        assert task1.has_image is False
        assert task1.confidence_score == 0.95
        assert task1.page_number == 5
        
        # Check second task
        task2 = page.tasks[1]
        assert task2.task_number == "2"
        assert task2.has_image is True
        assert task2.confidence_score == 0.87
    
    def test_parse_api_response_with_image_info(self):
        """Test parsing with image metadata."""
        response_data = self.create_valid_api_response(1)
        start_time = time.time()
        image_info = {
            "size_bytes": 1024000,
            "dimensions": (800, 600),
            "format": "PNG",
            "max_dimension": 800
        }
        
        page = self.extractor.parse_api_response(
            response_data, 1, start_time, image_info
        )
        
        assert page.image_size_bytes == 1024000
        assert page.image_dimensions == (800, 600)
        assert page.get_metadata("image_format") == "PNG"
        assert page.get_metadata("image_max_dimension") == 800
    
    def test_parse_api_response_invalid_structure(self):
        """Test parsing with invalid response structure."""
        start_time = time.time()
        
        # Test non-dict response
        with pytest.raises(DataExtractionError, match="must be a dictionary"):
            self.extractor.parse_api_response("invalid", 1, start_time)
        
        # Test missing tasks field
        with pytest.raises(DataExtractionError, match="missing 'tasks' field"):
            self.extractor.parse_api_response({"page_number": 1}, 1, start_time)
        
        # Test tasks not a list
        with pytest.raises(DataExtractionError, match="must be a list"):
            self.extractor.parse_api_response(
                {"page_number": 1, "tasks": "not_a_list"}, 1, start_time
            )
    
    def test_parse_api_response_with_task_errors(self):
        """Test parsing when some tasks fail extraction."""
        response_data = {
            "page_number": 1,
            "tasks": [
                {
                    "task_number": "1",
                    "task_text": "Valid task",
                    "has_image": False,
                    "confidence": 0.9
                },
                {
                    "task_number": "2"
                    # Missing required fields
                },
                {
                    "task_number": "3",
                    "task_text": "Another valid task",
                    "has_image": True,
                    "confidence": 0.8
                }
            ]
        }
        start_time = time.time()
        
        page = self.extractor.parse_api_response(response_data, 1, start_time)
        
        # Should have 2 valid tasks and 1 error
        assert len(page.tasks) == 2
        assert len(page.errors) == 1
        assert page.processing_status == ProcessingStatus.FAILED  # Has errors
        assert "Failed to extract task 1" in page.errors[0]
    
    def test_parse_api_response_page_info_validation(self):
        """Test page info validation and warnings."""
        response_data = {
            "page_number": 1,
            "tasks": [
                {
                    "task_number": "1",
                    "task_text": "Only task",
                    "has_image": False,
                    "confidence": 0.9
                }
            ],
            "page_info": {
                "total_tasks": 3,  # Expected 3, but only 1 extracted
                "processing_notes": "Test notes",
                "custom_field": "custom_value"
            }
        }
        start_time = time.time()
        
        page = self.extractor.parse_api_response(response_data, 1, start_time)
        
        assert len(page.warnings) == 1
        assert "Expected 3 tasks but extracted 1" in page.warnings[0]
        assert page.get_metadata("api_notes") == "Test notes"
        assert page.get_metadata("page_info_custom_field") == "custom_value"
    
    def test_extract_single_task_success(self):
        """Test successful single task extraction."""
        task_data = {
            "task_number": "5a",
            "task_text": "  Вычисли 7 × 8  ",
            "has_image": True,
            "confidence": 0.92,
            "extra_field": "extra_value"
        }
        
        task = self.extractor._extract_single_task(task_data, 3)
        
        assert task.page_number == 3
        assert task.task_number == "5a"
        assert task.task_text == "Вычисли 7 × 8"  # Should be cleaned
        assert task.has_image is True
        assert task.confidence_score == 0.92
        assert task.get_metadata("extraction_source") == "vision_api"
        assert task.get_metadata("raw_task_number") == "5a"
        assert task.get_metadata("api_extra_field") == "extra_value"
    
    def test_extract_single_task_missing_fields(self):
        """Test single task extraction with missing required fields."""
        incomplete_task = {
            "task_number": "1"
            # Missing task_text and has_image
        }
        
        with pytest.raises(DataExtractionError, match="Missing required field"):
            self.extractor._extract_single_task(incomplete_task, 1)
    
    def test_extract_single_task_empty_text(self):
        """Test single task extraction with empty text."""
        task_data = {
            "task_number": "1",
            "task_text": "   ",  # Empty after cleaning
            "has_image": False
        }
        
        with pytest.raises(DataExtractionError, match="Task text cannot be empty"):
            self.extractor._extract_single_task(task_data, 1)
    
    def test_extract_single_task_invalid_confidence(self):
        """Test single task extraction with invalid confidence."""
        task_data = {
            "task_number": "1",
            "task_text": "Valid text",
            "has_image": False,
            "confidence": "invalid"  # Invalid confidence
        }
        
        task = self.extractor._extract_single_task(task_data, 1)
        
        # Should handle invalid confidence gracefully
        assert task.confidence_score is None
    
    def test_process_task_number_valid(self):
        """Test task number processing with valid numbers."""
        assert self.extractor._process_task_number("1") == "1"
        assert self.extractor._process_task_number("5a") == "5a"
        assert self.extractor._process_task_number("№12") == "№12"
        assert self.extractor._process_task_number("задача-3") == "задача3"
    
    def test_process_task_number_unknown(self):
        """Test task number processing with unknown/invalid numbers."""
        # Test various unknown formats
        assert self.extractor._process_task_number("unknown").startswith("unknown-")
        assert self.extractor._process_task_number("").startswith("unknown-")
        assert self.extractor._process_task_number("null").startswith("unknown-")
        assert self.extractor._process_task_number("none").startswith("unknown-")
        
        # Test invalid characters (should clean and become empty)
        assert self.extractor._process_task_number("!@#$%").startswith("unknown-")
    
    def test_generate_unknown_task_number(self):
        """Test unknown task number generation."""
        # Reset counter for consistent testing
        self.extractor.unknown_task_counter = 0
        self.extractor.session_stats["unknown_tasks_generated"] = 0
        
        num1 = self.extractor.generate_unknown_task_number()
        num2 = self.extractor.generate_unknown_task_number()
        num3 = self.extractor.generate_unknown_task_number()
        
        assert num1 == "unknown-1"
        assert num2 == "unknown-2"
        assert num3 == "unknown-3"
        assert self.extractor.unknown_task_counter == 3
        assert self.extractor.session_stats["unknown_tasks_generated"] == 3
    
    def test_validate_task_data_valid(self):
        """Test validation with valid task data."""
        valid_data = {
            "task_number": "1",
            "task_text": "Valid task text",
            "has_image": False,
            "confidence": 0.85
        }
        
        is_valid, errors = self.extractor.validate_task_data(valid_data)
        
        assert is_valid is True
        assert len(errors) == 0
    
    def test_validate_task_data_invalid(self):
        """Test validation with invalid task data."""
        invalid_data = {
            "task_number": "1",
            # Missing task_text and has_image
            "confidence": 1.5  # Invalid confidence > 1.0
        }
        
        is_valid, errors = self.extractor.validate_task_data(invalid_data)
        
        assert is_valid is False
        assert len(errors) >= 2  # Missing fields + invalid confidence
        assert any("Missing required field: task_text" in error for error in errors)
        assert any("Missing required field: has_image" in error for error in errors)
        assert any("Confidence must be between 0.0 and 1.0" in error for error in errors)
    
    def test_validate_task_data_edge_cases(self):
        """Test validation with edge cases."""
        # Very long text
        long_text_data = {
            "task_number": "1",
            "task_text": "x" * 15000,  # Very long text
            "has_image": False
        }
        
        is_valid, errors = self.extractor.validate_task_data(long_text_data)
        assert not is_valid
        assert any("unusually long" in error for error in errors)
        
        # Invalid has_image type
        invalid_image_data = {
            "task_number": "1",
            "task_text": "Valid text",
            "has_image": "not_boolean"
        }
        
        # Should still pass because we try to convert to bool
        is_valid, errors = self.extractor.validate_task_data(invalid_image_data)
        assert is_valid  # String can be converted to bool
    
    def test_clean_task_text_basic(self):
        """Test basic text cleaning."""
        # Test whitespace cleaning
        assert self.extractor.clean_task_text("  text  ") == "text"
        assert self.extractor.clean_task_text("text   with    spaces") == "text with spaces"
        
        # Test empty text
        assert self.extractor.clean_task_text("") == ""
        assert self.extractor.clean_task_text("   ") == ""
    
    def test_clean_task_text_mathematical_symbols(self):
        """Test cleaning with mathematical symbols."""
        # Test mathematical operators
        text = "2+3=5"
        cleaned = self.extractor.clean_task_text(text)
        assert cleaned == "2 + 3 = 5"
        
        # Test mathematical symbols normalization
        text = "5×3÷2−1≤10"
        cleaned = self.extractor.clean_task_text(text)
        assert "×" in cleaned
        assert "÷" in cleaned
        assert " - " in cleaned  # minus sign normalized
        assert "≤" in cleaned
    
    def test_clean_task_text_ocr_artifacts(self):
        """Test cleaning OCR artifacts."""
        # Test bullet points removal
        text = "• Задача: вычисли ▪ результат"
        cleaned = self.extractor.clean_task_text(text)
        assert "•" not in cleaned
        assert "▪" not in cleaned
        assert "Задача: вычисли результат" in cleaned
        
        # Test pipe characters
        text = "текст || с || трубами"
        cleaned = self.extractor.clean_task_text(text)
        assert "||" not in cleaned
        assert "текст с трубами" in cleaned
        
        # Test multiple underscores
        text = "текст____с____подчёркиваниями"
        cleaned = self.extractor.clean_task_text(text)
        assert "____" not in cleaned
        assert "текст с подчёркиваниями" in cleaned
    
    def test_clean_task_text_punctuation_cleanup(self):
        """Test leading/trailing punctuation cleanup."""
        # Test leading punctuation
        text = "!@#Задача 1"
        cleaned = self.extractor.clean_task_text(text)
        assert cleaned == "Задача 1"
        
        # Test trailing punctuation (preserve valid ending punctuation)
        text = "Вычисли результат?@#"
        cleaned = self.extractor.clean_task_text(text)
        assert cleaned == "Вычисли результат?"
        
        text = "Найди ответ.@#"
        cleaned = self.extractor.clean_task_text(text)
        assert cleaned == "Найди ответ."
    
    def test_extract_multiple_pages_success(self):
        """Test successful multiple page extraction."""
        responses = [
            self.create_valid_api_response(1),
            self.create_valid_api_response(2),
            self.create_valid_api_response(3)
        ]
        page_numbers = [1, 2, 3]
        processing_times = [time.time() - 1, time.time() - 2, time.time() - 3]
        
        pages = self.extractor.extract_multiple_pages(
            responses, page_numbers, processing_times
        )
        
        assert len(pages) == 3
        assert all(page.is_processed() for page in pages)
        assert pages[0].page_number == 1
        assert pages[1].page_number == 2
        assert pages[2].page_number == 3
    
    def test_extract_multiple_pages_mismatch_error(self):
        """Test multiple page extraction with mismatched inputs."""
        responses = [self.create_valid_api_response(1)]
        page_numbers = [1, 2]  # Mismatch
        
        with pytest.raises(DataExtractionError, match="Mismatch between responses"):
            self.extractor.extract_multiple_pages(responses, page_numbers)
    
    def test_extract_multiple_pages_with_failures(self):
        """Test multiple page extraction with some failures."""
        responses = [
            self.create_valid_api_response(1),
            {"invalid": "data"},  # This will fail
            self.create_valid_api_response(3)
        ]
        page_numbers = [1, 2, 3]
        
        pages = self.extractor.extract_multiple_pages(responses, page_numbers)
        
        assert len(pages) == 3
        assert pages[0].is_processed()  # Page 1 success
        assert not pages[1].is_processed()  # Page 2 failed
        assert pages[1].processing_status == ProcessingStatus.FAILED
        assert pages[1].has_errors()
        assert pages[2].is_processed()  # Page 3 success
    
    def test_get_session_statistics(self):
        """Test getting session statistics."""
        # Process some data to generate stats
        response_data = self.create_valid_api_response(1)
        start_time = time.time()
        
        self.extractor.parse_api_response(response_data, 1, start_time)
        
        stats = self.extractor.get_session_statistics()
        
        assert "total_tasks_processed" in stats
        assert "unknown_tasks_generated" in stats
        assert "validation_errors" in stats
        assert "text_cleanups_performed" in stats
        assert "unknown_task_counter" in stats
        assert "session_duration" in stats
        
        assert stats["total_tasks_processed"] == 2  # Two tasks in test response
    
    def test_reset_session_stats(self):
        """Test resetting session statistics."""
        # Generate some stats first
        self.extractor.unknown_task_counter = 5
        self.extractor.session_stats["total_tasks_processed"] = 10
        
        self.extractor.reset_session_stats()
        
        assert self.extractor.unknown_task_counter == 0
        assert self.extractor.session_stats["total_tasks_processed"] == 0
        assert self.extractor.session_stats["unknown_tasks_generated"] == 0
        assert self.extractor.session_stats["validation_errors"] == 0
        assert self.extractor.session_stats["text_cleanups_performed"] == 0
    
    def test_task_metadata_preservation(self):
        """Test that task metadata is properly preserved."""
        task_data = {
            "task_number": "1",
            "task_text": "Test task",
            "has_image": False,
            "confidence": 0.9,
            "custom_field1": "value1",
            "custom_field2": {"nested": "value2"}
        }
        
        task = self.extractor._extract_single_task(task_data, 1)
        
        assert task.get_metadata("api_custom_field1") == "value1"
        assert task.get_metadata("api_custom_field2") == {"nested": "value2"}
        assert task.get_metadata("extraction_source") == "vision_api"
        assert task.get_metadata("raw_task_number") == "1"
    
    def test_text_cleaning_tracking(self):
        """Test that text cleaning is properly tracked in statistics."""
        # Reset stats
        self.extractor.reset_session_stats()
        
        # Text that needs cleaning
        dirty_text = "  • Задача:   вычисли    2+3  "
        clean_text = self.extractor.clean_task_text(dirty_text)
        
        assert clean_text != dirty_text
        assert self.extractor.session_stats["text_cleanups_performed"] == 1
        
        # Text that doesn't need cleaning
        already_clean = "Чистый текст"
        result = self.extractor.clean_task_text(already_clean)
        
        assert result == already_clean
        assert self.extractor.session_stats["text_cleanups_performed"] == 1  # No change


class TestDataExtractionError:
    """Tests for DataExtractionError exception."""
    
    def test_data_extraction_error_creation(self):
        """Test creating DataExtractionError."""
        error = DataExtractionError("Test extraction error")
        assert str(error) == "Test extraction error"
        assert isinstance(error, Exception)
    
    def test_data_extraction_error_inheritance(self):
        """Test DataExtractionError inheritance."""
        error = DataExtractionError("Test error")
        assert isinstance(error, Exception)
        assert error.__class__.__name__ == "DataExtractionError" 