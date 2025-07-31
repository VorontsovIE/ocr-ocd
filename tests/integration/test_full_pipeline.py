"""Integration tests for full processing pipeline."""

import time
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest
from PIL import Image
import io

from src.core.pdf_processor import PDFProcessor, PDFProcessingError
from src.core.vision_client import VisionClient, VisionAPIError
from src.core.data_extractor import DataExtractor, DataExtractionError
from src.core.prompt_manager import PromptManager, PromptType
from src.models.task import Task
from src.models.page import Page, ProcessingStatus
from src.utils.config import APIConfig


class TestFullPipeline:
    """Integration tests for the complete processing pipeline."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = APIConfig(
            api_key="test_api_key",
            model_name="gpt-4-vision-preview",
            max_tokens=4096,
            temperature=0.1,
            timeout=60,
            max_retries=3,
            retry_delay=1
        )
        
        # Create test components
        self.pdf_processor = None  # Will be created in tests
        self.vision_client = None  # Will be created in tests  
        self.data_extractor = DataExtractor()
        self.prompt_manager = PromptManager()
    
    def create_test_pdf(self, page_count: int = 3) -> Path:
        """Create a test PDF file with multiple pages.
        
        Args:
            page_count: Number of pages to create
            
        Returns:
            Path to created PDF file
        """
        pdf_path = self.temp_dir / "test_math_book.pdf"
        
        # This would normally create a real PDF, but for testing we'll mock it
        # In a real implementation, you'd use a library like reportlab
        pdf_path.touch()  # Create empty file for now
        
        return pdf_path
    
    def create_mock_api_response(self, page_number: int, task_count: int = 2) -> str:
        """Create mock API response JSON.
        
        Args:
            page_number: Page number
            task_count: Number of tasks to include
            
        Returns:
            JSON string response
        """
        import json
        
        tasks = []
        for i in range(1, task_count + 1):
            tasks.append({
                "task_number": str(i),
                "task_text": f"Задача {i}: Вычисли {i} + {i} = ?",
                "has_image": i % 2 == 0,  # Every second task has image
                "confidence": 0.9 - (i * 0.1)
            })
        
        response = {
            "page_number": page_number,
            "tasks": tasks,
            "page_info": {
                "total_tasks": task_count,
                "processing_notes": f"Test page {page_number}"
            }
        }
        
        return json.dumps(response, ensure_ascii=False)
    
    @patch('src.core.vision_client.OpenAI')
    @patch('src.core.pdf_processor.fitz')
    def test_pipeline_pdf_to_tasks_success(self, mock_fitz, mock_openai):
        """Test complete pipeline from PDF to extracted tasks."""
        # Setup PDF processor mock
        mock_doc = Mock()
        mock_doc.__len__ = Mock(return_value=2)  # 2 pages
        
        mock_page = Mock()
        mock_pix = Mock()
        mock_pix.tobytes.return_value = b"fake_image_data"
        mock_page.get_pixmap.return_value = mock_pix
        mock_doc.__getitem__.return_value = mock_page
        
        mock_fitz.open.return_value = mock_doc
        
        # Setup Vision API mock
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        mock_choice = Mock()
        mock_usage = Mock()
        mock_usage.total_tokens = 150
        mock_usage.model_dump.return_value = {"total_tokens": 150}
        
        # Create different responses for each page
        page1_response = self.create_mock_api_response(1, 2)
        page2_response = self.create_mock_api_response(2, 3)
        
        mock_choice.message.content = page1_response
        mock_response1 = Mock()
        mock_response1.choices = [mock_choice]
        mock_response1.usage = mock_usage
        mock_response1.model = "gpt-4-vision-preview"
        
        mock_choice2 = Mock()
        mock_choice2.message.content = page2_response
        mock_response2 = Mock()
        mock_response2.choices = [mock_choice2]
        mock_response2.usage = mock_usage
        mock_response2.model = "gpt-4-vision-preview"
        
        mock_client.chat.completions.create.side_effect = [mock_response1, mock_response2]
        
        # Create test PDF
        pdf_path = self.create_test_pdf(2)
        
        # Initialize components
        pdf_processor = PDFProcessor(pdf_path, temp_dir=self.temp_dir)
        vision_client = VisionClient(self.config)
        
        # Process PDF pages
        with pdf_processor:
            all_pages = []
            page_count = pdf_processor.get_page_count()
            
            for page_num in range(page_count):
                # Convert page to image
                image_data = pdf_processor.convert_page_to_image(page_num)
                
                # Extract tasks with Vision API
                start_time = time.time()
                api_response = vision_client.extract_tasks_from_page(
                    image_data, page_num + 1  # 1-indexed
                )
                
                # Parse API response to create Page object
                if api_response["json_valid"]:
                    page = self.data_extractor.parse_api_response(
                        api_response["parsed_data"],
                        page_num + 1,
                        start_time,
                        api_response["image_info"]
                    )
                    all_pages.append(page)
        
        # Verify results
        assert len(all_pages) == 2
        
        # Check page 1
        page1 = all_pages[0]
        assert page1.page_number == 1
        assert len(page1.tasks) == 2
        assert page1.is_processed()
        assert page1.tasks[0].task_number == "1"
        assert "Задача 1" in page1.tasks[0].task_text
        
        # Check page 2
        page2 = all_pages[1]
        assert page2.page_number == 2
        assert len(page2.tasks) == 3
        assert page2.is_processed()
        
        # Verify total task count
        total_tasks = sum(len(page.tasks) for page in all_pages)
        assert total_tasks == 5
    
    @patch('src.core.vision_client.OpenAI')
    @patch('src.core.pdf_processor.fitz')
    def test_pipeline_with_api_errors(self, mock_fitz, mock_openai):
        """Test pipeline behavior when API errors occur."""
        # Setup PDF processor
        mock_doc = Mock()
        mock_doc.__len__ = Mock(return_value=1)
        mock_page = Mock()
        mock_pix = Mock()
        mock_pix.tobytes.return_value = b"fake_image_data"
        mock_page.get_pixmap.return_value = mock_pix
        mock_doc.__getitem__.return_value = mock_page
        mock_fitz.open.return_value = mock_doc
        
        # Setup Vision API to fail
        mock_client = Mock()
        mock_openai.return_value = mock_client
        from openai import RateLimitError
        
        rate_limit_error = RateLimitError(
            message="Rate limit exceeded",
            response=Mock(status_code=429),
            body={"error": {"message": "Rate limit exceeded"}}
        )
        
        mock_client.chat.completions.create.side_effect = rate_limit_error
        
        pdf_path = self.create_test_pdf(1)
        pdf_processor = PDFProcessor(pdf_path, temp_dir=self.temp_dir)
        vision_client = VisionClient(self.config)
        
        # Process should fail gracefully
        with pdf_processor:
            image_data = pdf_processor.convert_page_to_image(0)
            
            with pytest.raises(VisionAPIError):
                vision_client.extract_tasks_from_page(image_data, 1)
    
    @patch('src.core.vision_client.OpenAI')
    @patch('src.core.pdf_processor.fitz')
    def test_pipeline_with_invalid_json_fallback(self, mock_fitz, mock_openai):
        """Test pipeline with invalid JSON response and fallback."""
        # Setup PDF processor
        mock_doc = Mock()
        mock_doc.__len__ = Mock(return_value=1)
        mock_page = Mock()
        mock_pix = Mock()
        mock_pix.tobytes.return_value = b"fake_image_data"
        mock_page.get_pixmap.return_value = mock_pix
        mock_doc.__getitem__.return_value = mock_page
        mock_fitz.open.return_value = mock_doc
        
        # Setup Vision API responses
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        mock_usage = Mock()
        mock_usage.total_tokens = 100
        mock_usage.model_dump.return_value = {"total_tokens": 100}
        
        # First response: invalid JSON
        mock_choice1 = Mock()
        mock_choice1.message.content = "Invalid JSON response"
        mock_response1 = Mock()
        mock_response1.choices = [mock_choice1]
        mock_response1.usage = mock_usage
        mock_response1.model = "gpt-4-vision-preview"
        
        # Second response: valid JSON (fallback)
        mock_choice2 = Mock()
        mock_choice2.message.content = self.create_mock_api_response(1, 1)
        mock_response2 = Mock()
        mock_response2.choices = [mock_choice2]
        mock_response2.usage = mock_usage
        mock_response2.model = "gpt-4-vision-preview"
        
        mock_client.chat.completions.create.side_effect = [mock_response1, mock_response2]
        
        pdf_path = self.create_test_pdf(1)
        pdf_processor = PDFProcessor(pdf_path, temp_dir=self.temp_dir)
        vision_client = VisionClient(self.config)
        
        with pdf_processor:
            image_data = pdf_processor.convert_page_to_image(0)
            
            # Should retry with fallback prompt
            api_response = vision_client.extract_tasks_from_page(
                image_data, 1, use_fallback_on_error=True
            )
            
            assert api_response["json_valid"] is True
            assert api_response["prompt_type"] == "fallback"
            
            # Should be able to extract page
            page = self.data_extractor.parse_api_response(
                api_response["parsed_data"],
                1,
                time.time(),
                api_response["image_info"]
            )
            
            assert page.page_number == 1
            assert len(page.tasks) == 1
            assert page.is_processed()
    
    def test_data_extractor_with_different_prompt_types(self):
        """Test data extractor with responses from different prompt types."""
        # Test standard prompt response
        standard_response = {
            "page_number": 1,
            "tasks": [
                {
                    "task_number": "1",
                    "task_text": "Стандартная задача",
                    "has_image": False,
                    "confidence": 0.9
                }
            ],
            "page_info": {"total_tasks": 1}
        }
        
        # Test exercise list response
        exercise_response = {
            "page_number": 2,
            "tasks": [
                {
                    "task_number": "1а",
                    "task_text": "2 + 2 = ?",
                    "has_image": False,
                    "confidence": 0.95
                },
                {
                    "task_number": "1б",
                    "task_text": "3 + 3 = ?",
                    "has_image": False,
                    "confidence": 0.95
                }
            ],
            "page_info": {"total_tasks": 2, "content_type": "exercise_list"}
        }
        
        # Test mixed content response
        mixed_response = {
            "page_number": 3,
            "tasks": [
                {
                    "task_number": "1",
                    "task_text": "Задача с диаграммой",
                    "has_image": True,
                    "confidence": 0.85
                }
            ],
            "page_info": {"total_tasks": 1, "visual_elements": ["диаграмма"]}
        }
        
        start_time = time.time()
        
        # Extract all pages
        page1 = self.data_extractor.parse_api_response(standard_response, 1, start_time)
        page2 = self.data_extractor.parse_api_response(exercise_response, 2, start_time)
        page3 = self.data_extractor.parse_api_response(mixed_response, 3, start_time)
        
        # Verify each page type
        assert page1.get_task_count() == 1
        assert not page1.tasks[0].has_image
        
        assert page2.get_task_count() == 2
        assert page2.tasks[0].task_number == "1а"
        assert page2.tasks[1].task_number == "1б"
        
        assert page3.get_task_count() == 1
        assert page3.tasks[0].has_image is True
        assert "диаграмма" in page3.get_metadata("page_info_visual_elements")
    
    def test_prompt_selection_logic(self):
        """Test automatic prompt selection based on page hints."""
        # Test with different hint combinations
        test_cases = [
            # (hints, expected_prompt_type_in_content)
            ({"has_images": True}, "диаграммами"),  # Mixed content
            ({"estimated_problems": 8, "text_density": "low"}, "упражнений"),  # Exercise list
            ({"text_density": "high"}, "текстовые"),  # Word problems
            ({}, "начальной школы")  # Standard (default)
        ]
        
        for hints, expected_marker in test_cases:
            prompt = self.prompt_manager.get_prompt_auto(1, hints)
            assert expected_marker in prompt
            assert "страницу 1" in prompt
    
    def test_session_statistics_tracking(self):
        """Test that session statistics are properly tracked across pipeline."""
        # Reset stats
        self.data_extractor.reset_session_stats()
        
        # Process multiple responses
        responses = [
            {
                "page_number": 1,
                "tasks": [
                    {"task_number": "1", "task_text": "Task 1", "has_image": False},
                    {"task_number": "unknown", "task_text": "Task 2", "has_image": True}
                ]
            },
            {
                "page_number": 2,
                "tasks": [
                    {"task_number": "  3  ", "task_text": "  • Task 3  ", "has_image": False}
                ]
            }
        ]
        
        start_time = time.time()
        
        for i, response in enumerate(responses, 1):
            self.data_extractor.parse_api_response(response, i, start_time)
        
        stats = self.data_extractor.get_session_statistics()
        
        assert stats["total_tasks_processed"] == 3
        assert stats["unknown_tasks_generated"] == 1  # One "unknown" task
        assert stats["text_cleanups_performed"] >= 1  # "• Task 3" was cleaned
    
    @patch('src.core.vision_client.OpenAI') 
    def test_performance_benchmarking(self, mock_openai):
        """Test performance characteristics of the pipeline."""
        # Setup fast mock API
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        mock_choice = Mock()
        mock_choice.message.content = self.create_mock_api_response(1, 5)  # 5 tasks per page
        
        mock_usage = Mock()
        mock_usage.total_tokens = 200
        mock_usage.model_dump.return_value = {"total_tokens": 200}
        
        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage
        mock_response.model = "gpt-4-vision-preview"
        
        mock_client.chat.completions.create.return_value = mock_response
        
        vision_client = VisionClient(self.config)
        
        # Create test image
        test_image = Image.new('RGB', (100, 100), color='white')
        img_buffer = io.BytesIO()
        test_image.save(img_buffer, format='PNG')
        image_data = img_buffer.getvalue()
        
        # Benchmark API + extraction time
        page_count = 5
        start_time = time.time()
        
        all_pages = []
        for page_num in range(1, page_count + 1):
            api_start = time.time()
            api_response = vision_client.extract_tasks_from_page(image_data, page_num)
            
            if api_response["json_valid"]:
                page = self.data_extractor.parse_api_response(
                    api_response["parsed_data"],
                    page_num,
                    api_start,
                    api_response["image_info"]
                )
                all_pages.append(page)
        
        total_time = time.time() - start_time
        
        # Performance assertions
        assert len(all_pages) == page_count
        assert total_time < 5.0  # Should process 5 pages in under 5 seconds (mocked)
        
        total_tasks = sum(len(page.tasks) for page in all_pages)
        assert total_tasks == page_count * 5  # 5 tasks per page
        
        avg_time_per_page = total_time / page_count
        assert avg_time_per_page < 1.0  # Less than 1 second per page (mocked)
    
    def test_error_recovery_and_continuation(self):
        """Test that pipeline can recover from errors and continue processing."""
        # Simulate processing multiple pages where some fail
        responses = [
            # Page 1: Success
            {
                "page_number": 1,
                "tasks": [{"task_number": "1", "task_text": "Good task", "has_image": False}]
            },
            # Page 2: Invalid structure (will fail)
            {"invalid": "structure"},
            # Page 3: Success
            {
                "page_number": 3,
                "tasks": [{"task_number": "2", "task_text": "Another good task", "has_image": True}]
            }
        ]
        
        page_numbers = [1, 2, 3]
        
        # Use batch processing method which handles errors gracefully
        pages = self.data_extractor.extract_multiple_pages(responses, page_numbers)
        
        assert len(pages) == 3
        
        # Page 1: Success
        assert pages[0].is_processed()
        assert len(pages[0].tasks) == 1
        
        # Page 2: Failed
        assert not pages[1].is_processed()
        assert pages[1].processing_status == ProcessingStatus.FAILED
        assert pages[1].has_errors()
        
        # Page 3: Success (recovered)
        assert pages[2].is_processed()
        assert len(pages[2].tasks) == 1
    
    def teardown_method(self):
        """Cleanup test fixtures."""
        # Clean up temporary directory
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir) 