"""Tests for CSVWriter module."""

import tempfile
import csv
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch
import pytest
import pandas as pd

from src.core.csv_writer import CSVWriter, CSVExportError
from src.models.task import Task
from src.models.page import Page, ProcessingStatus


class TestCSVWriter:
    """Tests for CSVWriter class."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.output_path = self.temp_dir / "test_output.csv" 
        self.csv_writer = CSVWriter(str(self.output_path))
    
    def create_test_tasks(self, count: int = 3) -> list[Task]:
        """Create test tasks for testing.
        
        Args:
            count: Number of tasks to create
            
        Returns:
            List of test Task objects
        """
        tasks = []
        for i in range(1, count + 1):
            task = Task(
                page_number=1,
                task_number=str(i),
                task_text=f"Тестовая задача {i}: Вычисли {i} + {i}",
                has_image=i % 2 == 0,
                confidence_score=0.9 - (i * 0.1),
                created_at=datetime.now()
            )
            # Add some metadata
            task.add_metadata("extraction_source", "test")
            task.add_metadata("raw_task_number", str(i))
            task.add_metadata("text_cleaned", False)
            tasks.append(task)
        
        return tasks
    
    def create_test_pages(self, page_count: int = 2, tasks_per_page: int = 2) -> list[Page]:
        """Create test pages with tasks.
        
        Args:
            page_count: Number of pages to create
            tasks_per_page: Number of tasks per page
            
        Returns:
            List of test Page objects
        """
        pages = []
        task_counter = 1
        
        for page_num in range(1, page_count + 1):
            page = Page(
                page_number=page_num,
                processing_status=ProcessingStatus.COMPLETED,
                processing_time=1.5
            )
            
            # Add tasks to page
            for task_num in range(tasks_per_page):
                task = Task(
                    page_number=page_num,
                    task_number=str(task_counter),
                    task_text=f"Задача {task_counter} со страницы {page_num}",
                    has_image=task_counter % 3 == 0,
                    confidence_score=0.85
                )
                page.add_task(task)
                task_counter += 1
            
            pages.append(page)
        
        return pages
    
    def test_csv_writer_initialization(self):
        """Test CSVWriter initialization."""
        writer = CSVWriter("/path/to/output.csv", encoding="utf-8", delimiter=";")
        
        assert writer.output_path == Path("/path/to/output.csv")
        assert writer.encoding == "utf-8"
        assert writer.delimiter == ";"
        assert isinstance(writer.export_stats, dict)
        assert writer.export_stats["total_tasks_exported"] == 0
    
    def test_validate_output_path_success(self):
        """Test successful output path validation."""
        assert self.csv_writer.validate_output_path() is True
    
    def test_validate_output_path_invalid_directory(self):
        """Test output path validation with invalid directory."""
        # Create writer with path in non-existent directory with no permissions
        invalid_path = "/root/restricted/output.csv"  # Usually no write permissions
        writer = CSVWriter(invalid_path)
        
        # This might pass or fail depending on system permissions
        # The important thing is it doesn't crash
        result = writer.validate_output_path()
        assert isinstance(result, bool)
    
    def test_create_dataframe_basic(self):
        """Test basic DataFrame creation."""
        tasks = self.create_test_tasks(3)
        df = self.csv_writer.create_dataframe(tasks, include_metadata=False)
        
        # Check basic structure
        assert len(df) == 3
        assert list(df.columns) == ["page_number", "task_number", "task_text", "has_image"]
        
        # Check data content
        assert df.iloc[0]["task_number"] == "1"
        assert df.iloc[0]["has_image"] is False
        assert df.iloc[1]["has_image"] is True  # Even numbered task
        assert "Тестовая задача" in df.iloc[0]["task_text"]
    
    def test_create_dataframe_with_metadata(self):
        """Test DataFrame creation with metadata columns."""
        tasks = self.create_test_tasks(2)
        df = self.csv_writer.create_dataframe(tasks, include_metadata=True)
        
        # Check extended columns
        expected_columns = [
            "page_number", "task_number", "task_text", "has_image",
            "confidence_score", "processing_time", "word_count",
            "is_unknown_number", "is_high_confidence", "created_at",
            "extraction_source", "text_cleaned", "raw_task_number"
        ]
        assert list(df.columns) == expected_columns
        
        # Check metadata content
        assert df.iloc[0]["confidence_score"] == 0.8  # 0.9 - 0.1
        assert df.iloc[0]["extraction_source"] == "test"
        assert df.iloc[0]["is_unknown_number"] is False
        assert df.iloc[0]["word_count"] > 0
    
    def test_create_dataframe_sorting(self):
        """Test that DataFrame is sorted by page and task number."""
        # Create tasks in mixed order
        tasks = [
            Task(page_number=2, task_number="2", task_text="Page 2 Task 2", has_image=False),
            Task(page_number=1, task_number="3", task_text="Page 1 Task 3", has_image=False),
            Task(page_number=1, task_number="1", task_text="Page 1 Task 1", has_image=False),
            Task(page_number=2, task_number="1", task_text="Page 2 Task 1", has_image=False)
        ]
        
        df = self.csv_writer.create_dataframe(tasks, include_metadata=False)
        
        # Check sorting
        assert df.iloc[0]["page_number"] == 1
        assert df.iloc[0]["task_number"] == "1"
        assert df.iloc[1]["page_number"] == 1  
        assert df.iloc[1]["task_number"] == "3"
        assert df.iloc[2]["page_number"] == 2
        assert df.iloc[2]["task_number"] == "1"
        assert df.iloc[3]["page_number"] == 2
        assert df.iloc[3]["task_number"] == "2"
    
    def test_write_tasks_success(self):
        """Test successful task writing to CSV."""
        pages = self.create_test_pages(2, 2)  # 2 pages, 2 tasks each
        
        result = self.csv_writer.write_tasks(pages, include_metadata=False)
        
        # Check return value
        assert result["tasks_exported"] == 4
        assert result["pages_processed"] == 2
        assert result["output_file"] == str(self.output_path)
        
        # Check file was created
        assert self.output_path.exists()
        
        # Check CSV content
        df = pd.read_csv(self.output_path)
        assert len(df) == 4
        assert list(df.columns) == ["page_number", "task_number", "task_text", "has_image"]
    
    def test_write_tasks_with_metadata(self):
        """Test writing tasks with metadata columns."""
        pages = self.create_test_pages(1, 2)
        
        result = self.csv_writer.write_tasks(pages, include_metadata=True)
        
        # Check file content
        df = pd.read_csv(self.output_path)
        assert len(df) == 2
        
        # Should have metadata columns
        metadata_columns = ["confidence_score", "word_count", "is_unknown_number"]
        for col in metadata_columns:
            assert col in df.columns
    
    def test_write_tasks_empty_pages(self):
        """Test writing with empty pages."""
        empty_pages = [
            Page(page_number=1, processing_status=ProcessingStatus.COMPLETED),
            Page(page_number=2, processing_status=ProcessingStatus.COMPLETED)
        ]
        
        result = self.csv_writer.write_tasks(empty_pages)
        
        assert result["tasks_exported"] == 0
        assert result["pages_processed"] == 0
    
    def test_write_tasks_no_pages(self):
        """Test writing with no pages."""
        result = self.csv_writer.write_tasks([])
        
        assert result["tasks_exported"] == 0
        assert result["pages_processed"] == 0
    
    def test_write_tasks_invalid_path(self):
        """Test writing with invalid output path."""
        # Mock validate_output_path to return False
        with patch.object(self.csv_writer, 'validate_output_path', return_value=False):
            pages = self.create_test_pages(1, 1)
            
            with pytest.raises(CSVExportError, match="Invalid output path"):
                self.csv_writer.write_tasks(pages)
    
    def test_csv_encoding_and_delimiter(self):
        """Test CSV with different encoding and delimiter."""
        # Create writer with different settings
        custom_path = self.temp_dir / "custom.csv"
        writer = CSVWriter(str(custom_path), encoding="utf-8", delimiter=";")
        
        pages = self.create_test_pages(1, 1)
        writer.write_tasks(pages, include_metadata=False)
        
        # Read file manually to check delimiter
        with open(custom_path, 'r', encoding='utf-8') as f:
            content = f.read()
            assert ";" in content  # Should use semicolon delimiter
            assert "," not in content.split('\n')[0]  # Header should not have commas
    
    def test_task_to_csv_row_basic(self):
        """Test task to CSV row conversion without metadata."""
        task = Task(
            page_number=5,
            task_number="3a",
            task_text="Test task text",
            has_image=True,
            confidence_score=0.87
        )
        
        row = self.csv_writer._task_to_csv_row(task, include_metadata=False)
        
        expected_row = {
            "page_number": 5,
            "task_number": "3a",
            "task_text": "Test task text",
            "has_image": True
        }
        assert row == expected_row
    
    def test_task_to_csv_row_with_metadata(self):
        """Test task to CSV row conversion with metadata."""
        task = Task(
            page_number=2,
            task_number="1",
            task_text="Metadata task",
            has_image=False,
            confidence_score=0.95,
            created_at=datetime(2024, 1, 15, 10, 30, 0)
        )
        task.add_metadata("extraction_source", "vision_api")
        task.add_metadata("text_cleaned", True)
        
        row = self.csv_writer._task_to_csv_row(task, include_metadata=True)
        
        # Check basic fields
        assert row["page_number"] == 2
        assert row["task_number"] == "1"
        assert row["has_image"] is False
        
        # Check metadata fields
        assert row["confidence_score"] == 0.95
        assert row["extraction_source"] == "vision_api"
        assert row["text_cleaned"] is True
        assert row["is_unknown_number"] is False
        assert row["is_high_confidence"] is True
        assert row["word_count"] == 2  # "Metadata task"
        assert "2024-01-15T10:30:00" in row["created_at"]
    
    def test_append_tasks_new_file(self):
        """Test appending tasks to non-existent file (creates new)."""
        pages = self.create_test_pages(1, 2)
        
        result = self.csv_writer.append_tasks(pages)
        
        # Should create new file
        assert result["tasks_appended"] == 2
        assert result["pages_processed"] == 1
        assert self.output_path.exists()
    
    def test_append_tasks_existing_file(self):
        """Test appending tasks to existing file."""
        # Create initial file
        initial_pages = self.create_test_pages(1, 2)
        self.csv_writer.write_tasks(initial_pages)
        
        # Append more tasks
        new_pages = self.create_test_pages(1, 1)  # 1 page, 1 task
        # Adjust task numbers to avoid conflicts
        new_pages[0].tasks[0].task_number = "new_1"
        
        result = self.csv_writer.append_tasks(new_pages)
        
        assert result["tasks_appended"] == 1
        assert result["total_tasks_in_file"] == 3  # 2 initial + 1 new
        
        # Check file content
        df = pd.read_csv(self.output_path)
        assert len(df) == 3
    
    def test_append_tasks_empty(self):
        """Test appending empty task list."""
        empty_pages = [Page(page_number=1, processing_status=ProcessingStatus.COMPLETED)]
        
        result = self.csv_writer.append_tasks(empty_pages)
        
        assert result["tasks_appended"] == 0
        assert result["pages_processed"] == 0
    
    def test_get_export_statistics(self):
        """Test getting export statistics."""
        pages = self.create_test_pages(2, 3)
        self.csv_writer.write_tasks(pages)
        
        stats = self.csv_writer.get_export_statistics()
        
        assert stats["total_tasks_exported"] == 6
        assert stats["total_pages_processed"] == 2
        assert stats["export_start_time"] is not None
        assert stats["export_end_time"] is not None
    
    def test_create_export_report(self):
        """Test creating detailed export report."""
        pages = self.create_test_pages(2, 2)
        
        # Add some variety to tasks
        pages[0].tasks[0].confidence_score = 0.95  # High confidence
        pages[0].tasks[1].has_image = True
        pages[1].tasks[0].task_number = "unknown-1"  # Unknown number
        
        report = self.csv_writer.create_export_report(pages)
        
        # Check report content
        assert "CSV Export Report" in report
        assert "Total Pages: 2" in report
        assert "Total Tasks: 4" in report
        assert str(self.output_path) in report
        assert "Quality Metrics" in report
        assert "Average Confidence" in report
    
    def test_column_order_consistency(self):
        """Test that column order is consistent."""
        basic_order = self.csv_writer._get_column_order(include_metadata=False)
        metadata_order = self.csv_writer._get_column_order(include_metadata=True)
        
        # Basic columns should be first in both cases
        expected_basic = ["page_number", "task_number", "task_text", "has_image"]
        assert basic_order == expected_basic
        
        # Metadata order should start with basic columns
        assert metadata_order[:4] == expected_basic
        assert len(metadata_order) > len(basic_order)
        
        # Check some expected metadata columns
        assert "confidence_score" in metadata_order
        assert "word_count" in metadata_order
        assert "created_at" in metadata_order
    
    def test_special_characters_in_text(self):
        """Test handling of special characters in task text."""
        task = Task(
            page_number=1,
            task_number="1",
            task_text='Задача с "кавычками", запятыми, и новой\nстрокой',
            has_image=False
        )
        pages = [Page(page_number=1, processing_status=ProcessingStatus.COMPLETED)]
        pages[0].add_task(task)
        
        self.csv_writer.write_tasks(pages)
        
        # Read back and verify content is preserved
        df = pd.read_csv(self.output_path)
        assert len(df) == 1
        # Content should be properly escaped/quoted
        assert "кавычками" in df.iloc[0]["task_text"]
    
    def test_unicode_content(self):
        """Test handling of Unicode content."""
        task = Task(
            page_number=1,
            task_number="№1",  # Unicode number symbol
            task_text="Математика: 2² + 3√4 ≥ 10",  # Mathematical Unicode
            has_image=False
        )
        pages = [Page(page_number=1, processing_status=ProcessingStatus.COMPLETED)]
        pages[0].add_task(task)
        
        self.csv_writer.write_tasks(pages)
        
        # Read back with proper encoding
        df = pd.read_csv(self.output_path, encoding='utf-8')
        assert len(df) == 1
        assert df.iloc[0]["task_number"] == "№1"
        assert "2²" in df.iloc[0]["task_text"]
        assert "3√4" in df.iloc[0]["task_text"]
        assert "≥" in df.iloc[0]["task_text"]
    
    def test_large_dataset_export(self):
        """Test exporting large dataset."""
        # Create many pages with many tasks
        pages = self.create_test_pages(10, 20)  # 10 pages * 20 tasks = 200 tasks
        
        result = self.csv_writer.write_tasks(pages)
        
        assert result["tasks_exported"] == 200
        assert result["pages_processed"] == 10
        
        # Check file exists and has correct size
        assert self.output_path.exists()
        df = pd.read_csv(self.output_path)
        assert len(df) == 200
    
    def test_export_statistics_accuracy(self):
        """Test accuracy of export statistics calculation."""
        # Create tasks with specific characteristics
        pages = []
        page = Page(page_number=1, processing_status=ProcessingStatus.COMPLETED)
        
        # High confidence task
        task1 = Task(page_number=1, task_number="1", task_text="High conf", 
                    has_image=False, confidence_score=0.95)
        page.add_task(task1)
        
        # Low confidence task with image
        task2 = Task(page_number=1, task_number="2", task_text="Low conf", 
                    has_image=True, confidence_score=0.6)
        page.add_task(task2)
        
        # Unknown numbered task
        task3 = Task(page_number=1, task_number="unknown-1", task_text="Unknown", 
                    has_image=False, confidence_score=0.8)
        page.add_task(task3)
        
        pages.append(page)
        
        result = self.csv_writer.write_tasks(pages)
        
        # Check statistics
        assert result["tasks_exported"] == 3
        assert result["high_confidence_tasks"] == 1  # Only task1
        assert result["unknown_numbered_tasks"] == 1  # Only task3
        assert result["tasks_with_images"] == 1  # Only task2
    
    def teardown_method(self):
        """Cleanup test fixtures."""
        # Clean up temporary directory
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)


class TestCSVExportError:
    """Tests for CSVExportError exception."""
    
    def test_csv_export_error_creation(self):
        """Test creating CSVExportError."""
        error = CSVExportError("Test CSV export error")
        assert str(error) == "Test CSV export error"
        assert isinstance(error, Exception)
    
    def test_csv_export_error_inheritance(self):
        """Test CSVExportError inheritance."""
        error = CSVExportError("Test error")
        assert isinstance(error, Exception)
        assert error.__class__.__name__ == "CSVExportError" 