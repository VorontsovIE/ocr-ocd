"""Data extraction and structuring module."""

import re
import time
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from src.models.task import Task
from src.models.page import Page, ProcessingStatus
from src.utils.logger import get_logger, log_error_with_context

logger = get_logger(__name__)


class DataExtractionError(Exception):
    """Custom exception for data extraction errors."""
    pass


class DataExtractor:
    """Handles extraction and structuring of task data from API responses."""
    
    def __init__(self) -> None:
        """Initialize data extractor."""
        self.unknown_task_counter = 0
        self.session_stats = {
            "total_tasks_processed": 0,
            "unknown_tasks_generated": 0,
            "validation_errors": 0,
            "text_cleanups_performed": 0
        }
        
        logger.info("DataExtractor initialized")
    
    def parse_api_response(
        self, 
        response_data: Dict[str, Any], 
        page_number: int,
        processing_start_time: float,
        image_info: Optional[Dict[str, Any]] = None
    ) -> Page:
        """Parse API response and create Page object with tasks.
        
        Args:
            response_data: Raw API response data (parsed JSON)
            page_number: Page number
            processing_start_time: When processing started (for timing)
            image_info: Optional image metadata
            
        Returns:
            Page object with extracted tasks
            
        Raises:
            DataExtractionError: If parsing fails
        """
        try:
            # Create page object
            processing_time = time.time() - processing_start_time
            page = Page(
                page_number=page_number,
                processing_time=processing_time,
                processing_status=ProcessingStatus.PROCESSING
            )
            
            # Add image metadata if available
            if image_info:
                page.image_size_bytes = image_info.get("size_bytes")
                page.image_dimensions = image_info.get("dimensions")
                page.add_metadata("image_format", image_info.get("format"))
                page.add_metadata("image_max_dimension", image_info.get("max_dimension"))
            
            # Validate response structure
            if not isinstance(response_data, dict):
                raise DataExtractionError("Response data must be a dictionary")
            
            if "tasks" not in response_data:
                raise DataExtractionError("Response missing 'tasks' field")
            
            if not isinstance(response_data["tasks"], list):
                raise DataExtractionError("'tasks' field must be a list")
            
            # Extract tasks
            tasks_data = response_data["tasks"]
            logger.info(f"Processing {len(tasks_data)} tasks for page {page_number}")
            
            for i, task_data in enumerate(tasks_data):
                try:
                    task = self._extract_single_task(task_data, page_number)
                    page.add_task(task)
                    self.session_stats["total_tasks_processed"] += 1
                    
                except Exception as e:
                    error_msg = f"Failed to extract task {i}: {e}"
                    page.add_error(error_msg)
                    logger.warning(error_msg, task_index=i, task_data=task_data)
                    self.session_stats["validation_errors"] += 1
            
            # Add page info if available
            if "page_info" in response_data:
                page_info = response_data["page_info"]
                
                if "total_tasks" in page_info:
                    expected_tasks = page_info["total_tasks"]
                    actual_tasks = len(page.tasks)
                    
                    if expected_tasks != actual_tasks:
                        page.add_warning(
                            f"Expected {expected_tasks} tasks but extracted {actual_tasks}"
                        )
                
                if "processing_notes" in page_info:
                    page.add_metadata("api_notes", page_info["processing_notes"])
                
                # Add other page_info fields as metadata
                for key, value in page_info.items():
                    if key not in ["total_tasks", "processing_notes"]:
                        page.add_metadata(f"page_info_{key}", value)
            
            # Set final status
            if page.has_errors():
                page.set_processing_status(ProcessingStatus.FAILED)
            else:
                page.set_processing_status(ProcessingStatus.COMPLETED)
            
            logger.info(
                f"Page {page_number} extraction completed",
                tasks_extracted=len(page.tasks),
                errors=len(page.errors),
                warnings=len(page.warnings),
                processing_time=processing_time
            )
            
            return page
            
        except Exception as e:
            error_msg = f"Failed to parse API response for page {page_number}: {e}"
            log_error_with_context(
                e,
                {
                    "operation": "parse_api_response",
                    "page_number": page_number,
                    "response_data_type": type(response_data).__name__,
                    "response_keys": list(response_data.keys()) if isinstance(response_data, dict) else None
                }
            )
            raise DataExtractionError(error_msg) from e
    
    def _extract_single_task(self, task_data: Dict[str, Any], page_number: int) -> Task:
        """Extract single task from task data.
        
        Args:
            task_data: Raw task data dictionary
            page_number: Page number
            
        Returns:
            Task object
            
        Raises:
            DataExtractionError: If task extraction fails
        """
        try:
            # Validate required fields
            required_fields = ["task_number", "task_text", "has_image"]
            for field in required_fields:
                if field not in task_data:
                    raise DataExtractionError(f"Missing required field: {field}")
            
            # Extract and clean task number
            raw_task_number = str(task_data["task_number"]).strip()
            task_number = self._process_task_number(raw_task_number)
            
            # Extract and clean task text
            raw_task_text = str(task_data["task_text"]).strip()
            task_text = self.clean_task_text(raw_task_text)
            
            # Validate task text is not empty
            if not task_text:
                raise DataExtractionError("Task text cannot be empty")
            
            # Extract has_image flag
            has_image = bool(task_data["has_image"])
            
            # Extract confidence score if available
            confidence_score = None
            if "confidence" in task_data:
                try:
                    confidence_score = float(task_data["confidence"])
                    if not (0.0 <= confidence_score <= 1.0):
                        confidence_score = None
                except (ValueError, TypeError):
                    confidence_score = None
            
            # Create task object
            task = Task(
                page_number=page_number,
                task_number=task_number,
                task_text=task_text,
                has_image=has_image,
                confidence_score=confidence_score,
                created_at=datetime.now()
            )
            
            # Add extraction metadata
            task.add_metadata("extraction_source", "vision_api")
            task.add_metadata("raw_task_number", raw_task_number)
            task.add_metadata("text_cleaned", raw_task_text != task_text)
            
            # Add additional fields as metadata
            for key, value in task_data.items():
                if key not in required_fields + ["confidence"]:
                    task.add_metadata(f"api_{key}", value)
            
            logger.debug(
                f"Task extracted successfully",
                page_number=page_number,
                task_number=task_number,
                has_image=has_image,
                confidence=confidence_score,
                text_length=len(task_text)
            )
            
            return task
            
        except Exception as e:
            error_msg = f"Failed to extract task: {e}"
            log_error_with_context(
                e,
                {
                    "operation": "_extract_single_task",
                    "page_number": page_number,
                    "task_data": task_data
                }
            )
            raise DataExtractionError(error_msg) from e
    
    def _process_task_number(self, raw_number: str) -> str:
        """Process and validate task number.
        
        Args:
            raw_number: Raw task number from API
            
        Returns:
            Processed task number
        """
        if not raw_number or raw_number.lower() in ["unknown", "null", "none", ""]:
            return self.generate_unknown_task_number()
        
        # Clean task number
        cleaned_number = re.sub(r'[^\w\-\.\u0410-\u044f№]', '', raw_number)
        
        if not cleaned_number:
            return self.generate_unknown_task_number()
        
        return cleaned_number
    
    def generate_unknown_task_number(self) -> str:
        """Generate unknown task number.
        
        Returns:
            Unknown task number in format unknown-X
        """
        self.unknown_task_counter += 1
        self.session_stats["unknown_tasks_generated"] += 1
        unknown_number = f"unknown-{self.unknown_task_counter}"
        
        logger.debug(f"Generated unknown task number: {unknown_number}")
        return unknown_number
    
    def validate_task_data(self, task_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate extracted task data.
        
        Args:
            task_data: Raw task data dictionary
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Check required fields
        required_fields = ["task_number", "task_text", "has_image"]
        for field in required_fields:
            if field not in task_data:
                errors.append(f"Missing required field: {field}")
        
        # Validate task_text
        if "task_text" in task_data:
            task_text = str(task_data["task_text"]).strip()
            if not task_text:
                errors.append("Task text cannot be empty")
            elif len(task_text) > 10000:  # Very long text might be an error
                errors.append("Task text is unusually long")
        
        # Validate has_image
        if "has_image" in task_data:
            if not isinstance(task_data["has_image"], bool):
                try:
                    bool(task_data["has_image"])
                except (ValueError, TypeError):
                    errors.append("has_image must be boolean")
        
        # Validate confidence if present
        if "confidence" in task_data:
            try:
                confidence = float(task_data["confidence"])
                if not (0.0 <= confidence <= 1.0):
                    errors.append("Confidence must be between 0.0 and 1.0")
            except (ValueError, TypeError):
                errors.append("Confidence must be a number")
        
        is_valid = len(errors) == 0
        return is_valid, errors
    
    def clean_task_text(self, text: str) -> str:
        """Clean and normalize task text.
        
        Args:
            text: Raw task text
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        original_text = text
        
        # Basic text cleaning
        text = text.strip()
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove common OCR artifacts
        text = re.sub(r'[•·▪▫■□▲△]', '', text)  # Remove bullet points
        text = re.sub(r'\|+', ' ', text)  # Replace pipes with spaces
        text = re.sub(r'_{2,}', ' ', text)  # Replace multiple underscores
        
        # Fix common mathematical symbols
        text = text.replace('×', '×')  # Ensure proper multiplication sign
        text = text.replace('÷', '÷')  # Ensure proper division sign
        text = text.replace('−', '-')  # Replace minus sign with hyphen
        text = text.replace('≤', '≤')  # Less than or equal
        text = text.replace('≥', '≥')  # Greater than or equal
        
        # Clean up spacing around mathematical operators
        text = re.sub(r'\s*([+\-×÷=<>≤≥])\s*', r' \1 ', text)
        
        # Remove leading/trailing punctuation that might be OCR errors
        text = re.sub(r'^[^\w\u0410-\u044f№]+', '', text)
        text = re.sub(r'[^\w\u0410-\u044f?.!]+$', '', text)
        
        # Final cleanup
        text = text.strip()
        
        if text != original_text:
            self.session_stats["text_cleanups_performed"] += 1
            logger.debug(
                "Text cleaned",
                original_length=len(original_text),
                cleaned_length=len(text),
                changes_made=True
            )
        
        return text
    
    def extract_multiple_pages(
        self,
        responses_data: List[Dict[str, Any]],
        page_numbers: List[int],
        processing_times: Optional[List[float]] = None
    ) -> List[Page]:
        """Extract multiple pages from multiple API responses.
        
        Args:
            responses_data: List of API response data
            page_numbers: List of page numbers
            processing_times: Optional list of processing start times
            
        Returns:
            List of Page objects
            
        Raises:
            DataExtractionError: If extraction fails
        """
        if len(responses_data) != len(page_numbers):
            raise DataExtractionError("Mismatch between responses and page numbers")
        
        if processing_times and len(processing_times) != len(responses_data):
            raise DataExtractionError("Mismatch between responses and processing times")
        
        pages = []
        
        for i, (response_data, page_number) in enumerate(zip(responses_data, page_numbers)):
            try:
                start_time = processing_times[i] if processing_times else time.time()
                page = self.parse_api_response(response_data, page_number, start_time)
                pages.append(page)
                
            except Exception as e:
                logger.error(f"Failed to extract page {page_number}: {e}")
                # Create failed page
                failed_page = Page(
                    page_number=page_number,
                    processing_status=ProcessingStatus.FAILED
                )
                failed_page.add_error(f"Extraction failed: {e}")
                pages.append(failed_page)
        
        logger.info(
            f"Batch extraction completed",
            total_pages=len(pages),
            successful_pages=len([p for p in pages if p.is_processed()]),
            failed_pages=len([p for p in pages if not p.is_processed()])
        )
        
        return pages
    
    def get_session_statistics(self) -> Dict[str, Any]:
        """Get statistics for current extraction session.
        
        Returns:
            Dictionary with session statistics
        """
        return {
            **self.session_stats,
            "unknown_task_counter": self.unknown_task_counter,
            "session_duration": time.time(),  # Could track session start time
        }
    
    def reset_session_stats(self) -> None:
        """Reset session statistics."""
        self.session_stats = {
            "total_tasks_processed": 0,
            "unknown_tasks_generated": 0,
            "validation_errors": 0,
            "text_cleanups_performed": 0
        }
        self.unknown_task_counter = 0
        logger.info("Session statistics reset") 