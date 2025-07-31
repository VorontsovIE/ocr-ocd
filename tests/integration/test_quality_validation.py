"""Quality validation tests for output data."""

import time
import statistics
from typing import List, Dict, Any
from unittest.mock import Mock, patch
import pytest

from src.core.data_extractor import DataExtractor
from src.models.task import Task
from src.models.page import Page, ProcessingStatus


class TestOutputQuality:
    """Tests for validating quality of extracted data."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.extractor = DataExtractor()
    
    def create_quality_test_data(self) -> List[Dict[str, Any]]:
        """Create test data for quality validation."""
        return [
            {
                "page_number": 1,
                "tasks": [
                    {
                        "task_number": "1",
                        "task_text": "Вычисли: 25 + 37 = ?",
                        "has_image": False,
                        "confidence": 0.95
                    },
                    {
                        "task_number": "2",
                        "task_text": "Найди значение выражения: (12 + 8) × 3",
                        "has_image": True,
                        "confidence": 0.92
                    },
                    {
                        "task_number": "3а",
                        "task_text": "Сравни числа: 45 ... 54",
                        "has_image": False,
                        "confidence": 0.88
                    }
                ],
                "page_info": {
                    "total_tasks": 3,
                    "content_type": "mixed",
                    "visual_quality": "high"
                }
            },
            {
                "page_number": 2,
                "tasks": [
                    {
                        "task_number": "4",
                        "task_text": "Реши задачу: В корзине было 24 яблока. Съели 8 яблок. Сколько яблок осталось?",
                        "has_image": False,
                        "confidence": 0.97
                    },
                    {
                        "task_number": "5",
                        "task_text": "Построй график по данным таблицы",
                        "has_image": True,
                        "confidence": 0.85
                    }
                ],
                "page_info": {
                    "total_tasks": 2,
                    "content_type": "word_problems",
                    "text_density": "high"
                }
            }
        ]
    
    def test_task_text_quality_metrics(self):
        """Test quality metrics for task text extraction."""
        test_data = self.create_quality_test_data()
        start_time = time.time()
        
        all_tasks = []
        for page_data in test_data:
            page = self.extractor.parse_api_response(
                page_data, page_data["page_number"], start_time
            )
            all_tasks.extend(page.tasks)
        
        # Quality metrics
        total_tasks = len(all_tasks)
        assert total_tasks == 5
        
        # Check text length distribution
        text_lengths = [len(task.task_text) for task in all_tasks]
        avg_length = statistics.mean(text_lengths)
        assert avg_length > 10  # Meaningful text length
        assert avg_length < 200  # Not too verbose
        
        # Check text contains mathematical content
        math_keywords = ["вычисли", "найди", "сравни", "реши", "построй", "+", "-", "×", "="]
        tasks_with_math = 0
        
        for task in all_tasks:
            text_lower = task.task_text.lower()
            if any(keyword in text_lower for keyword in math_keywords):
                tasks_with_math += 1
        
        math_ratio = tasks_with_math / total_tasks
        assert math_ratio >= 0.8  # At least 80% should contain math content
    
    def test_task_numbering_quality(self):
        """Test quality of task numbering extraction."""
        test_data = self.create_quality_test_data()
        start_time = time.time()
        
        all_tasks = []
        for page_data in test_data:
            page = self.extractor.parse_api_response(
                page_data, page_data["page_number"], start_time
            )
            all_tasks.extend(page.tasks)
        
        # Check task number patterns
        task_numbers = [task.task_number for task in all_tasks]
        
        # No unknown numbers in this test data
        unknown_count = len([num for num in task_numbers if num.startswith("unknown-")])
        assert unknown_count == 0
        
        # Check variety of number formats
        numeric_pattern = len([num for num in task_numbers if num.isdigit()])
        alpha_pattern = len([num for num in task_numbers if any(c.isalpha() for c in num)])
        
        assert numeric_pattern >= 3  # At least 3 numeric numbers
        assert alpha_pattern >= 1   # At least 1 with letters (like "3а")
        
        # Check uniqueness
        assert len(set(task_numbers)) == len(task_numbers)  # All unique
    
    def test_confidence_score_distribution(self):
        """Test distribution and quality of confidence scores."""
        test_data = self.create_quality_test_data()
        start_time = time.time()
        
        all_tasks = []
        for page_data in test_data:
            page = self.extractor.parse_api_response(
                page_data, page_data["page_number"], start_time
            )
            all_tasks.extend(page.tasks)
        
        # Check confidence scores
        confidence_scores = [
            task.confidence_score for task in all_tasks 
            if task.confidence_score is not None
        ]
        
        assert len(confidence_scores) == len(all_tasks)  # All tasks have confidence
        
        # Check confidence range
        assert all(0.0 <= score <= 1.0 for score in confidence_scores)
        
        # Check reasonable distribution
        avg_confidence = statistics.mean(confidence_scores)
        assert avg_confidence >= 0.8  # High quality extraction should have high confidence
        
        # Check that tasks with images have lower confidence on average
        image_tasks = [task for task in all_tasks if task.has_image]
        no_image_tasks = [task for task in all_tasks if not task.has_image]
        
        if image_tasks and no_image_tasks:
            avg_image_confidence = statistics.mean([t.confidence_score for t in image_tasks])
            avg_no_image_confidence = statistics.mean([t.confidence_score for t in no_image_tasks])
            
            # Tasks with images typically harder to process
            assert avg_image_confidence <= avg_no_image_confidence + 0.1
    
    def test_page_metadata_preservation(self):
        """Test that page metadata is properly preserved and enriched."""
        test_data = self.create_quality_test_data()
        start_time = time.time()
        
        pages = []
        for page_data in test_data:
            page = self.extractor.parse_api_response(
                page_data, page_data["page_number"], start_time
            )
            pages.append(page)
        
        # Check page 1 metadata
        page1 = pages[0]
        assert page1.get_metadata("page_info_content_type") == "mixed"
        assert page1.get_metadata("page_info_visual_quality") == "high"
        
        # Check page 2 metadata  
        page2 = pages[1]
        assert page2.get_metadata("page_info_content_type") == "word_problems"
        assert page2.get_metadata("page_info_text_density") == "high"
        
        # Check that all pages have processing metadata
        for page in pages:
            assert page.processing_time > 0
            assert page.processing_status == ProcessingStatus.COMPLETED
            assert page.processed_at is not None
    
    def test_data_consistency_validation(self):
        """Test consistency of extracted data across pages."""
        test_data = self.create_quality_test_data()
        start_time = time.time()
        
        pages = []
        for page_data in test_data:
            page = self.extractor.parse_api_response(
                page_data, page_data["page_number"], start_time
            )
            pages.append(page)
        
        # Check page numbering consistency
        page_numbers = [page.page_number for page in pages]
        assert page_numbers == [1, 2]
        
        # Check task numbering progression
        all_task_numbers = []
        for page in pages:
            for task in page.tasks:
                all_task_numbers.append(task.task_number)
        
        # Should have variety but no duplicates
        assert len(set(all_task_numbers)) == len(all_task_numbers)
        
        # Check that all tasks belong to correct pages
        for page in pages:
            for task in page.tasks:
                assert task.page_number == page.page_number
    
    def test_text_cleaning_effectiveness(self):
        """Test effectiveness of text cleaning operations."""
        # Create test data with various cleaning challenges
        dirty_data = {
            "page_number": 1,
            "tasks": [
                {
                    "task_number": "1",  
                    "task_text": "  • Вычисли:   2 + 3 =  ? ",  # Extra spaces, bullet
                    "has_image": False,
                    "confidence": 0.9
                },
                {
                    "task_number": "2",
                    "task_text": "Найди||значение||выражения: 5×3÷2−1",  # Pipes, math symbols
                    "has_image": False,
                    "confidence": 0.85
                },
                {
                    "task_number": "3",
                    "task_text": "!@#Реши задачу про яблоки.@#!",  # Leading/trailing junk
                    "has_image": False,
                    "confidence": 0.92
                }
            ]
        }
        
        start_time = time.time()
        page = self.extractor.parse_api_response(dirty_data, 1, start_time)
        
        # Check cleaning results
        task1_text = page.tasks[0].task_text
        assert task1_text == "Вычисли: 2 + 3 = ?"
        assert "•" not in task1_text
        assert task1_text.count(" ") == 4  # Proper spacing
        
        task2_text = page.tasks[1].task_text
        assert "||" not in task2_text
        assert " × " in task2_text  # Proper math symbol spacing
        assert " ÷ " in task2_text
        assert " - " in task2_text
        
        task3_text = page.tasks[2].task_text
        assert task3_text == "Реши задачу про яблоки."
        assert not task3_text.startswith("!")
        assert not task3_text.endswith("!")
        
        # Check statistics tracking
        stats = self.extractor.get_session_statistics()
        assert stats["text_cleanups_performed"] >= 3
    
    def test_multilingual_content_handling(self):
        """Test handling of mixed Russian/mathematical content."""
        multilingual_data = {
            "page_number": 1,
            "tasks": [
                {
                    "task_number": "1",
                    "task_text": "Вычисли: 2² + 3² = ?",  # Russian + mathematical notation
                    "has_image": False,
                    "confidence": 0.9
                },
                {
                    "task_number": "2",
                    "task_text": "Найди x: 2x + 5 = 15",  # Russian + algebra
                    "has_image": False,
                    "confidence": 0.87
                },
                {
                    "task_number": "№3",
                    "task_text": "Построй график функции y = 2x + 1",  # Number sign + function
                    "has_image": True,
                    "confidence": 0.85
                }
            ]
        }
        
        start_time = time.time()
        page = self.extractor.parse_api_response(multilingual_data, 1, start_time)
        
        # Verify all tasks extracted properly
        assert len(page.tasks) == 3
        
        # Check that mathematical notation is preserved
        task1 = page.tasks[0]
        assert "2²" in task1.task_text
        assert "3²" in task1.task_text
        
        task2 = page.tasks[1]
        assert "2x" in task2.task_text
        assert " x:" in task2.task_text  # Proper spacing around variable
        
        task3 = page.tasks[2]
        assert task3.task_number == "№3"  # Number sign preserved
        assert "y = 2x" in task3.task_text
    
    def test_edge_case_handling(self):
        """Test handling of edge cases in data extraction."""
        edge_cases_data = {
            "page_number": 1,
            "tasks": [
                {
                    "task_number": "",  # Empty task number
                    "task_text": "Task with empty number",
                    "has_image": False,
                    "confidence": 0.8
                },
                {
                    "task_number": "1",
                    "task_text": "A",  # Very short text
                    "has_image": False,
                    "confidence": 0.6
                },
                {
                    "task_number": "2",
                    "task_text": "Very long task text that goes on and on and contains lots of details about the mathematical problem including multiple steps and explanations that might be typical in more advanced textbooks but could also appear in elementary materials",
                    "has_image": False,
                    "confidence": 0.9
                },
                {
                    "task_number": "3",
                    "task_text": "Normal task",
                    "has_image": False,
                    "confidence": None  # Missing confidence
                }
            ]
        }
        
        start_time = time.time()
        page = self.extractor.parse_api_response(edge_cases_data, 1, start_time)
        
        # All tasks should be extracted
        assert len(page.tasks) == 4
        
        # Check empty task number handling
        task1 = page.tasks[0]
        assert task1.task_number.startswith("unknown-")
        
        # Check very short text
        task2 = page.tasks[1]
        assert task2.task_text == "A"
        assert task2.task_number == "1"
        
        # Check very long text
        task3 = page.tasks[2]
        assert len(task3.task_text) > 100
        assert task3.task_number == "2"
        
        # Check missing confidence
        task4 = page.tasks[3]
        assert task4.confidence_score is None
        assert task4.task_number == "3"
    
    def test_performance_quality_relationship(self):
        """Test relationship between processing performance and quality."""
        # Create data with varying complexity
        simple_data = {
            "page_number": 1,
            "tasks": [
                {"task_number": "1", "task_text": "2 + 2", "has_image": False, "confidence": 0.95}
            ]
        }
        
        complex_data = {
            "page_number": 2,
            "tasks": [
                {
                    "task_number": "1",
                    "task_text": "Реши сложную задачу с несколькими условиями и найди все возможные решения",
                    "has_image": True,
                    "confidence": 0.82
                },
                {
                    "task_number": "2а",
                    "task_text": "Построй диаграмму по следующим данным",
                    "has_image": True,
                    "confidence": 0.78
                }
            ]
        }
        
        # Process both types
        start_time = time.time()
        simple_page = self.extractor.parse_api_response(simple_data, 1, start_time)
        
        start_time = time.time()  
        complex_page = self.extractor.parse_api_response(complex_data, 2, start_time)
        
        # Simple pages should process faster and with higher confidence
        assert simple_page.processing_time <= complex_page.processing_time
        
        simple_avg_confidence = statistics.mean([
            t.confidence_score for t in simple_page.tasks if t.confidence_score
        ])
        complex_avg_confidence = statistics.mean([
            t.confidence_score for t in complex_page.tasks if t.confidence_score
        ])
        
        # Simple content typically has higher confidence
        assert simple_avg_confidence >= complex_avg_confidence - 0.1
    
    def test_batch_processing_quality_consistency(self):
        """Test that batch processing maintains quality consistency."""
        # Create multiple similar pages
        batch_data = []
        for i in range(1, 4):
            batch_data.append({
                "page_number": i,
                "tasks": [
                    {
                        "task_number": str(j),
                        "task_text": f"Задача {j}: Вычисли {j * 2} + {j * 3}",
                        "has_image": j % 2 == 0,
                        "confidence": 0.9 - (j * 0.05)
                    }
                    for j in range(1, 4)  # 3 tasks per page
                ]
            })
        
        # Process batch
        pages = self.extractor.extract_multiple_pages(
            batch_data, 
            [1, 2, 3],
            [time.time() - i for i in range(3)]
        )
        
        # Check consistency across pages
        assert len(pages) == 3
        assert all(page.is_processed() for page in pages)
        assert all(len(page.tasks) == 3 for page in pages)
        
        # Check quality metrics consistency
        all_confidences = []
        all_text_lengths = []
        
        for page in pages:
            for task in page.tasks:
                if task.confidence_score:
                    all_confidences.append(task.confidence_score)
                all_text_lengths.append(len(task.task_text))
        
        # Quality should be consistent across batch
        confidence_std = statistics.stdev(all_confidences)
        assert confidence_std < 0.2  # Low variation in confidence
        
        text_length_std = statistics.stdev(all_text_lengths)
        avg_text_length = statistics.mean(all_text_lengths)
        cv = text_length_std / avg_text_length  # Coefficient of variation
        assert cv < 0.5  # Reasonable consistency in text lengths


class TestQualityMetrics:
    """Additional quality metrics and validation tests."""
    
    def test_calculate_extraction_accuracy(self):
        """Test calculation of extraction accuracy metrics."""
        # This would typically use reference data, but for demo purposes
        # we'll create a synthetic validation scenario
        
        extractor = DataExtractor()
        
        # Simulate extraction results vs expected results
        extracted_tasks = [
            Task(page_number=1, task_number="1", task_text="Task 1", has_image=False),
            Task(page_number=1, task_number="2", task_text="Task 2", has_image=True),
            Task(page_number=1, task_number="unknown-1", task_text="Task 3", has_image=False),
        ]
        
        expected_tasks = [
            {"task_number": "1", "task_text": "Task 1", "has_image": False},
            {"task_number": "2", "task_text": "Task 2", "has_image": True},
            {"task_number": "3", "task_text": "Task 3", "has_image": False},  # Should match unknown-1
        ]
        
        # Calculate accuracy metrics
        task_count_accuracy = len(extracted_tasks) / len(expected_tasks)
        assert task_count_accuracy == 1.0  # Got all tasks
        
        # Number extraction accuracy (2 out of 3 correct)
        correct_numbers = 0
        for i, task in enumerate(extracted_tasks):
            expected_num = expected_tasks[i]["task_number"]
            if task.task_number == expected_num or (
                task.task_number.startswith("unknown-") and expected_num == "3"
            ):
                correct_numbers += 1
        
        number_accuracy = correct_numbers / len(extracted_tasks)
        assert number_accuracy >= 0.66  # At least 2/3 correct
        
        # Text extraction accuracy (exact matches)
        correct_texts = sum(
            1 for i, task in enumerate(extracted_tasks)
            if task.task_text == expected_tasks[i]["task_text"]
        )
        text_accuracy = correct_texts / len(extracted_tasks)
        assert text_accuracy == 1.0  # All text should match exactly
    
    def test_quality_scoring_system(self):
        """Test comprehensive quality scoring system."""
        extractor = DataExtractor()
        
        # High quality data
        high_quality_data = {
            "page_number": 1,
            "tasks": [
                {"task_number": "1", "task_text": "Clear task text", "has_image": False, "confidence": 0.95},
                {"task_number": "2", "task_text": "Another clear task", "has_image": True, "confidence": 0.92}
            ]
        }
        
        # Lower quality data
        lower_quality_data = {
            "page_number": 2,
            "tasks": [
                {"task_number": "", "task_text": "  unclear   text  ", "has_image": False, "confidence": 0.65},
                {"task_number": "?", "task_text": "Very unclear and confusing task description", "has_image": True, "confidence": 0.58}
            ]
        }
        
        start_time = time.time()
        high_page = extractor.parse_api_response(high_quality_data, 1, start_time)
        low_page = extractor.parse_api_response(lower_quality_data, 2, start_time)
        
        # Calculate quality scores
        def calculate_page_quality_score(page: Page) -> float:
            """Calculate quality score for a page (0-100)."""
            if not page.tasks:
                return 0.0
                
            factors = []
            
            # Confidence factor
            confidences = [t.confidence_score for t in page.tasks if t.confidence_score]
            if confidences:
                confidence_factor = statistics.mean(confidences) * 100
                factors.append(confidence_factor)
            
            # Task number factor (penalty for unknown numbers)
            unknown_count = len([t for t in page.tasks if t.task_number.startswith("unknown-")])
            number_factor = max(0, 100 - (unknown_count / len(page.tasks)) * 50)
            factors.append(number_factor)
            
            # Text quality factor (based on length and cleaning)
            text_lengths = [len(t.task_text) for t in page.tasks]
            avg_length = statistics.mean(text_lengths)
            length_factor = min(100, avg_length * 2)  # Reasonable text length
            factors.append(length_factor)
            
            # Processing success factor
            success_factor = 100 if page.is_processed() else 0
            factors.append(success_factor)
            
            return statistics.mean(factors)
        
        high_score = calculate_page_quality_score(high_page)
        low_score = calculate_page_quality_score(low_page)
        
        assert high_score > low_score
        assert high_score >= 85  # High quality should score well
        assert low_score <= 75   # Lower quality should score lower 