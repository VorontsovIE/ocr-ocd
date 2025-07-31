"""Tests for data models."""

import pytest
from datetime import datetime
from src.models.task import Task
from src.models.page import Page, ProcessingStatus


class TestTask:
    """Tests for Task model."""
    
    def test_task_creation_minimal(self):
        """Test creating task with minimal required fields."""
        task = Task(
            page_number=1,
            task_number="1",
            task_text="Solve 2 + 2"
        )
        
        assert task.page_number == 1
        assert task.task_number == "1"
        assert task.task_text == "Solve 2 + 2"
        assert task.has_image is False
        assert task.confidence_score is None
        assert task.processing_time is None
        assert isinstance(task.extraction_metadata, dict)
        assert isinstance(task.created_at, datetime)
    
    def test_task_creation_full(self):
        """Test creating task with all fields."""
        metadata = {"source": "test", "model": "gpt-4"}
        
        task = Task(
            page_number=5,
            task_number="unknown-1",
            task_text="Calculate the area of rectangle",
            has_image=True,
            confidence_score=0.85,
            processing_time=2.5,
            extraction_metadata=metadata
        )
        
        assert task.page_number == 5
        assert task.task_number == "unknown-1"
        assert task.task_text == "Calculate the area of rectangle"
        assert task.has_image is True
        assert task.confidence_score == 0.85
        assert task.processing_time == 2.5
        assert task.extraction_metadata == metadata
    
    def test_task_validation_page_number(self):
        """Test page number validation."""
        # Valid page number
        task = Task(page_number=1, task_number="1", task_text="Test")
        assert task.page_number == 1
        
        # Invalid page number (zero)
        with pytest.raises(ValueError):
            Task(page_number=0, task_number="1", task_text="Test")
        
        # Invalid page number (negative)
        with pytest.raises(ValueError):
            Task(page_number=-1, task_number="1", task_text="Test")
    
    def test_task_validation_task_number(self):
        """Test task number validation."""
        # Valid task numbers
        valid_numbers = ["1", "unknown-1", "№5", "задача 3"]
        for num in valid_numbers:
            task = Task(page_number=1, task_number=num, task_text="Test")
            assert task.task_number == num.strip()
        
        # Invalid task number (empty)
        with pytest.raises(ValueError, match="Task number cannot be empty"):
            Task(page_number=1, task_number="", task_text="Test")
        
        # Invalid task number (whitespace only)
        with pytest.raises(ValueError, match="Task number cannot be empty"):
            Task(page_number=1, task_number="   ", task_text="Test")
    
    def test_task_validation_task_text(self):
        """Test task text validation."""
        # Valid task text
        task = Task(page_number=1, task_number="1", task_text="  Valid text  ")
        assert task.task_text == "Valid text"  # Should be trimmed
        
        # Text with excessive whitespace
        task = Task(page_number=1, task_number="1", task_text="Text   with    spaces")
        assert task.task_text == "Text with spaces"  # Should normalize spaces
        
        # Invalid task text (empty)
        with pytest.raises(ValueError, match="Task text cannot be empty"):
            Task(page_number=1, task_number="1", task_text="")
        
        # Invalid task text (whitespace only)
        with pytest.raises(ValueError, match="Task text cannot be empty"):
            Task(page_number=1, task_number="1", task_text="   ")
    
    def test_task_validation_confidence_score(self):
        """Test confidence score validation."""
        # Valid confidence scores
        for score in [0.0, 0.5, 1.0]:
            task = Task(
                page_number=1, task_number="1", task_text="Test",
                confidence_score=score
            )
            assert task.confidence_score == score
        
        # Invalid confidence scores
        with pytest.raises(ValueError):
            Task(
                page_number=1, task_number="1", task_text="Test",
                confidence_score=-0.1
            )
        
        with pytest.raises(ValueError):
            Task(
                page_number=1, task_number="1", task_text="Test",
                confidence_score=1.1
            )
    
    def test_task_low_confidence_warning(self):
        """Test low confidence warning in metadata."""
        task = Task(
            page_number=1, task_number="1", task_text="Test",
            confidence_score=0.2
        )
        
        assert task.extraction_metadata.get('low_confidence_warning') is True
    
    def test_task_to_csv_row(self):
        """Test CSV row conversion."""
        task = Task(
            page_number=1,
            task_number="1",
            task_text="Test task",
            has_image=True,
            confidence_score=0.9,
            processing_time=1.5
        )
        
        csv_row = task.to_csv_row()
        
        assert csv_row["page_number"] == 1
        assert csv_row["task_number"] == "1"
        assert csv_row["task_text"] == "Test task"
        assert csv_row["has_image"] is True
        assert csv_row["confidence_score"] == 0.9
        assert csv_row["processing_time"] == 1.5
        assert "created_at" in csv_row
    
    def test_task_to_json(self):
        """Test JSON conversion."""
        task = Task(
            page_number=1,
            task_number="1", 
            task_text="Test task",
            extraction_metadata={"test": "data"}
        )
        
        # Without metadata
        json_str = task.to_json(include_metadata=False)
        assert "extraction_metadata" not in json_str
        assert "Test task" in json_str
        
        # With metadata
        json_str = task.to_json(include_metadata=True)
        assert "extraction_metadata" in json_str
        assert "test" in json_str
    
    def test_task_get_display_text(self):
        """Test display text method."""
        # Short text
        task = Task(page_number=1, task_number="1", task_text="Short")
        assert task.get_display_text(100) == "Short"
        
        # Long text
        long_text = "A" * 200
        task = Task(page_number=1, task_number="1", task_text=long_text)
        display = task.get_display_text(50)
        assert len(display) == 50
        assert display.endswith("...")
    
    def test_task_is_unknown_number(self):
        """Test unknown number detection."""
        # Unknown number
        task = Task(page_number=1, task_number="unknown-1", task_text="Test")
        assert task.is_unknown_number() is True
        
        # Known number
        task = Task(page_number=1, task_number="1", task_text="Test")
        assert task.is_unknown_number() is False
    
    def test_task_get_word_count(self):
        """Test word count method."""
        task = Task(page_number=1, task_number="1", task_text="This has five words")
        assert task.get_word_count() == 4  # "This", "has", "five", "words"
    
    def test_task_is_high_confidence(self):
        """Test high confidence detection."""
        # High confidence
        task = Task(
            page_number=1, task_number="1", task_text="Test",
            confidence_score=0.9
        )
        assert task.is_high_confidence() is True
        assert task.is_high_confidence(0.95) is False
        
        # Low confidence
        task = Task(
            page_number=1, task_number="1", task_text="Test",
            confidence_score=0.5
        )
        assert task.is_high_confidence() is False
        
        # No confidence score
        task = Task(page_number=1, task_number="1", task_text="Test")
        assert task.is_high_confidence() is False
    
    def test_task_metadata_methods(self):
        """Test metadata manipulation methods."""
        task = Task(page_number=1, task_number="1", task_text="Test")
        
        # Add metadata
        task.add_metadata("key1", "value1")
        assert task.get_metadata("key1") == "value1"
        
        # Get non-existent metadata
        assert task.get_metadata("nonexistent") is None
        assert task.get_metadata("nonexistent", "default") == "default"
    
    def test_task_sorting(self):
        """Test task sorting."""
        task1 = Task(page_number=1, task_number="1", task_text="First")
        task2 = Task(page_number=1, task_number="2", task_text="Second")
        task3 = Task(page_number=2, task_number="1", task_text="Third")
        
        tasks = [task3, task2, task1]
        sorted_tasks = sorted(tasks)
        
        assert sorted_tasks[0] == task1  # Page 1, Task 1
        assert sorted_tasks[1] == task2  # Page 1, Task 2
        assert sorted_tasks[2] == task3  # Page 2, Task 1
    
    def test_task_string_representation(self):
        """Test string representation."""
        task = Task(
            page_number=1, task_number="1", task_text="Test task",
            confidence_score=0.85
        )
        
        str_repr = str(task)
        assert "Task 1" in str_repr
        assert "(page 1)" in str_repr
        assert "(conf: 0.85)" in str_repr
        assert "Test task" in str_repr


class TestPage:
    """Tests for Page model."""
    
    def test_page_creation_minimal(self):
        """Test creating page with minimal required fields."""
        page = Page(page_number=1)
        
        assert page.page_number == 1
        assert len(page.tasks) == 0
        assert page.image_path is None
        assert page.processing_status == ProcessingStatus.PENDING
        assert len(page.errors) == 0
        assert len(page.warnings) == 0
        assert isinstance(page.metadata, dict)
        assert isinstance(page.created_at, datetime)
    
    def test_page_creation_full(self):
        """Test creating page with all fields."""
        tasks = [
            Task(page_number=1, task_number="1", task_text="Task 1"),
            Task(page_number=1, task_number="2", task_text="Task 2")
        ]
        
        page = Page(
            page_number=1,
            tasks=tasks,
            image_path="test.png",
            processing_status=ProcessingStatus.COMPLETED,
            processing_time=30.5
        )
        
        assert page.page_number == 1
        assert len(page.tasks) == 2
        assert page.image_path == "test.png"
        assert page.processing_status == ProcessingStatus.COMPLETED
        assert page.processing_time == 30.5
    
    def test_page_validation_page_number(self):
        """Test page number validation."""
        # Valid page number
        page = Page(page_number=1)
        assert page.page_number == 1
        
        # Invalid page numbers
        with pytest.raises(ValueError):
            Page(page_number=0)
        
        with pytest.raises(ValueError):
            Page(page_number=-1)
    
    def test_page_validation_processing_status(self):
        """Test processing status validation."""
        # Valid statuses
        valid_statuses = [
            ProcessingStatus.PENDING,
            ProcessingStatus.PROCESSING,
            ProcessingStatus.COMPLETED,
            ProcessingStatus.FAILED,
            ProcessingStatus.SKIPPED
        ]
        
        for status in valid_statuses:
            page = Page(page_number=1, processing_status=status)
            assert page.processing_status == status
        
        # Invalid status
        with pytest.raises(ValueError, match="Invalid processing status"):
            Page(page_number=1, processing_status="invalid_status")
    
    def test_page_task_page_number_correction(self):
        """Test automatic correction of task page numbers."""
        # Task with wrong page number
        task = Task(page_number=5, task_number="1", task_text="Test")
        page = Page(page_number=1, tasks=[task])
        
        # Should be corrected to match page number
        assert page.tasks[0].page_number == 1
    
    def test_page_add_task(self):
        """Test adding tasks to page."""
        page = Page(page_number=1)
        task = Task(page_number=2, task_number="1", task_text="Test")  # Wrong page number
        
        page.add_task(task)
        
        assert len(page.tasks) == 1
        assert page.tasks[0].page_number == 1  # Should be corrected
    
    def test_page_add_tasks(self):
        """Test adding multiple tasks."""
        page = Page(page_number=1)
        tasks = [
            Task(page_number=1, task_number="1", task_text="Task 1"),
            Task(page_number=1, task_number="2", task_text="Task 2")
        ]
        
        page.add_tasks(tasks)
        assert len(page.tasks) == 2
    
    def test_page_remove_task(self):
        """Test removing tasks."""
        page = Page(page_number=1)
        task1 = Task(page_number=1, task_number="1", task_text="Task 1")
        task2 = Task(page_number=1, task_number="2", task_text="Task 2")
        
        page.add_tasks([task1, task2])
        
        # Remove existing task
        result = page.remove_task("1")
        assert result is True
        assert len(page.tasks) == 1
        assert page.tasks[0].task_number == "2"
        
        # Try to remove non-existent task
        result = page.remove_task("999")
        assert result is False
        assert len(page.tasks) == 1
    
    def test_page_get_task(self):
        """Test getting task by number."""
        page = Page(page_number=1)
        task = Task(page_number=1, task_number="1", task_text="Test")
        page.add_task(task)
        
        # Get existing task
        found_task = page.get_task("1")
        assert found_task is not None
        assert found_task.task_number == "1"
        
        # Get non-existent task
        found_task = page.get_task("999")
        assert found_task is None
    
    def test_page_filtering_methods(self):
        """Test task filtering methods."""
        page = Page(page_number=1)
        
        tasks = [
            Task(page_number=1, task_number="1", task_text="Task 1", has_image=True, confidence_score=0.9),
            Task(page_number=1, task_number="unknown-1", task_text="Task 2", has_image=False, confidence_score=0.5),
            Task(page_number=1, task_number="3", task_text="Task 3", has_image=True, confidence_score=0.95)
        ]
        
        page.add_tasks(tasks)
        
        # Tasks with images
        image_tasks = page.get_tasks_with_images()
        assert len(image_tasks) == 2
        
        # Unknown tasks
        unknown_tasks = page.get_unknown_tasks()
        assert len(unknown_tasks) == 1
        assert unknown_tasks[0].task_number == "unknown-1"
        
        # High confidence tasks
        high_conf_tasks = page.get_high_confidence_tasks(0.8)
        assert len(high_conf_tasks) == 2
    
    def test_page_error_warning_handling(self):
        """Test error and warning handling."""
        page = Page(page_number=1)
        
        # Add error
        page.add_error("Test error")
        assert page.has_errors() is True
        assert len(page.errors) == 1
        assert "Test error" in page.errors[0]
        
        # Add warning
        page.add_warning("Test warning")
        assert page.has_warnings() is True
        assert len(page.warnings) == 1
        assert "Test warning" in page.warnings[0]
    
    def test_page_processing_status_methods(self):
        """Test processing status methods."""
        page = Page(page_number=1)
        
        # Initial status
        assert page.is_processed() is False
        
        # Set to completed
        page.set_processing_status(ProcessingStatus.COMPLETED)
        assert page.processing_status == ProcessingStatus.COMPLETED
        assert page.is_processed() is True
        assert page.processed_at is not None
    
    def test_page_statistics_methods(self):
        """Test page statistics methods."""
        page = Page(page_number=1)
        
        tasks = [
            Task(page_number=1, task_number="1", task_text="One two", confidence_score=0.8),
            Task(page_number=1, task_number="2", task_text="Three four five", confidence_score=0.9)
        ]
        
        page.add_tasks(tasks)
        
        # Word count
        assert page.get_total_word_count() == 5  # "One two" + "Three four five"
        
        # Average confidence
        avg_conf = page.get_average_confidence()
        assert avg_conf == 0.85  # (0.8 + 0.9) / 2
    
    def test_page_sort_tasks(self):
        """Test task sorting."""
        page = Page(page_number=1)
        
        tasks = [
            Task(page_number=1, task_number="3", task_text="Third", confidence_score=0.7),
            Task(page_number=1, task_number="1", task_text="First", confidence_score=0.9),
            Task(page_number=1, task_number="2", task_text="Second", confidence_score=0.8)
        ]
        
        page.add_tasks(tasks)
        
        # Sort by number
        page.sort_tasks(by_number=True)
        assert page.tasks[0].task_number == "1"
        assert page.tasks[1].task_number == "2"
        assert page.tasks[2].task_number == "3"
        
        # Sort by confidence
        page.sort_tasks(by_number=False)
        assert page.tasks[0].confidence_score == 0.9  # Highest first
        assert page.tasks[1].confidence_score == 0.8
        assert page.tasks[2].confidence_score == 0.7
    
    def test_page_serialization(self):
        """Test page serialization methods."""
        page = Page(page_number=1, processing_time=30.5)
        task = Task(page_number=1, task_number="1", task_text="Test")
        page.add_task(task)
        
        # To dict
        page_dict = page.to_dict(include_tasks=True)
        assert "tasks" in page_dict
        assert len(page_dict["tasks"]) == 1
        
        page_dict = page.to_dict(include_tasks=False)
        assert "tasks" not in page_dict
        
        # To JSON
        json_str = page.to_json(include_tasks=True)
        assert "tasks" in json_str
        assert "Test" in json_str
        
        # Summary
        summary = page.get_summary()
        assert summary["page_number"] == 1
        assert summary["task_count"] == 1
        assert summary["processing_time"] == 30.5
    
    def test_page_iteration(self):
        """Test page iteration methods."""
        page = Page(page_number=1)
        tasks = [
            Task(page_number=1, task_number="1", task_text="Task 1"),
            Task(page_number=1, task_number="2", task_text="Task 2")
        ]
        page.add_tasks(tasks)
        
        # Length
        assert len(page) == 2
        
        # Indexing
        assert page[0].task_number == "1"
        assert page[1].task_number == "2"
        
        # Iteration
        task_numbers = [task.task_number for task in page]
        assert task_numbers == ["1", "2"]
    
    def test_page_string_representation(self):
        """Test page string representation."""
        page = Page(page_number=1, processing_status=ProcessingStatus.COMPLETED)
        task = Task(page_number=1, task_number="1", task_text="Test")
        page.add_task(task)
        
        str_repr = str(page)
        assert "✅" in str_repr  # Completed emoji
        assert "Page 1" in str_repr
        assert "1 tasks" in str_repr


class TestProcessingStatus:
    """Tests for ProcessingStatus constants."""
    
    def test_processing_status_constants(self):
        """Test that all status constants are defined."""
        assert ProcessingStatus.PENDING == "pending"
        assert ProcessingStatus.PROCESSING == "processing"
        assert ProcessingStatus.COMPLETED == "completed"
        assert ProcessingStatus.FAILED == "failed"
        assert ProcessingStatus.SKIPPED == "skipped" 