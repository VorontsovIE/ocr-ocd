"""Page data model."""

import json
from typing import List, Optional, Dict, Any, Iterator
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from .task import Task


class ProcessingStatus:
    """Constants for page processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class Page(BaseModel):
    """Represents a page from the textbook with extracted tasks."""
    
    page_number: int = Field(
        ..., 
        ge=1, 
        description="Page number in the PDF (1-indexed)"
    )
    tasks: List[Task] = Field(
        default_factory=list, 
        description="List of tasks on this page"
    )
    image_path: Optional[str] = Field(
        default=None, 
        description="Path to page image file"
    )
    image_size_bytes: Optional[int] = Field(
        default=None,
        ge=0,
        description="Size of page image in bytes"
    )
    image_dimensions: Optional[tuple] = Field(
        default=None,
        description="Image dimensions as (width, height)"
    )
    processing_time: Optional[float] = Field(
        default=None, 
        ge=0.0,
        description="Time taken to process this page in seconds"
    )
    processing_status: str = Field(
        default=ProcessingStatus.PENDING,
        description="Current processing status"
    )
    errors: List[str] = Field(
        default_factory=list, 
        description="Any errors encountered during processing"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Warnings from processing"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional page metadata"
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="When this page was created"
    )
    processed_at: Optional[datetime] = Field(
        default=None,
        description="When this page was processed"
    )
    
    @field_validator('processing_status')
    @classmethod
    def validate_processing_status(cls, v):
        """Validate processing status."""
        valid_statuses = [
            ProcessingStatus.PENDING,
            ProcessingStatus.PROCESSING,
            ProcessingStatus.COMPLETED,
            ProcessingStatus.FAILED,
            ProcessingStatus.SKIPPED
        ]
        if v not in valid_statuses:
            raise ValueError(f"Invalid processing status: {v}")
        return v
    
    @field_validator('tasks')
    @classmethod
    def validate_tasks_page_numbers(cls, v, info):
        """Ensure all tasks have correct page number."""
        if info.data:
            page_number = info.data.get('page_number')
            if page_number:
                for task in v:
                    if task.page_number != page_number:
                        task.page_number = page_number
        return v
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
        json_schema_extra = {
            "example": {
                "page_number": 1,
                "tasks": [],
                "processing_status": "completed",
                "processing_time": 45.2,
                "image_path": "temp/page_0001.png"
            }
        }
    
    def add_task(self, task: Task) -> None:
        """Add a task to this page.
        
        Args:
            task: Task object to add
        """
        # Ensure task has correct page number
        if task.page_number != self.page_number:
            task.page_number = self.page_number
        
        self.tasks.append(task)
    
    def add_tasks(self, tasks: List[Task]) -> None:
        """Add multiple tasks to this page.
        
        Args:
            tasks: List of Task objects to add
        """
        for task in tasks:
            self.add_task(task)
    
    def remove_task(self, task_number: str) -> bool:
        """Remove a task by task number.
        
        Args:
            task_number: Task number to remove
            
        Returns:
            True if task was found and removed
        """
        for i, task in enumerate(self.tasks):
            if task.task_number == task_number:
                del self.tasks[i]
                return True
        return False
    
    def get_task(self, task_number: str) -> Optional[Task]:
        """Get a task by task number.
        
        Args:
            task_number: Task number to find
            
        Returns:
            Task object if found, None otherwise
        """
        for task in self.tasks:
            if task.task_number == task_number:
                return task
        return None
    
    def get_task_count(self) -> int:
        """Get number of tasks on this page.
        
        Returns:
            Number of tasks
        """
        return len(self.tasks)
    
    def get_tasks_with_images(self) -> List[Task]:
        """Get tasks that contain images.
        
        Returns:
            List of tasks with images
        """
        return [task for task in self.tasks if task.has_image]
    
    def get_unknown_tasks(self) -> List[Task]:
        """Get tasks with unknown numbers.
        
        Returns:
            List of tasks with unknown- numbers
        """
        return [task for task in self.tasks if task.is_unknown_number()]
    
    def get_high_confidence_tasks(self, threshold: float = 0.8) -> List[Task]:
        """Get tasks with high confidence scores.
        
        Args:
            threshold: Confidence threshold
            
        Returns:
            List of high confidence tasks
        """
        return [task for task in self.tasks if task.is_high_confidence(threshold)]
    
    def has_errors(self) -> bool:
        """Check if page has processing errors.
        
        Returns:
            True if there are errors
        """
        return len(self.errors) > 0
    
    def has_warnings(self) -> bool:
        """Check if page has processing warnings.
        
        Returns:
            True if there are warnings
        """
        return len(self.warnings) > 0
    
    def add_error(self, error_message: str) -> None:
        """Add an error message to this page.
        
        Args:
            error_message: Error description
        """
        timestamp = datetime.now().isoformat()
        self.errors.append(f"[{timestamp}] {error_message}")
    
    def add_warning(self, warning_message: str) -> None:
        """Add a warning message to this page.
        
        Args:
            warning_message: Warning description
        """
        timestamp = datetime.now().isoformat()
        self.warnings.append(f"[{timestamp}] {warning_message}")
    
    def set_processing_status(self, status: str) -> None:
        """Set processing status and timestamp.
        
        Args:
            status: New processing status
        """
        self.processing_status = status
        if status == ProcessingStatus.COMPLETED:
            self.processed_at = datetime.now()
    
    def is_processed(self) -> bool:
        """Check if page has been successfully processed.
        
        Returns:
            True if processing completed successfully
        """
        return self.processing_status == ProcessingStatus.COMPLETED
    
    def get_total_word_count(self) -> int:
        """Get total word count for all tasks on page.
        
        Returns:
            Total word count
        """
        return sum(task.get_word_count() for task in self.tasks)
    
    def get_average_confidence(self) -> Optional[float]:
        """Get average confidence score for all tasks.
        
        Returns:
            Average confidence score or None if no scores available
        """
        scores = [task.confidence_score for task in self.tasks 
                 if task.confidence_score is not None]
        
        if not scores:
            return None
        
        return sum(scores) / len(scores)
    
    def sort_tasks(self, by_number: bool = True) -> None:
        """Sort tasks on this page.
        
        Args:
            by_number: If True, sort by task number; if False, sort by confidence
        """
        if by_number:
            self.tasks.sort()
        else:
            # Sort by confidence score (descending)
            self.tasks.sort(
                key=lambda t: t.confidence_score or 0.0, 
                reverse=True
            )
    
    def to_dict(self, include_tasks: bool = True) -> Dict[str, Any]:
        """Convert page to dictionary.
        
        Args:
            include_tasks: Whether to include tasks in output
            
        Returns:
            Dictionary representation
        """
        data = self.dict()
        if not include_tasks:
            data.pop('tasks', None)
        return data
    
    def to_json(self, include_tasks: bool = True) -> str:
        """Convert page to JSON string.
        
        Args:
            include_tasks: Whether to include tasks in output
            
        Returns:
            JSON string representation
        """
        data = self.to_dict(include_tasks=include_tasks)
        return json.dumps(data, ensure_ascii=False, default=str)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get page processing summary.
        
        Returns:
            Summary dictionary with key metrics
        """
        return {
            "page_number": self.page_number,
            "task_count": self.get_task_count(),
            "tasks_with_images": len(self.get_tasks_with_images()),
            "unknown_tasks": len(self.get_unknown_tasks()),
            "processing_status": self.processing_status,
            "processing_time": self.processing_time,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "average_confidence": self.get_average_confidence(),
            "total_word_count": self.get_total_word_count()
        }
    
    def __iter__(self) -> Iterator[Task]:
        """Iterate over tasks."""
        return iter(self.tasks)
    
    def __len__(self) -> int:
        """Get number of tasks."""
        return len(self.tasks)
    
    def __getitem__(self, index: int) -> Task:
        """Get task by index."""
        return self.tasks[index]
    
    def __str__(self) -> str:
        """String representation of page."""
        status_emoji = {
            ProcessingStatus.PENDING: "⏳",
            ProcessingStatus.PROCESSING: "🔄", 
            ProcessingStatus.COMPLETED: "✅",
            ProcessingStatus.FAILED: "❌",
            ProcessingStatus.SKIPPED: "⏭️"
        }
        
        emoji = status_emoji.get(self.processing_status, "❓")
        error_str = f", {len(self.errors)} errors" if self.errors else ""
        
        return f"{emoji} Page {self.page_number}: {len(self.tasks)} tasks{error_str}"
    
    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata to this page."""
        if self.metadata is None:
            self.metadata = {}
        self.metadata[key] = value
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata value."""
        if self.metadata is None:
            return default
        return self.metadata.get(key, default)
    
    def add_error(self, error: str) -> None:
        """Add an error message."""
        if self.errors is None:
            self.errors = []
        self.errors.append(error)
        
    def add_warning(self, warning: str) -> None:
        """Add a warning message."""
        if self.warnings is None:
            self.warnings = []
        self.warnings.append(warning)
    
    def has_errors(self) -> bool:
        """Check if page has errors."""
        return bool(self.errors)
    
    def has_warnings(self) -> bool:
        """Check if page has warnings."""
        return bool(self.warnings)
        
    def set_processing_status(self, status: str) -> None:
        """Set processing status."""
        self.processing_status = status
        
    def is_processed(self) -> bool:
        """Check if page is successfully processed."""
        return self.processing_status == ProcessingStatus.COMPLETED 