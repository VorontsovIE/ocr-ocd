"""Main application entry point for OCR-OCD."""

import sys
import time
import signal
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

import click
from tqdm import tqdm

from src.utils.config import load_config, Config
from src.utils.logger import setup_logger, get_logger, setup_development_logger, setup_production_logger
from src.utils.state_manager import StateManager
from src.utils.pdf_utils import generate_unique_temp_dir, validate_pdf_file, cleanup_temp_dir
from src.core.pdf_processor import PDFProcessor, PDFProcessingError
from src.core.vision_client import VisionClient, VisionAPIError
from src.core.data_extractor import DataExtractor, DataExtractionError
from src.core.csv_writer import CSVWriter, CSVExportError
from src.models.page import Page, ProcessingStatus

# Global variables for cleanup
pdf_processor: Optional[PDFProcessor] = None
state_manager: Optional[StateManager] = None
logger = None


def signal_handler(signum, frame):
    """Handle interrupt signals gracefully."""
    global pdf_processor, state_manager, logger
    
    if logger:
        logger.warning(f"Received signal {signum}, shutting down gracefully...")
    
    # Save current state
    if state_manager:
        try:
            state_manager.save_state()
            if logger:
                logger.info("Processing state saved successfully")
        except Exception as e:
            if logger:
                logger.error(f"Failed to save state: {e}")
    
    # Cleanup PDF processor
    if pdf_processor:
        try:
            pdf_processor.close()
            if logger:
                logger.info("PDF processor cleaned up")
        except Exception as e:
            if logger:
                logger.error(f"Failed to cleanup PDF processor: {e}")
    
    if logger:
        logger.info("Application shutdown complete")
    
    sys.exit(0)


class OCROCDOrchestrator:
    """Main orchestrator for the OCR-OCD pipeline."""
    
    def __init__(self, config: Config):
        """Initialize orchestrator with configuration.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.logger = get_logger(__name__)
        
        # Initialize components
        self.pdf_processor: Optional[PDFProcessor] = None
        self.vision_client: Optional[VisionClient] = None
        self.data_extractor = DataExtractor()
        self.csv_writer: Optional[CSVWriter] = None
        self.state_manager: Optional[StateManager] = None
        self.unique_temp_dir: Optional[Path] = None
        
        # Processing statistics
        self.stats = {
            "start_time": None,
            "end_time": None,
            "total_pages": 0,
            "processed_pages": 0,
            "successful_pages": 0,
            "failed_pages": 0,
            "total_tasks": 0,
            "api_calls": 0,
            "api_errors": 0,
            "total_processing_time": 0.0
        }
        
        self.logger.info("OCROCDOrchestrator initialized")
    
    def setup_components(self, input_pdf: str, output_csv: str) -> bool:
        """Setup all pipeline components.
        
        Args:
            input_pdf: Path to input PDF file
            output_csv: Path to output CSV file
            
        Returns:
            True if setup successful, False otherwise
        """
        try:
            pdf_path = Path(input_pdf)
            
            # Validate PDF file first
            if not validate_pdf_file(pdf_path):
                self.logger.error(f"PDF validation failed: {input_pdf}")
                return False
            
            # Generate unique temporary directory for this PDF
            unique_temp_dir = generate_unique_temp_dir(
                pdf_path=pdf_path,
                base_temp_dir=Path(self.config.temp_dir)
            )
            
            self.logger.info(f"Using unique temp directory: {unique_temp_dir}")
            
            # Setup PDF processor with unique temp directory
            self.pdf_processor = PDFProcessor(
                pdf_path=input_pdf,
                temp_dir=unique_temp_dir,
                dpi=300,
                image_format="PNG"
            )
            
            # Setup Vision client
            self.vision_client = VisionClient(self.config.api)
            
            # Setup CSV writer
            self.csv_writer = CSVWriter(output_csv)
            
            # Setup state manager with unique temp directory
            state_file = unique_temp_dir / "processing_state.json"
            self.state_manager = StateManager(str(state_file))
            
            # Store temp directory for cleanup
            self.unique_temp_dir = unique_temp_dir
            
            # Test API connection
            if not self.vision_client.test_api_connection():
                self.logger.error("Failed to connect to OpenAI API")
                return False
            
            if not self.csv_writer.validate_output_path():
                self.logger.error(f"Invalid output path: {output_csv}")
                return False
            
            self.logger.info("All components setup successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to setup components: {e}")
            return False
    
    def process_pdf(self, resume: bool = False) -> Dict[str, Any]:
        """Process the entire PDF document.
        
        Args:
            resume: Whether to resume from previous state
            
        Returns:
            Dictionary with processing results
        """
        self.stats["start_time"] = datetime.now()
        
        try:
            # Load or initialize state
            if resume and self.state_manager.can_resume():
                self.logger.info("Resuming from previous state")
                state = self.state_manager.load_state()
                start_page = state.get("next_page", 0)
            else:
                start_page = 0
                if resume:
                    self.logger.info("No valid state found, starting from beginning")
            
            # Load PDF
            with self.pdf_processor:
                self.pdf_processor.load_pdf()
                total_pages = self.pdf_processor.get_page_count()
                self.stats["total_pages"] = total_pages
                
                self.logger.info(f"Processing PDF with {total_pages} pages, starting from page {start_page + 1}")
                
                # Process pages with progress bar
                all_pages = []
                
                with tqdm(total=total_pages, initial=start_page, desc="Processing pages") as pbar:
                    for page_num in range(start_page, total_pages):
                        try:
                            page = self._process_single_page(page_num)
                            all_pages.append(page)
                            
                            if page.is_processed():
                                self.stats["successful_pages"] += 1
                                self.stats["total_tasks"] += len(page.tasks)
                            else:
                                self.stats["failed_pages"] += 1
                            
                            self.stats["processed_pages"] += 1
                            
                            # Update state
                            self.state_manager.update_progress(page_num + 1, total_pages)
                            
                            # Save state periodically
                            if page_num % 5 == 0:  # Every 5 pages
                                self.state_manager.save_state()
                            
                            pbar.update(1)
                            pbar.set_postfix({
                                'Tasks': self.stats["total_tasks"],
                                'Errors': self.stats["failed_pages"]
                            })
                            
                        except KeyboardInterrupt:
                            self.logger.warning("Processing interrupted by user")
                            break
                        except Exception as e:
                            self.logger.error(f"Failed to process page {page_num + 1}: {e}")
                            self.stats["failed_pages"] += 1
                            self.stats["processed_pages"] += 1
                            self.state_manager.add_error(page_num, str(e))
                            pbar.update(1)
                
                # Export to CSV
                if all_pages:
                    self.logger.info("Exporting results to CSV...")
                    csv_result = self.csv_writer.write_tasks(all_pages, include_metadata=True)
                    self.logger.info(f"Exported {csv_result['tasks_exported']} tasks to {csv_result['output_file']}")
                else:
                    self.logger.warning("No pages were successfully processed")
                
                # Cleanup state file on successful completion
                if self.stats["processed_pages"] == total_pages:
                    self.state_manager.cleanup_state()
                
                self.stats["end_time"] = datetime.now()
                
                return self._create_final_report(all_pages)
                
        except Exception as e:
            self.logger.error(f"PDF processing failed: {e}")
            self.stats["end_time"] = datetime.now()
            raise
    
    def _process_single_page(self, page_num: int) -> Page:
        """Process a single PDF page.
        
        Args:
            page_num: Page number (0-indexed)
            
        Returns:
            Processed Page object
        """
        page_start_time = time.time()
        
        try:
            self.logger.debug(f"Processing page {page_num + 1}")
            
            # Convert page to image
            image_data = self.pdf_processor.convert_page_to_image(page_num)
            image_info = {
                "size_bytes": len(image_data),
                "format": "PNG",
                "max_dimension": 2048  # From PDF processor settings
            }
            
            # Extract tasks with Vision API
            api_start_time = time.time()
            api_response = self.vision_client.extract_tasks_from_page(
                image_data, 
                page_num + 1,  # 1-indexed for user display
                use_fallback_on_error=True
            )
            self.stats["api_calls"] += 1
            
            if not api_response["json_valid"]:
                self.stats["api_errors"] += 1
                raise VisionAPIError("Failed to get valid JSON response from API")
            
            # Parse API response to create Page object
            page = self.data_extractor.parse_api_response(
                api_response["parsed_data"],
                page_num + 1,  # 1-indexed
                page_start_time,
                image_info
            )
            
            # Add API metadata to page
            page.add_metadata("api_model", api_response.get("model", "unknown"))
            page.add_metadata("api_tokens", api_response.get("usage", {}).get("total_tokens", 0))
            page.add_metadata("prompt_type", api_response.get("prompt_type", "standard"))
            
            processing_time = time.time() - page_start_time
            self.stats["total_processing_time"] += processing_time
            
            self.logger.info(
                f"Page {page_num + 1} processed successfully",
                tasks_extracted=len(page.tasks),
                processing_time=processing_time,
                api_tokens=api_response.get("usage", {}).get("total_tokens", 0)
            )
            
            return page
            
        except Exception as e:
            # Create failed page
            failed_page = Page(
                page_number=page_num + 1,
                processing_status=ProcessingStatus.FAILED,
                processing_time=time.time() - page_start_time
            )
            failed_page.add_error(f"Processing failed: {e}")
            
            self.logger.error(f"Failed to process page {page_num + 1}: {e}")
            return failed_page
    
    def _create_final_report(self, pages: List[Page]) -> Dict[str, Any]:
        """Create final processing report.
        
        Args:
            pages: List of processed pages
            
        Returns:
            Dictionary with final statistics
        """
        processing_duration = None
        if self.stats["start_time"] and self.stats["end_time"]:
            processing_duration = (self.stats["end_time"] - self.stats["start_time"]).total_seconds()
        
        # Calculate additional statistics
        extractor_stats = self.data_extractor.get_session_statistics()
        
        report = {
            "summary": {
                "total_pages": self.stats["total_pages"],
                "processed_pages": self.stats["processed_pages"],
                "successful_pages": self.stats["successful_pages"],
                "failed_pages": self.stats["failed_pages"],
                "success_rate": self.stats["successful_pages"] / max(self.stats["processed_pages"], 1) * 100,
                "total_tasks": self.stats["total_tasks"],
                "processing_duration_seconds": processing_duration,
                "avg_time_per_page": self.stats["total_processing_time"] / max(self.stats["processed_pages"], 1)
            },
            "api_usage": {
                "total_api_calls": self.stats["api_calls"],
                "api_errors": self.stats["api_errors"],
                "api_success_rate": (self.stats["api_calls"] - self.stats["api_errors"]) / max(self.stats["api_calls"], 1) * 100
            },
            "data_quality": {
                "unknown_numbered_tasks": extractor_stats.get("unknown_tasks_generated", 0),
                "text_cleanups_performed": extractor_stats.get("text_cleanups_performed", 0),
                "validation_errors": extractor_stats.get("validation_errors", 0)
            },
            "timing": {
                "start_time": self.stats["start_time"].isoformat() if self.stats["start_time"] else None,
                "end_time": self.stats["end_time"].isoformat() if self.stats["end_time"] else None,
                "total_processing_time": self.stats["total_processing_time"]
            }
        }
        
        return report
    
    def cleanup(self):
        """Cleanup orchestrator resources."""
        try:
            # Close PDF processor first
            if self.pdf_processor:
                self.pdf_processor.close()
            
            # Save final state
            if self.state_manager:
                self.state_manager.save_state()
            
            # Clean up unique temporary directory
            if self.unique_temp_dir:
                cleanup_temp_dir(self.unique_temp_dir, keep_processed_files=True)
                self.logger.info(f"Cleaned up temporary directory: {self.unique_temp_dir}")
            
            self.logger.info("Orchestrator cleanup completed")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")


@click.command()
@click.argument('input_pdf', type=click.Path(exists=True, path_type=Path))
@click.argument('output_csv', type=click.Path(path_type=Path))
@click.option('--config', '-c', type=click.Path(exists=True), help='Path to configuration file')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.option('--resume', '-r', is_flag=True, help='Resume from previous state if available')
@click.option('--production', '-p', is_flag=True, help='Use production logging (JSON format)')
def main(
    input_pdf: Path, 
    output_csv: Path, 
    config: Optional[Path], 
    verbose: bool,
    resume: bool,
    production: bool
) -> None:
    """OCR-OCD: Extract mathematical tasks from PDF textbooks using ChatGPT-4 Vision.
    
    INPUT_PDF: Path to the PDF file to process
    OUTPUT_CSV: Path where to save the extracted tasks in CSV format
    """
    global pdf_processor, state_manager, logger
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Load configuration
        app_config = load_config()
        
        # Setup logging
        if production:
            setup_production_logger()
        else:
            setup_development_logger()
        
        logger = get_logger(__name__)
        logger.info("=== OCR-OCD Application Started ===")
        logger.info(f"Input PDF: {input_pdf}")
        logger.info(f"Output CSV: {output_csv}")
        logger.info(f"Verbose mode: {verbose}")
        logger.info(f"Resume mode: {resume}")
        logger.info(f"Production mode: {production}")
        
        # Initialize orchestrator
        orchestrator = OCROCDOrchestrator(app_config)
        
        # Setup components
        if not orchestrator.setup_components(str(input_pdf), str(output_csv)):
            logger.error("Failed to setup application components")
            sys.exit(1)
        
        # Store global references for cleanup
        pdf_processor = orchestrator.pdf_processor
        state_manager = orchestrator.state_manager
        
        # Process PDF
        logger.info("Starting PDF processing...")
        click.echo(f"Processing {input_pdf} -> {output_csv}")
        
        result = orchestrator.process_pdf(resume=resume)
        
        # Display results
        summary = result["summary"]
        click.echo("\n" + "="*50)
        click.echo("PROCESSING COMPLETE")
        click.echo("="*50)
        click.echo(f"Total Pages: {summary['total_pages']}")
        click.echo(f"Processed: {summary['processed_pages']}")
        click.echo(f"Successful: {summary['successful_pages']}")
        click.echo(f"Failed: {summary['failed_pages']}")
        click.echo(f"Success Rate: {summary['success_rate']:.1f}%")
        click.echo(f"Total Tasks Extracted: {summary['total_tasks']}")
        
        if summary.get('processing_duration_seconds'):
            duration = summary['processing_duration_seconds']
            click.echo(f"Processing Time: {duration:.1f}s ({duration/60:.1f} min)")
            click.echo(f"Average per Page: {summary['avg_time_per_page']:.1f}s")
        
        # API usage
        api_stats = result["api_usage"]
        click.echo(f"\nAPI Calls: {api_stats['total_api_calls']}")
        click.echo(f"API Errors: {api_stats['api_errors']}")
        click.echo(f"API Success Rate: {api_stats['api_success_rate']:.1f}%")
        
        # Data quality
        quality = result["data_quality"]
        click.echo(f"\nData Quality:")
        click.echo(f"  Unknown Task Numbers: {quality['unknown_numbered_tasks']}")
        click.echo(f"  Text Cleanups: {quality['text_cleanups_performed']}")
        click.echo(f"  Validation Errors: {quality['validation_errors']}")
        
        click.echo(f"\nOutput saved to: {output_csv}")
        
        # Show CSV report if requested
        if verbose and orchestrator.csv_writer:
            click.echo("\n" + "="*50)
            click.echo("CSV EXPORT REPORT")
            click.echo("="*50)
            pages = []  # We'd need to store this from processing
            # For now, just show basic stats
            click.echo("Detailed CSV report available in logs.")
        
        # Cleanup
        orchestrator.cleanup()
        
        logger.info("=== OCR-OCD Application Completed Successfully ===")
        
        # Exit with appropriate code
        if summary['failed_pages'] > 0:
            sys.exit(2)  # Partial success
        else:
            sys.exit(0)  # Complete success
        
    except KeyboardInterrupt:
        logger.warning("Application interrupted by user")
        sys.exit(130)  # SIGINT exit code
    except Exception as e:
        if logger:
            logger.error(f"Application failed with error: {e}")
        else:
            click.echo(f"ERROR: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main() 