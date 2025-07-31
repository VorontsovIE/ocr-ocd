"""CSV export module."""

import csv
import time
from typing import List, Optional, Dict, Any, Union
from pathlib import Path
from datetime import datetime
import pandas as pd

from src.models.task import Task
from src.models.page import Page
from src.utils.logger import get_logger, log_function_call, log_function_result

logger = get_logger(__name__)


class CSVExportError(Exception):
    """Custom exception for CSV export errors."""
    pass


class CSVWriter:
    """Handles exporting task data to CSV format."""
    
    def __init__(self, output_path: str, encoding: str = "utf-8", delimiter: str = ",") -> None:
        """Initialize CSV writer.
        
        Args:
            output_path: Output CSV file path
            encoding: File encoding (default: utf-8)
            delimiter: CSV delimiter (default: comma)
        """
        self.output_path = Path(output_path)
        self.encoding = encoding
        self.delimiter = delimiter
        self.export_stats = {
            "total_tasks_exported": 0,
            "total_pages_processed": 0,
            "high_confidence_tasks": 0,
            "unknown_numbered_tasks": 0,
            "tasks_with_images": 0,
            "export_start_time": None,
            "export_end_time": None
        }
        
        logger.info(f"CSVWriter initialized with output path: {self.output_path}")
    
    @log_function_call
    def write_tasks(self, pages: List[Page], include_metadata: bool = True) -> Dict[str, Any]:
        """Write tasks from multiple pages to CSV.
        
        Args:
            pages: List of Page objects containing tasks
            include_metadata: Whether to include task metadata columns
            
        Returns:
            Dictionary with export statistics
            
        Raises:
            CSVExportError: If export fails
        """
        try:
            self.export_stats["export_start_time"] = datetime.now()
            
            # Validate output path
            if not self.validate_output_path():
                raise CSVExportError(f"Invalid output path: {self.output_path}")
            
            # Collect all tasks from pages
            all_tasks = []
            processed_pages = 0
            
            for page in pages:
                if page.tasks:
                    all_tasks.extend(page.tasks)
                    processed_pages += 1
                    logger.debug(f"Collected {len(page.tasks)} tasks from page {page.page_number}")
            
            if not all_tasks:
                logger.warning("No tasks to export")
                return self._create_export_summary(0, processed_pages)
            
            # Create DataFrame and export
            df = self.create_dataframe(all_tasks, include_metadata)
            self._write_dataframe_to_csv(df)
            
            # Update statistics
            self._update_export_stats(all_tasks, processed_pages)
            
            self.export_stats["export_end_time"] = datetime.now()
            
            summary = self._create_export_summary(len(all_tasks), processed_pages)
            logger.info(f"CSV export completed successfully", **summary)
            
            return summary
            
        except Exception as e:
            error_msg = f"Failed to export tasks to CSV: {e}"
            logger.error(error_msg, output_path=str(self.output_path))
            raise CSVExportError(error_msg) from e
    
    def create_dataframe(self, tasks: List[Task], include_metadata: bool = True) -> pd.DataFrame:
        """Create pandas DataFrame from task list.
        
        Args:
            tasks: List of Task objects
            include_metadata: Whether to include metadata columns
            
        Returns:
            DataFrame with task data
            
        Raises:
            CSVExportError: If DataFrame creation fails
        """
        try:
            logger.debug(f"Creating DataFrame from {len(tasks)} tasks")
            
            # Sort tasks by page number and task number for consistent output
            sorted_tasks = sorted(tasks, key=lambda t: (t.page_number, t.task_number))
            
            # Create basic data structure
            data = []
            for task in sorted_tasks:
                row = self._task_to_csv_row(task, include_metadata)
                data.append(row)
            
            # Create DataFrame
            df = pd.DataFrame(data)
            
            # Ensure consistent column order
            column_order = self._get_column_order(include_metadata)
            df = df.reindex(columns=column_order, fill_value="")
            
            logger.debug(f"DataFrame created with shape: {df.shape}")
            return df
            
        except Exception as e:
            error_msg = f"Failed to create DataFrame: {e}"
            logger.error(error_msg, task_count=len(tasks))
            raise CSVExportError(error_msg) from e
    
    def _task_to_csv_row(self, task: Task, include_metadata: bool) -> Dict[str, Any]:
        """Convert Task object to CSV row dictionary.
        
        Args:
            task: Task object
            include_metadata: Whether to include metadata
            
        Returns:
            Dictionary representing CSV row
        """
        # Basic required columns
        row = {
            "page_number": task.page_number,
            "task_number": task.task_number,
            "task_text": task.task_text,
            "has_image": task.has_image
        }
        
        if include_metadata:
            # Optional metadata columns
            row.update({
                "confidence_score": task.confidence_score if task.confidence_score is not None else "",
                "processing_time": task.processing_time if task.processing_time is not None else "",
                "word_count": task.get_word_count(),
                "is_unknown_number": task.is_unknown_number(),
                "is_high_confidence": task.is_high_confidence(),
                "created_at": task.created_at.isoformat() if task.created_at else "",
                "extraction_source": task.get_metadata("extraction_source", ""),
                "text_cleaned": task.get_metadata("text_cleaned", ""),
                "raw_task_number": task.get_metadata("raw_task_number", "")
            })
        
        return row
    
    def _get_column_order(self, include_metadata: bool) -> List[str]:
        """Get consistent column order for CSV output.
        
        Args:
            include_metadata: Whether metadata columns are included
            
        Returns:
            List of column names in order
        """
        basic_columns = [
            "page_number",
            "task_number", 
            "task_text",
            "has_image"
        ]
        
        if include_metadata:
            metadata_columns = [
                "confidence_score",
                "processing_time",
                "word_count",
                "is_unknown_number",
                "is_high_confidence", 
                "created_at",
                "extraction_source",
                "text_cleaned",
                "raw_task_number"
            ]
            return basic_columns + metadata_columns
        
        return basic_columns
    
    def _write_dataframe_to_csv(self, df: pd.DataFrame) -> None:
        """Write DataFrame to CSV file.
        
        Args:
            df: DataFrame to write
            
        Raises:
            CSVExportError: If writing fails
        """
        try:
            # Ensure parent directory exists
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write to CSV with proper encoding
            df.to_csv(
                self.output_path,
                index=False,
                encoding=self.encoding,
                sep=self.delimiter,
                quoting=csv.QUOTE_MINIMAL,
                escapechar='\\',
                na_rep=""  # Empty string for NaN values
            )
            
            logger.info(f"CSV file written successfully: {self.output_path}")
            
        except Exception as e:
            error_msg = f"Failed to write CSV file: {e}"
            logger.error(error_msg, output_path=str(self.output_path))
            raise CSVExportError(error_msg) from e
    
    def validate_output_path(self) -> bool:
        """Validate output path is writable.
        
        Returns:
            True if path is valid and writable
        """
        try:
            # Check if parent directory exists or can be created
            parent_dir = self.output_path.parent
            if not parent_dir.exists():
                try:
                    parent_dir.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    logger.error(f"Cannot create output directory: {e}")
                    return False
            
            # Check if directory is writable
            if not parent_dir.is_dir():
                logger.error(f"Output parent is not a directory: {parent_dir}")
                return False
            
            # Try to create a test file to check write permissions
            test_file = parent_dir / ".write_test"
            try:
                test_file.touch()
                test_file.unlink()  # Remove test file
            except Exception as e:
                logger.error(f"No write permission for directory: {e}")
                return False
            
            # Check file extension
            if self.output_path.suffix.lower() != '.csv':
                logger.warning(f"Output file does not have .csv extension: {self.output_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"Path validation failed: {e}")
            return False
    
    def _update_export_stats(self, tasks: List[Task], processed_pages: int) -> None:
        """Update export statistics.
        
        Args:
            tasks: List of exported tasks
            processed_pages: Number of processed pages
        """
        self.export_stats.update({
            "total_tasks_exported": len(tasks),
            "total_pages_processed": processed_pages,
            "high_confidence_tasks": len([t for t in tasks if t.is_high_confidence()]),
            "unknown_numbered_tasks": len([t for t in tasks if t.is_unknown_number()]),
            "tasks_with_images": len([t for t in tasks if t.has_image])
        })
    
    def _create_export_summary(self, task_count: int, page_count: int) -> Dict[str, Any]:
        """Create export summary dictionary.
        
        Args:
            task_count: Number of tasks exported
            page_count: Number of pages processed
            
        Returns:
            Summary dictionary
        """
        return {
            "output_file": str(self.output_path),
            "tasks_exported": task_count,
            "pages_processed": page_count,
            "high_confidence_tasks": self.export_stats.get("high_confidence_tasks", 0),
            "unknown_numbered_tasks": self.export_stats.get("unknown_numbered_tasks", 0),
            "tasks_with_images": self.export_stats.get("tasks_with_images", 0),
            "export_time": self.export_stats.get("export_end_time"),
            "file_size_bytes": self.output_path.stat().st_size if self.output_path.exists() else 0
        }
    
    def append_tasks(self, new_pages: List[Page], include_metadata: bool = True) -> Dict[str, Any]:
        """Append new tasks to existing CSV file.
        
        Args:
            new_pages: List of new Page objects to append
            include_metadata: Whether to include metadata columns
            
        Returns:
            Dictionary with append statistics
            
        Raises:
            CSVExportError: If append fails
        """
        try:
            # Collect new tasks
            new_tasks = []
            for page in new_pages:
                new_tasks.extend(page.tasks)
            
            if not new_tasks:
                logger.info("No new tasks to append")
                return {"tasks_appended": 0, "pages_processed": 0}
            
            # Check if file exists
            if not self.output_path.exists():
                logger.info("Output file doesn't exist, creating new file")
                return self.write_tasks(new_pages, include_metadata)
            
            # Read existing data
            existing_df = pd.read_csv(self.output_path, encoding=self.encoding, sep=self.delimiter)
            
            # Create new data
            new_df = self.create_dataframe(new_tasks, include_metadata)
            
            # Combine and write
            combined_df = pd.concat([existing_df, new_df], ignore_index=True)
            self._write_dataframe_to_csv(combined_df)
            
            logger.info(f"Appended {len(new_tasks)} tasks to existing CSV")
            
            return {
                "tasks_appended": len(new_tasks),
                "pages_processed": len(new_pages),
                "total_tasks_in_file": len(combined_df)
            }
            
        except Exception as e:
            error_msg = f"Failed to append tasks to CSV: {e}"
            logger.error(error_msg)
            raise CSVExportError(error_msg) from e
    
    def get_export_statistics(self) -> Dict[str, Any]:
        """Get current export statistics.
        
        Returns:
            Dictionary with export statistics
        """
        return self.export_stats.copy()
    
    def create_export_report(self, pages: List[Page]) -> str:
        """Create a detailed export report.
        
        Args:
            pages: List of processed pages
            
        Returns:
            Formatted report string
        """
        total_tasks = sum(len(page.tasks) for page in pages)
        total_pages = len(pages)
        
        # Calculate statistics
        all_tasks = []
        for page in pages:
            all_tasks.extend(page.tasks)
        
        high_conf_count = len([t for t in all_tasks if t.is_high_confidence()])
        unknown_count = len([t for t in all_tasks if t.is_unknown_number()])
        image_count = len([t for t in all_tasks if t.has_image])
        
        avg_confidence = 0.0
        if all_tasks:
            confidences = [t.confidence_score for t in all_tasks if t.confidence_score is not None]
            if confidences:
                avg_confidence = sum(confidences) / len(confidences)
        
        report = f"""
=== CSV Export Report ===
Output File: {self.output_path}
Export Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Data Summary:
- Total Pages: {total_pages}
- Total Tasks: {total_tasks}
- Tasks with Images: {image_count} ({image_count/total_tasks*100:.1f}%)
- High Confidence Tasks: {high_conf_count} ({high_conf_count/total_tasks*100:.1f}%)
- Unknown Numbered Tasks: {unknown_count} ({unknown_count/total_tasks*100:.1f}%)
- Average Confidence: {avg_confidence:.3f}

File Details:
- Encoding: {self.encoding}
- Delimiter: '{self.delimiter}'
- File Size: {self.output_path.stat().st_size if self.output_path.exists() else 0} bytes

Quality Metrics:
- Task Number Coverage: {(total_tasks-unknown_count)/total_tasks*100:.1f}%
- Average Text Length: {sum(len(t.task_text) for t in all_tasks)/len(all_tasks):.1f} chars
- Pages with Errors: {len([p for p in pages if p.has_errors()])}
        """.strip()
        
        return report 