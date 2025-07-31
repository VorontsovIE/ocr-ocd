"""Tests for StateManager module."""

import json
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch
import pytest

from src.utils.state_manager import StateManager, ProcessingState


class TestProcessingState:
    """Tests for ProcessingState model."""
    
    def test_processing_state_creation(self):
        """Test ProcessingState model creation."""
        state = ProcessingState(
            session_id="test_session",
            input_pdf_path="/path/to/input.pdf",
            output_csv_path="/path/to/output.csv",
            total_pages=10,
            session_start_time=datetime.now().isoformat(),
            last_update_time=datetime.now().isoformat()
        )
        
        assert state.session_id == "test_session"
        assert state.input_pdf_path == "/path/to/input.pdf"
        assert state.output_csv_path == "/path/to/output.csv"
        assert state.total_pages == 10
        assert state.current_page == 0  # Default
        assert state.next_page == 0  # Default
        assert state.completed_pages == []  # Default
        assert state.failed_pages == []  # Default
        assert state.processing_errors == {}  # Default
    
    def test_processing_state_validation(self):
        """Test ProcessingState validation."""
        # Missing required fields should raise ValidationError
        with pytest.raises(Exception):  # Pydantic ValidationError
            ProcessingState()
        
        # Invalid total_pages should raise ValidationError
        with pytest.raises(Exception):  # Pydantic ValidationError
            ProcessingState(
                session_id="test",
                input_pdf_path="/path/to/input.pdf",
                output_csv_path="/path/to/output.csv",
                total_pages=-1,  # Invalid negative
                session_start_time=datetime.now().isoformat(),
                last_update_time=datetime.now().isoformat()
            )


class TestStateManager:
    """Tests for StateManager class."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.state_file = self.temp_dir / "test_state.json"
        self.state_manager = StateManager(str(self.state_file))
    
    def test_state_manager_initialization(self):
        """Test StateManager initialization."""
        assert self.state_manager.state_file_path == self.state_file
        assert self.state_manager.current_state is None
        assert self.state_manager.session_id.startswith("session_")
        assert len(self.state_manager.session_id) > 10  # Should be reasonably unique
    
    def test_generate_session_id(self):
        """Test session ID generation."""
        id1 = self.state_manager._generate_session_id()
        id2 = self.state_manager._generate_session_id()
        
        assert id1 != id2  # Should be unique
        assert id1.startswith("session_")
        assert id2.startswith("session_")
    
    def test_initialize_state(self):
        """Test state initialization."""
        state = self.state_manager.initialize_state(
            input_pdf_path="/test/input.pdf",
            output_csv_path="/test/output.csv",
            total_pages=5,
            config_hash="test_hash"
        )
        
        assert isinstance(state, ProcessingState)
        assert state.input_pdf_path == "/test/input.pdf"
        assert state.output_csv_path == "/test/output.csv"
        assert state.total_pages == 5
        assert state.configuration_hash == "test_hash"
        assert state.session_id == self.state_manager.session_id
        
        # Should be stored in state_manager
        assert self.state_manager.current_state == state
    
    def test_save_and_load_state(self):
        """Test saving and loading state."""
        # Initialize state
        original_state = self.state_manager.initialize_state(
            input_pdf_path="/test/input.pdf",
            output_csv_path="/test/output.csv",
            total_pages=3
        )
        
        # Save state
        result = self.state_manager.save_state()
        assert result is True
        assert self.state_file.exists()
        
        # Create new state manager and load
        new_manager = StateManager(str(self.state_file))
        loaded_data = new_manager.load_state()
        
        assert loaded_data["session_id"] == original_state.session_id
        assert loaded_data["input_pdf_path"] == "/test/input.pdf"
        assert loaded_data["total_pages"] == 3
        assert new_manager.current_state.session_id == original_state.session_id
    
    def test_load_state_file_not_found(self):
        """Test loading state when file doesn't exist."""
        non_existent_file = self.temp_dir / "non_existent.json"
        manager = StateManager(str(non_existent_file))
        
        with pytest.raises(FileNotFoundError):
            manager.load_state()
    
    def test_load_state_corrupted_file(self):
        """Test loading state with corrupted JSON file."""
        # Write invalid JSON
        self.state_file.write_text("invalid json content")
        
        with pytest.raises(ValueError, match="State file is corrupted"):
            self.state_manager.load_state()
    
    def test_update_progress(self):
        """Test progress updates."""
        # Initialize state
        self.state_manager.initialize_state("/test/input.pdf", "/test/output.csv", 5)
        
        # Update progress for page 1 (1-indexed)
        self.state_manager.update_progress(1)
        
        state = self.state_manager.current_state
        assert state.current_page == 0  # 0-indexed internally
        assert state.next_page == 1  # Next page to process
        assert 0 in state.completed_pages
        
        # Update progress for page 3
        self.state_manager.update_progress(3)
        
        assert state.current_page == 2
        assert state.next_page == 3
        assert 2 in state.completed_pages
        assert len(state.completed_pages) == 2  # Pages 0 and 2
    
    def test_add_error(self):
        """Test adding errors for pages."""
        self.state_manager.initialize_state("/test/input.pdf", "/test/output.csv", 5)
        
        # Add error for page 2
        self.state_manager.add_error(2, "Test error message")
        
        state = self.state_manager.current_state
        assert 1 in state.failed_pages  # 0-indexed internally
        assert state.processing_errors[1] == "Test error message"
        
        # If page was in completed_pages, it should be removed
        state.completed_pages.append(1)  # Manually add for test
        self.state_manager.add_error(2, "Another error")
        
        assert 1 not in state.completed_pages
        assert 1 in state.failed_pages
    
    def test_add_warning(self):
        """Test adding warnings for pages."""
        self.state_manager.initialize_state("/test/input.pdf", "/test/output.csv", 5)
        
        # Add warnings for page 1
        self.state_manager.add_warning(1, "First warning")
        self.state_manager.add_warning(1, "Second warning")
        
        state = self.state_manager.current_state
        assert 0 in state.processing_warnings  # 0-indexed internally
        assert len(state.processing_warnings[0]) == 2
        assert "First warning" in state.processing_warnings[0]
        assert "Second warning" in state.processing_warnings[0]
    
    def test_update_statistics(self):
        """Test updating processing statistics."""
        self.state_manager.initialize_state("/test/input.pdf", "/test/output.csv", 5)
        
        # Update statistics
        stats = {
            "total_tasks_extracted": 25,
            "api_calls_made": 5,
            "api_errors": 1,
            "custom_metric": "test_value"
        }
        
        self.state_manager.update_statistics(stats)
        
        state = self.state_manager.current_state
        assert state.total_tasks_extracted == 25
        assert state.api_calls_made == 5
        assert state.api_errors == 1
        assert state.processing_statistics["custom_metric"] == "test_value"
    
    def test_can_resume_no_file(self):
        """Test can_resume when no state file exists."""
        assert self.state_manager.can_resume() is False
    
    def test_can_resume_with_remaining_pages(self):
        """Test can_resume with remaining pages."""
        # Create state with some completed pages
        self.state_manager.initialize_state("/test/input.pdf", "/test/output.csv", 5)
        self.state_manager.update_progress(1)
        self.state_manager.update_progress(2)
        self.state_manager.save_state()
        
        # Create new manager for same file
        new_manager = StateManager(str(self.state_file))
        assert new_manager.can_resume() is True
    
    def test_can_resume_all_completed(self):
        """Test can_resume when all pages are completed."""
        # Create state with all pages completed
        self.state_manager.initialize_state("/test/input.pdf", "/test/output.csv", 2)
        self.state_manager.update_progress(1)
        self.state_manager.update_progress(2)
        self.state_manager.save_state()
        
        # Create new manager for same file
        new_manager = StateManager(str(self.state_file))
        assert new_manager.can_resume() is False  # All pages done
    
    def test_get_next_page(self):
        """Test getting next page to process."""
        self.state_manager.initialize_state("/test/input.pdf", "/test/output.csv", 3)
        
        # Initially should return page 1 (1-indexed)
        assert self.state_manager.get_next_page() == 1
        
        # After processing page 1
        self.state_manager.update_progress(1)
        assert self.state_manager.get_next_page() == 2
        
        # After processing page 2
        self.state_manager.update_progress(2)
        assert self.state_manager.get_next_page() == 3
        
        # After processing all pages
        self.state_manager.update_progress(3)
        assert self.state_manager.get_next_page() is None
    
    def test_get_completion_percentage(self):
        """Test completion percentage calculation."""
        self.state_manager.initialize_state("/test/input.pdf", "/test/output.csv", 4)
        
        # Initially 0%
        assert self.state_manager.get_completion_percentage() == 0.0
        
        # After 1 page: 25%
        self.state_manager.update_progress(1)
        assert self.state_manager.get_completion_percentage() == 25.0
        
        # After 2 pages: 50%
        self.state_manager.update_progress(2)
        assert self.state_manager.get_completion_percentage() == 50.0
        
        # After all pages: 100%
        self.state_manager.update_progress(3)
        self.state_manager.update_progress(4)
        assert self.state_manager.get_completion_percentage() == 100.0
    
    def test_get_processing_summary(self):
        """Test getting processing summary."""
        self.state_manager.initialize_state("/test/input.pdf", "/test/output.csv", 5)
        self.state_manager.update_progress(1)
        self.state_manager.update_progress(2)
        self.state_manager.add_error(3, "Test error")
        self.state_manager.update_statistics({"total_tasks_extracted": 10})
        
        summary = self.state_manager.get_processing_summary()
        
        assert summary["total_pages"] == 5
        assert summary["completed_pages"] == 2
        assert summary["failed_pages"] == 1
        assert summary["remaining_pages"] == 2
        assert summary["completion_percentage"] == 40.0  # 2/5 * 100
        assert summary["total_tasks_extracted"] == 10
        assert summary["next_page"] == 3  # Next unprocessed page
    
    def test_cleanup_state(self):
        """Test state cleanup."""
        # Create and save state
        self.state_manager.initialize_state("/test/input.pdf", "/test/output.csv", 2)
        self.state_manager.save_state()
        
        assert self.state_file.exists()
        
        # Cleanup
        result = self.state_manager.cleanup_state()
        assert result is True
        assert not self.state_file.exists()
        
        # Should create backup file
        backup_file = self.state_file.with_suffix('.completed')
        assert backup_file.exists()
    
    def test_validate_configuration(self):
        """Test configuration validation."""
        # No current state - should return True
        assert self.state_manager.validate_configuration("any_hash") is True
        
        # Initialize state with hash
        self.state_manager.initialize_state(
            "/test/input.pdf", "/test/output.csv", 2,
            config_hash="original_hash"
        )
        
        # Same hash - should return True
        assert self.state_manager.validate_configuration("original_hash") is True
        
        # Different hash - should return False
        assert self.state_manager.validate_configuration("different_hash") is False
        
        # No hash in state - should return True (allow resumption)
        self.state_manager.current_state.configuration_hash = None
        assert self.state_manager.validate_configuration("any_hash") is True
    
    def test_get_failed_pages_report(self):
        """Test getting failed pages report."""
        self.state_manager.initialize_state("/test/input.pdf", "/test/output.csv", 5)
        
        # No failures initially
        assert self.state_manager.get_failed_pages_report() == {}
        
        # Add some failures
        self.state_manager.add_error(2, "Error on page 2")
        self.state_manager.add_error(4, "Error on page 4")
        
        report = self.state_manager.get_failed_pages_report()
        
        # Should return 1-indexed page numbers
        assert report == {2: "Error on page 2", 4: "Error on page 4"}
    
    def test_export_state_report(self):
        """Test exporting detailed state report."""
        self.state_manager.initialize_state("/test/input.pdf", "/test/output.csv", 3)
        self.state_manager.update_progress(1)
        self.state_manager.add_error(2, "Test error")
        self.state_manager.add_warning(1, "Test warning")
        
        report = self.state_manager.export_state_report()
        
        # Check report content
        assert "Processing State Report" in report
        assert "Total Pages: 3" in report
        assert "Completed: 1" in report
        assert "Failed: 1" in report
        assert "Test error" in report
        assert "Test warning" in report
    
    def test_export_state_report_to_file(self):
        """Test exporting state report to file."""
        self.state_manager.initialize_state("/test/input.pdf", "/test/output.csv", 2)
        
        output_path = self.temp_dir / "state_report.txt"
        report_text = self.state_manager.export_state_report(str(output_path))
        
        # File should be created
        assert output_path.exists()
        
        # Content should match
        file_content = output_path.read_text(encoding='utf-8')
        assert file_content == report_text
        assert "Processing State Report" in file_content
    
    def test_save_state_no_current_state(self):
        """Test saving state when no current state exists."""
        # Don't initialize state
        result = self.state_manager.save_state()
        assert result is False
    
    def test_save_state_atomic_write(self):
        """Test that state saving uses atomic write (temporary file)."""
        self.state_manager.initialize_state("/test/input.pdf", "/test/output.csv", 2)
        
        # Mock file operations to test atomic write
        original_rename = Path.rename
        rename_called = []
        
        def mock_rename(self, target):
            rename_called.append((str(self), str(target)))
            return original_rename(self, target)
        
        with patch.object(Path, 'rename', mock_rename):
            result = self.state_manager.save_state()
        
        assert result is True
        assert len(rename_called) == 1
        
        # Should rename from .tmp to actual file
        src, dst = rename_called[0]
        assert src.endswith('.tmp')
        assert dst == str(self.state_file)
    
    def test_state_persistence_across_instances(self):
        """Test that state persists across StateManager instances."""
        # Create state with first instance
        self.state_manager.initialize_state("/test/input.pdf", "/test/output.csv", 3)
        self.state_manager.update_progress(1)
        self.state_manager.add_error(2, "Test error")
        self.state_manager.update_statistics({"total_tasks_extracted": 5})
        self.state_manager.save_state()
        
        # Create new instance and load state
        new_manager = StateManager(str(self.state_file))
        new_manager.load_state()
        
        # Verify state was preserved
        assert new_manager.current_state.total_pages == 3
        assert len(new_manager.current_state.completed_pages) == 1
        assert len(new_manager.current_state.failed_pages) == 1
        assert new_manager.current_state.total_tasks_extracted == 5
        assert new_manager.current_state.processing_errors[1] == "Test error"
    
    def teardown_method(self):
        """Cleanup test fixtures."""
        # Clean up temporary directory
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir) 