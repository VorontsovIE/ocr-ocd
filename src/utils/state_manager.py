"""State management for processing resumption."""

import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from src.utils.logger import get_logger

logger = get_logger(__name__)


class ProcessingState(BaseModel):
    """Model for processing state data."""
    
    session_id: str = Field(..., description="Unique session identifier")
    input_pdf_path: str = Field(..., description="Path to input PDF file")
    output_csv_path: str = Field(..., description="Path to output CSV file")
    total_pages: int = Field(..., description="Total number of pages in PDF")
    current_page: int = Field(default=0, description="Current page being processed (0-indexed)")
    next_page: int = Field(default=0, description="Next page to process (0-indexed)")
    completed_pages: List[int] = Field(default_factory=list, description="List of completed page numbers")
    failed_pages: List[int] = Field(default_factory=list, description="List of failed page numbers")
    processing_errors: Dict[int, str] = Field(default_factory=dict, description="Mapping of page numbers to error messages")
    processing_warnings: Dict[int, List[str]] = Field(default_factory=dict, description="Mapping of page numbers to warning messages")
    session_start_time: str = Field(..., description="Session start time (ISO format)")
    last_update_time: str = Field(..., description="Last update time (ISO format)")
    total_tasks_extracted: int = Field(default=0, description="Total tasks extracted so far")
    api_calls_made: int = Field(default=0, description="Total API calls made")
    api_errors: int = Field(default=0, description="Number of API errors encountered")
    processing_statistics: Dict[str, Any] = Field(default_factory=dict, description="Additional processing statistics")
    configuration_hash: Optional[str] = Field(None, description="Hash of configuration for validation")


class StateManager:
    """Manages processing state for resumption capabilities."""
    
    def __init__(self, state_file_path: str):
        """Initialize state manager.
        
        Args:
            state_file_path: Path to state file
        """
        self.state_file_path = Path(state_file_path)
        self.current_state: Optional[ProcessingState] = None
        self.session_id = self._generate_session_id()
        
        logger.info(f"StateManager initialized with state file: {self.state_file_path}")
    
    def _generate_session_id(self) -> str:
        """Generate unique session identifier.
        
        Returns:
            Session ID string
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"session_{timestamp}_{hash(time.time()) % 10000:04d}"
    
    def initialize_state(
        self, 
        input_pdf_path: str, 
        output_csv_path: str, 
        total_pages: int,
        config_hash: Optional[str] = None
    ) -> ProcessingState:
        """Initialize new processing state.
        
        Args:
            input_pdf_path: Path to input PDF
            output_csv_path: Path to output CSV
            total_pages: Total number of pages
            config_hash: Optional configuration hash
            
        Returns:
            Initialized ProcessingState
        """
        self.current_state = ProcessingState(
            session_id=self.session_id,
            input_pdf_path=input_pdf_path,
            output_csv_path=output_csv_path,
            total_pages=total_pages,
            session_start_time=datetime.now().isoformat(),
            last_update_time=datetime.now().isoformat(),
            configuration_hash=config_hash
        )
        
        logger.info(f"Initialized new processing state for {total_pages} pages")
        return self.current_state
    
    def load_state(self) -> Dict[str, Any]:
        """Load processing state from file.
        
        Returns:
            Dictionary with state data
            
        Raises:
            FileNotFoundError: If state file doesn't exist
            ValueError: If state file is corrupted
        """
        try:
            if not self.state_file_path.exists():
                raise FileNotFoundError(f"State file not found: {self.state_file_path}")
            
            with open(self.state_file_path, 'r', encoding='utf-8') as f:
                state_data = json.load(f)
            
            # Validate and parse state
            self.current_state = ProcessingState.model_validate(state_data)
            
            logger.info(
                f"Loaded processing state",
                session_id=self.current_state.session_id,
                next_page=self.current_state.next_page,
                total_pages=self.current_state.total_pages,
                completed_pages=len(self.current_state.completed_pages)
            )
            
            return self.current_state.model_dump()
            
        except json.JSONDecodeError as e:
            error_msg = f"State file is corrupted: {e}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to load state: {e}"
            logger.error(error_msg)
            raise
    
    def save_state(self) -> bool:
        """Save current processing state to file.
        
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            if not self.current_state:
                logger.warning("No current state to save")
                return False
            
            # Update last update time
            self.current_state.last_update_time = datetime.now().isoformat()
            
            # Ensure parent directory exists
            self.state_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write state to temporary file first (atomic write)
            temp_file = self.state_file_path.with_suffix('.tmp')
            
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(
                    self.current_state.model_dump(),
                    f,
                    indent=2,
                    ensure_ascii=False
                )
            
            # Rename temporary file to actual state file
            temp_file.rename(self.state_file_path)
            
            logger.debug(f"State saved successfully to {self.state_file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
            return False
    
    def update_progress(self, current_page: int, total_pages: Optional[int] = None) -> None:
        """Update processing progress.
        
        Args:
            current_page: Current page number (1-indexed)
            total_pages: Total pages (if different from initial)
        """
        if not self.current_state:
            logger.warning("No current state to update")
            return
        
        # Convert to 0-indexed for internal storage
        current_page_idx = current_page - 1
        
        self.current_state.current_page = current_page_idx
        self.current_state.next_page = current_page_idx + 1
        
        if total_pages and total_pages != self.current_state.total_pages:
            self.current_state.total_pages = total_pages
            logger.info(f"Updated total pages to {total_pages}")
        
        # Add to completed pages if not already there
        if current_page_idx not in self.current_state.completed_pages:
            self.current_state.completed_pages.append(current_page_idx)
        
        # Remove from failed pages if it was there
        if current_page_idx in self.current_state.failed_pages:
            self.current_state.failed_pages.remove(current_page_idx)
            if current_page_idx in self.current_state.processing_errors:
                del self.current_state.processing_errors[current_page_idx]
        
        progress_percent = (current_page / self.current_state.total_pages) * 100
        logger.debug(f"Progress updated: page {current_page}/{self.current_state.total_pages} ({progress_percent:.1f}%)")
    
    def add_error(self, page_number: int, error_message: str) -> None:
        """Add error for a specific page.
        
        Args:
            page_number: Page number (1-indexed)
            error_message: Error message
        """
        if not self.current_state:
            logger.warning("No current state to update")
            return
        
        # Convert to 0-indexed
        page_idx = page_number - 1
        
        # Add to failed pages
        if page_idx not in self.current_state.failed_pages:
            self.current_state.failed_pages.append(page_idx)
        
        # Store error message
        self.current_state.processing_errors[page_idx] = error_message
        
        # Remove from completed pages if it was there
        if page_idx in self.current_state.completed_pages:
            self.current_state.completed_pages.remove(page_idx)
        
        logger.warning(f"Added error for page {page_number}: {error_message}")
    
    def add_warning(self, page_number: int, warning_message: str) -> None:
        """Add warning for a specific page.
        
        Args:
            page_number: Page number (1-indexed)
            warning_message: Warning message
        """
        if not self.current_state:
            logger.warning("No current state to update")
            return
        
        # Convert to 0-indexed
        page_idx = page_number - 1
        
        if page_idx not in self.current_state.processing_warnings:
            self.current_state.processing_warnings[page_idx] = []
        
        self.current_state.processing_warnings[page_idx].append(warning_message)
        
        logger.debug(f"Added warning for page {page_number}: {warning_message}")
    
    def update_statistics(self, stats: Dict[str, Any]) -> None:
        """Update processing statistics.
        
        Args:
            stats: Statistics dictionary
        """
        if not self.current_state:
            logger.warning("No current state to update")
            return
        
        # Update specific fields if provided
        if "total_tasks_extracted" in stats:
            self.current_state.total_tasks_extracted = stats["total_tasks_extracted"]
        
        if "api_calls_made" in stats:
            self.current_state.api_calls_made = stats["api_calls_made"]
        
        if "api_errors" in stats:
            self.current_state.api_errors = stats["api_errors"]
        
        # Update general statistics
        self.current_state.processing_statistics.update(stats)
        
        logger.debug("Processing statistics updated")
    
    def can_resume(self) -> bool:
        """Check if processing can be resumed from saved state.
        
        Returns:
            True if resume is possible, False otherwise
        """
        try:
            if not self.state_file_path.exists():
                logger.debug("No state file found for resumption")
                return False
            
            # Try to load and validate state
            state_data = self.load_state()
            
            # Check if there are remaining pages to process
            if not self.current_state:
                return False
            
            remaining_pages = self.current_state.total_pages - len(self.current_state.completed_pages)
            
            if remaining_pages <= 0:
                logger.info("All pages already completed, no resumption needed")
                return False
            
            logger.info(f"Can resume processing: {remaining_pages} pages remaining")
            return True
            
        except Exception as e:
            logger.warning(f"Cannot resume processing: {e}")
            return False
    
    def get_next_page(self) -> Optional[int]:
        """Get next page to process.
        
        Returns:
            Next page number (1-indexed) or None if all done
        """
        if not self.current_state:
            return None
        
        if self.current_state.next_page >= self.current_state.total_pages:
            return None
        
        # Return 1-indexed page number
        return self.current_state.next_page + 1
    
    def get_completion_percentage(self) -> float:
        """Get completion percentage.
        
        Returns:
            Completion percentage (0-100)
        """
        if not self.current_state or self.current_state.total_pages == 0:
            return 0.0
        
        completed = len(self.current_state.completed_pages)
        return (completed / self.current_state.total_pages) * 100
    
    def get_processing_summary(self) -> Dict[str, Any]:
        """Get processing summary.
        
        Returns:
            Dictionary with processing summary
        """
        if not self.current_state:
            return {}
        
        completed_count = len(self.current_state.completed_pages)
        failed_count = len(self.current_state.failed_pages)
        remaining_count = self.current_state.total_pages - completed_count - failed_count
        
        return {
            "session_id": self.current_state.session_id,
            "total_pages": self.current_state.total_pages,
            "completed_pages": completed_count,
            "failed_pages": failed_count,
            "remaining_pages": remaining_count,
            "completion_percentage": self.get_completion_percentage(),
            "total_tasks_extracted": self.current_state.total_tasks_extracted,
            "api_calls_made": self.current_state.api_calls_made,
            "api_errors": self.current_state.api_errors,
            "session_start_time": self.current_state.session_start_time,
            "last_update_time": self.current_state.last_update_time,
            "next_page": self.get_next_page()
        }
    
    def cleanup_state(self) -> bool:
        """Clean up state file after successful completion.
        
        Returns:
            True if cleanup successful, False otherwise
        """
        try:
            if self.state_file_path.exists():
                # Create backup before deletion
                backup_path = self.state_file_path.with_suffix('.completed')
                self.state_file_path.rename(backup_path)
                
                logger.info(f"State file backed up to {backup_path} and cleaned up")
                return True
            else:
                logger.debug("No state file to clean up")
                return True
                
        except Exception as e:
            logger.error(f"Failed to cleanup state file: {e}")
            return False
    
    def validate_configuration(self, config_hash: str) -> bool:
        """Validate that current configuration matches saved state.
        
        Args:
            config_hash: Hash of current configuration
            
        Returns:
            True if configuration matches, False otherwise
        """
        if not self.current_state:
            return True  # No state to validate against
        
        if not self.current_state.configuration_hash:
            logger.warning("No configuration hash in saved state")
            return True  # Allow resumption without hash
        
        if self.current_state.configuration_hash != config_hash:
            logger.warning("Configuration has changed since last run")
            return False
        
        return True
    
    def get_failed_pages_report(self) -> Dict[int, str]:
        """Get report of failed pages and their errors.
        
        Returns:
            Dictionary mapping page numbers (1-indexed) to error messages
        """
        if not self.current_state:
            return {}
        
        # Convert to 1-indexed page numbers
        return {
            page_idx + 1: error_msg
            for page_idx, error_msg in self.current_state.processing_errors.items()
        }
    
    def export_state_report(self, output_path: Optional[str] = None) -> str:
        """Export detailed state report.
        
        Args:
            output_path: Optional path to save report
            
        Returns:
            Report as string
        """
        if not self.current_state:
            return "No processing state available"
        
        summary = self.get_processing_summary()
        failed_pages = self.get_failed_pages_report()
        
        report_lines = [
            "=== Processing State Report ===",
            f"Session ID: {summary['session_id']}",
            f"Started: {summary['session_start_time']}",
            f"Last Update: {summary['last_update_time']}",
            "",
            "Progress:",
            f"  Total Pages: {summary['total_pages']}",
            f"  Completed: {summary['completed_pages']}",
            f"  Failed: {summary['failed_pages']}",
            f"  Remaining: {summary['remaining_pages']}",
            f"  Completion: {summary['completion_percentage']:.1f}%",
            "",
            "Extraction Results:",
            f"  Total Tasks: {summary['total_tasks_extracted']}",
            f"  API Calls: {summary['api_calls_made']}",
            f"  API Errors: {summary['api_errors']}",
            "",
        ]
        
        if failed_pages:
            report_lines.append("Failed Pages:")
            for page_num, error in failed_pages.items():
                report_lines.append(f"  Page {page_num}: {error}")
            report_lines.append("")
        
        if self.current_state.processing_warnings:
            report_lines.append("Warnings:")
            for page_idx, warnings in self.current_state.processing_warnings.items():
                page_num = page_idx + 1
                for warning in warnings:
                    report_lines.append(f"  Page {page_num}: {warning}")
            report_lines.append("")
        
        report_lines.append("=== End Report ===")
        
        report_text = "\n".join(report_lines)
        
        # Save to file if requested
        if output_path:
            try:
                Path(output_path).write_text(report_text, encoding='utf-8')
                logger.info(f"State report saved to {output_path}")
            except Exception as e:
                logger.error(f"Failed to save report to {output_path}: {e}")
        
        return report_text 