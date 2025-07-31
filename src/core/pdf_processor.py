"""PDF processing module for converting pages to images."""

import io
from typing import Generator, Tuple, Optional
from pathlib import Path
import fitz  # PyMuPDF
from PIL import Image
from src.utils.logger import get_logger, log_error_with_context


logger = get_logger(__name__)


class PDFProcessingError(Exception):
    """Custom exception for PDF processing errors."""
    pass


class PDFProcessor:
    """Handles PDF file loading and page-to-image conversion."""
    
    def __init__(
        self, 
        pdf_path: Path, 
        temp_dir: Path = Path("temp"),
        dpi: int = 150,
        image_format: str = "PNG"
    ) -> None:
        """Initialize PDF processor.
        
        Args:
            pdf_path: Path to PDF file
            temp_dir: Directory for temporary image files
            dpi: DPI for image conversion (higher = better quality but larger size)
            image_format: Output image format (PNG, JPEG)
        """
        self.pdf_path = Path(pdf_path)
        self.temp_dir = Path(temp_dir)
        self.dpi = dpi
        self.image_format = image_format.upper()
        self.doc: Optional[fitz.Document] = None
        self.page_count = 0
        
        # Create temp directory if it doesn't exist
        self.temp_dir.mkdir(exist_ok=True, parents=True)
        
        logger.debug(
            f"PDFProcessor initialized",
            pdf_path=str(self.pdf_path),
            temp_dir=str(self.temp_dir),
            dpi=self.dpi,
            image_format=self.image_format
        )
    
    def load_pdf(self) -> None:
        """Load PDF file and get page count.
        
        Raises:
            PDFProcessingError: If PDF file cannot be loaded
        """
        try:
            if not self.pdf_path.exists():
                raise PDFProcessingError(f"PDF file not found: {self.pdf_path}")
            
            if not self.pdf_path.is_file():
                raise PDFProcessingError(f"Path is not a file: {self.pdf_path}")
            
            logger.info(f"Loading PDF file: {self.pdf_path}")
            self.doc = fitz.open(str(self.pdf_path))
            self.page_count = len(self.doc)
            
            if self.page_count == 0:
                raise PDFProcessingError("PDF file contains no pages")
            
            logger.info(f"PDF loaded successfully: {self.page_count} pages")
            
        except fitz.FileDataError as e:
            error_msg = f"Invalid or corrupted PDF file: {e}"
            log_error_with_context(
                PDFProcessingError(error_msg),
                {"pdf_path": str(self.pdf_path), "original_error": str(e)}
            )
            raise PDFProcessingError(error_msg) from e
        
        except Exception as e:
            error_msg = f"Failed to load PDF file: {e}"
            log_error_with_context(
                e,
                {"pdf_path": str(self.pdf_path), "operation": "load_pdf"}
            )
            raise PDFProcessingError(error_msg) from e
    
    def get_page_count(self) -> int:
        """Get total number of pages in PDF.
        
        Returns:
            Total page count
            
        Raises:
            PDFProcessingError: If PDF is not loaded
        """
        if self.doc is None:
            raise PDFProcessingError("PDF not loaded. Call load_pdf() first.")
        
        return self.page_count
    
    def convert_page_to_image(self, page_number: int, save_to_file: bool = False) -> bytes:
        """Convert specific PDF page to image.
        
        Args:
            page_number: Page number to convert (0-indexed)
            save_to_file: Whether to save image to temp directory
            
        Returns:
            Image data as bytes
            
        Raises:
            PDFProcessingError: If page conversion fails
        """
        if self.doc is None:
            raise PDFProcessingError("PDF not loaded. Call load_pdf() first.")
        
        if page_number < 0 or page_number >= self.page_count:
            raise PDFProcessingError(
                f"Page number {page_number} out of range (0-{self.page_count-1})"
            )
        
        try:
            logger.debug(f"Converting page {page_number} to image")
            
            # Get the page
            page = self.doc[page_number]
            
            # Create transformation matrix for DPI
            zoom = self.dpi / 72.0  # 72 DPI is default
            mat = fitz.Matrix(zoom, zoom)
            
            # Render page to pixmap
            pix = page.get_pixmap(matrix=mat)
            
            # Convert to PIL Image for better control
            img_data = pix.tobytes("png")
            pil_image = Image.open(io.BytesIO(img_data))
            
            # Optimize image for API (reduce size if too large)
            max_dimension = 2048  # Max dimension for API
            if max(pil_image.size) > max_dimension:
                ratio = max_dimension / max(pil_image.size)
                new_size = (int(pil_image.width * ratio), int(pil_image.height * ratio))
                pil_image = pil_image.resize(new_size, Image.Resampling.LANCZOS)
                logger.debug(f"Resized image to {new_size} for API compatibility")
            
            # Convert to bytes
            output_buffer = io.BytesIO()
            if self.image_format == "JPEG":
                # Convert RGBA to RGB for JPEG
                if pil_image.mode == "RGBA":
                    pil_image = pil_image.convert("RGB")
                pil_image.save(output_buffer, format="JPEG", quality=85)
            else:
                pil_image.save(output_buffer, format="PNG")
            
            image_bytes = output_buffer.getvalue()
            
            # Save to file if requested
            if save_to_file:
                filename = f"page_{page_number:04d}.{self.image_format.lower()}"
                file_path = self.temp_dir / filename
                with open(file_path, 'wb') as f:
                    f.write(image_bytes)
                logger.debug(f"Saved page image to {file_path}")
            
            logger.debug(
                f"Page {page_number} converted successfully",
                image_size_kb=len(image_bytes) // 1024,
                image_dimensions=pil_image.size
            )
            
            return image_bytes
            
        except Exception as e:
            error_msg = f"Failed to convert page {page_number} to image: {e}"
            log_error_with_context(
                e,
                {
                    "page_number": page_number,
                    "pdf_path": str(self.pdf_path),
                    "operation": "convert_page_to_image"
                }
            )
            raise PDFProcessingError(error_msg) from e
    
    def process_all_pages(self, save_images: bool = False) -> Generator[Tuple[int, bytes], None, None]:
        """Generator that yields page number and image data for each page.
        
        Args:
            save_images: Whether to save images to temp directory
        
        Yields:
            Tuple of (page_number, image_data)
            
        Raises:
            PDFProcessingError: If PDF processing fails
        """
        if self.doc is None:
            raise PDFProcessingError("PDF not loaded. Call load_pdf() first.")
        
        logger.info(f"Starting processing of all {self.page_count} pages")
        
        for page_num in range(self.page_count):
            try:
                image_data = self.convert_page_to_image(page_num, save_to_file=save_images)
                yield (page_num, image_data)
            except PDFProcessingError as e:
                logger.error(f"Skipping page {page_num} due to error: {e}")
                continue
        
        logger.info("Finished processing all pages")
    
    def get_page_info(self, page_number: int) -> dict:
        """Get information about specific page.
        
        Args:
            page_number: Page number (0-indexed)
            
        Returns:
            Dictionary with page information
            
        Raises:
            PDFProcessingError: If page info cannot be retrieved
        """
        if self.doc is None:
            raise PDFProcessingError("PDF not loaded. Call load_pdf() first.")
        
        if page_number < 0 or page_number >= self.page_count:
            raise PDFProcessingError(
                f"Page number {page_number} out of range (0-{self.page_count-1})"
            )
        
        try:
            page = self.doc[page_number]
            rect = page.rect
            
            return {
                "page_number": page_number,
                "width": rect.width,
                "height": rect.height,
                "rotation": page.rotation,
                "has_text": bool(page.get_text().strip()),
                "has_images": bool(page.get_images()),
                "media_box": (rect.x0, rect.y0, rect.x1, rect.y1)
            }
            
        except Exception as e:
            error_msg = f"Failed to get page {page_number} info: {e}"
            log_error_with_context(
                e,
                {"page_number": page_number, "operation": "get_page_info"}
            )
            raise PDFProcessingError(error_msg) from e
    
    def cleanup_temp_files(self) -> None:
        """Remove all temporary image files."""
        try:
            if self.temp_dir.exists():
                for file in self.temp_dir.glob(f"*.{self.image_format.lower()}"):
                    file.unlink()
                logger.debug("Cleaned up temporary image files")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp files: {e}")
    
    def close(self) -> None:
        """Close PDF document and cleanup resources."""
        if self.doc is not None:
            self.doc.close()
            self.doc = None
            logger.debug("PDF document closed")
    
    def __enter__(self):
        """Context manager entry."""
        self.load_pdf()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        self.cleanup_temp_files() 