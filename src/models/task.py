"""Task data model."""

import json
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import datetime


class Task(BaseModel):
    """Represents a single mathematical task from the textbook."""
    
    page_number: int = Field(
        ..., 
        ge=1, 
        description="Page number where task is located (1-indexed)"
    )
    task_number: str = Field(
        ..., 
        min_length=1,
        max_length=100,
        description="Task number (original or unknown-X)"
    )
    task_text: str = Field(
        ..., 
        min_length=1,
        max_length=10000,
        description="Full text of the task"
    )
    has_image: bool = Field(
        default=False, 
        description="Whether task contains an image/diagram"
    )
    confidence_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score of text extraction (0-1)"
    )
    processing_time: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Time taken to process this task in seconds"
    )
    extraction_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata from extraction process"
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="When this task was created"
    )
    
    @field_validator('task_number')
    @classmethod
    def validate_task_number(cls, v):
        """Validate task number format."""
        if not v.strip():
            raise ValueError("Task number cannot be empty")
        
        # Allow original numbers (digits) or unknown- format
        if not (v.isdigit() or v.startswith('unknown-')):
            # Allow some flexibility for different numbering formats
            allowed_prefixes = ['№', 'N', 'n', 'задача', 'задание']
            if not any(v.lower().startswith(prefix.lower()) for prefix in allowed_prefixes):
                # If it doesn't match any known format, it's still valid but log a warning
                pass
        
        return v.strip()
    
    @field_validator('task_text')
    @classmethod
    def validate_task_text(cls, v):
        """Validate and clean task text."""
        if not v.strip():
            raise ValueError("Task text cannot be empty")
        
        # Basic text cleaning
        cleaned = v.strip()
        
        # Remove excessive whitespace
        import re
        cleaned = re.sub(r'\s+', ' ', cleaned)
        
        return cleaned
    
    @model_validator(mode='after')
    def validate_confidence_and_metadata(self):
        """Validate confidence score and metadata consistency."""
        confidence = self.confidence_score
        metadata = self.extraction_metadata or {}
        
        # If confidence is very low, add warning to metadata
        if confidence is not None and confidence < 0.3:
            metadata['low_confidence_warning'] = True
        
        self.extraction_metadata = metadata
        return self
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        json_schema_extra = {
            "example": {
                "page_number": 1,
                "task_number": "1",
                "task_text": "Сложи числа 2 + 3",
                "has_image": False,
                "confidence_score": 0.95,
                "processing_time": 1.5,
                "extraction_metadata": {"source": "vision_api"}
            }
        }
        
    def to_csv_row(self) -> Dict[str, Any]:
        """Convert task to CSV row format.
        
        Returns:
            Dictionary with CSV column names as keys
        """
        return {
            "page_number": self.page_number,
            "task_number": self.task_number,
            "task_text": self.task_text,
            "has_image": self.has_image,
            "confidence_score": self.confidence_score,
            "processing_time": self.processing_time,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
    
    def to_json(self, include_metadata: bool = False) -> str:
        """Convert task to JSON string.
        
        Args:
            include_metadata: Whether to include extraction metadata
            
        Returns:
            JSON string representation
        """
        data = self.dict()
        if not include_metadata:
            data.pop('extraction_metadata', None)
        
        return json.dumps(data, ensure_ascii=False, default=str)
    
    def get_display_text(self, max_length: int = 100) -> str:
        """Get shortened text for display purposes.
        
        Args:
            max_length: Maximum length of returned text
            
        Returns:
            Shortened task text with ellipsis if needed
        """
        if len(self.task_text) <= max_length:
            return self.task_text
        
        return self.task_text[:max_length-3] + "..."
    
    def is_unknown_number(self) -> bool:
        """Check if task has unknown number (generated by system).
        
        Returns:
            True if task number starts with 'unknown-'
        """
        return self.task_number.startswith('unknown-')
    
    def get_word_count(self) -> int:
        """Get word count of task text.
        
        Returns:
            Number of words in task text
        """
        return len(self.task_text.split())
    
    def is_high_confidence(self, threshold: float = 0.8) -> bool:
        """Check if task has high confidence score.
        
        Args:
            threshold: Confidence threshold (default 0.8)
            
        Returns:
            True if confidence score is above threshold
        """
        return self.confidence_score is not None and self.confidence_score >= threshold
    
    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata entry.
        
        Args:
            key: Metadata key
            value: Metadata value
        """
        self.extraction_metadata[key] = value
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata value.
        
        Args:
            key: Metadata key
            default: Default value if key not found
            
        Returns:
            Metadata value or default
        """
        return self.extraction_metadata.get(key, default)
    
    def __str__(self) -> str:
        """String representation of task."""
        confidence_str = f" (conf: {self.confidence_score:.2f})" if self.confidence_score else ""
        return f"Task {self.task_number} (page {self.page_number}){confidence_str}: {self.get_display_text(50)}"
    
    def __lt__(self, other: 'Task') -> bool:
        """Less than comparison for sorting."""
        if not isinstance(other, Task):
            return NotImplemented
        
        # Sort by page number first, then by task number
        if self.page_number != other.page_number:
            return self.page_number < other.page_number
        
        # For task numbers, try numeric comparison first
        try:
            self_num = int(self.task_number)
            other_num = int(other.task_number)
            return self_num < other_num
        except ValueError:
            # If not numeric, use string comparison
            return self.task_number < other.task_number 