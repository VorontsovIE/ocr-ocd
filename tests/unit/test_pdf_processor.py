"""Tests for PDF processor module."""

import tempfile
import io
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest
from src.core.pdf_processor import PDFProcessor, PDFProcessingError


class TestPDFProcessor:
    """Tests for PDFProcessor class."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.test_pdf_path = self.temp_dir / "test.pdf"
        self.processor = PDFProcessor(
            pdf_path=self.test_pdf_path,
            temp_dir=self.temp_dir / "temp",
            dpi=150
        )
    
    def test_init_default_params(self):
        """Test PDFProcessor initialization with default parameters."""
        processor = PDFProcessor(Path("test.pdf"))
        
        assert processor.pdf_path == Path("test.pdf")
        assert processor.temp_dir == Path("temp")
        assert processor.dpi == 150
        assert processor.image_format == "PNG"
        assert processor.doc is None
        assert processor.page_count == 0
    
    def test_init_custom_params(self):
        """Test PDFProcessor initialization with custom parameters."""
        processor = PDFProcessor(
            pdf_path="custom.pdf",
            temp_dir="custom_temp",
            dpi=300,
            image_format="jpeg"
        )
        
        assert processor.pdf_path == Path("custom.pdf")
        assert processor.temp_dir == Path("custom_temp")
        assert processor.dpi == 300
        assert processor.image_format == "JPEG"
    
    @patch('src.core.pdf_processor.fitz')
    def test_load_pdf_success(self, mock_fitz):
        """Test successful PDF loading."""
        # Create fake PDF file
        self.test_pdf_path.touch()
        
        # Mock fitz document
        mock_doc = Mock()
        mock_doc.__len__ = Mock(return_value=10)
        mock_fitz.open.return_value = mock_doc
        
        self.processor.load_pdf()
        
        assert self.processor.doc == mock_doc
        assert self.processor.page_count == 10
        mock_fitz.open.assert_called_once_with(str(self.test_pdf_path))
    
    def test_load_pdf_file_not_found(self):
        """Test PDF loading with non-existent file."""
        with pytest.raises(PDFProcessingError, match="PDF file not found"):
            self.processor.load_pdf()
    
    def test_load_pdf_not_a_file(self):
        """Test PDF loading with directory instead of file."""
        self.test_pdf_path.mkdir()
        
        with pytest.raises(PDFProcessingError, match="Path is not a file"):
            self.processor.load_pdf()
    
    @patch('src.core.pdf_processor.fitz')
    def test_load_pdf_corrupted_file(self, mock_fitz):
        """Test PDF loading with corrupted file."""
        self.test_pdf_path.touch()
        mock_fitz.open.side_effect = Exception("FileDataError: corrupted")
        
        with pytest.raises(PDFProcessingError, match="Failed to load PDF file"):
            self.processor.load_pdf()
    
    @patch('src.core.pdf_processor.fitz')
    def test_load_pdf_empty_document(self, mock_fitz):
        """Test PDF loading with empty document."""
        self.test_pdf_path.touch()
        mock_doc = Mock()
        mock_doc.__len__ = Mock(return_value=0)
        mock_fitz.open.return_value = mock_doc
        
        with pytest.raises(PDFProcessingError, match="PDF file contains no pages"):
            self.processor.load_pdf()
    
    def test_get_page_count_not_loaded(self):
        """Test getting page count when PDF is not loaded."""
        with pytest.raises(PDFProcessingError, match="PDF not loaded"):
            self.processor.get_page_count()
    
    def test_get_page_count_loaded(self):
        """Test getting page count when PDF is loaded."""
        mock_doc = Mock()
        self.processor.doc = mock_doc
        self.processor.page_count = 5
        
        assert self.processor.get_page_count() == 5
    
    def test_convert_page_to_image_not_loaded(self):
        """Test page conversion when PDF is not loaded."""
        with pytest.raises(PDFProcessingError, match="PDF not loaded"):
            self.processor.convert_page_to_image(0)
    
    def test_convert_page_to_image_invalid_page_number(self):
        """Test page conversion with invalid page number."""
        self.processor.doc = Mock()
        self.processor.page_count = 5
        
        with pytest.raises(PDFProcessingError, match="Page number .* out of range"):
            self.processor.convert_page_to_image(-1)
        
        with pytest.raises(PDFProcessingError, match="Page number .* out of range"):
            self.processor.convert_page_to_image(5)
    
    @patch('src.core.pdf_processor.Image')
    @patch('src.core.pdf_processor.fitz')
    def test_convert_page_to_image_success(self, mock_fitz, mock_image):
        """Test successful page conversion."""
        # Setup mocks
        mock_page = Mock()
        mock_pix = Mock()
        mock_pix.tobytes.return_value = b"fake_image_data"
        mock_page.get_pixmap.return_value = mock_pix
        
        mock_doc = Mock()
        mock_doc.__getitem__.return_value = mock_page
        
        mock_pil_image = Mock()
        mock_pil_image.size = (800, 600)
        mock_pil_image.mode = "RGB"
        mock_image.open.return_value = mock_pil_image
        
        # Setup processor
        self.processor.doc = mock_doc
        self.processor.page_count = 5
        
        # Mock file operations
        with patch('builtins.open', create=True) as mock_open:
            mock_file = Mock()
            mock_open.return_value.__enter__ = Mock(return_value=mock_file)
            mock_open.return_value.__exit__ = Mock(return_value=None)
            
            with patch('io.BytesIO') as mock_bytesio:
                mock_buffer = Mock()
                mock_buffer.getvalue.return_value = b"converted_image_data"
                mock_bytesio.return_value = mock_buffer
                
                result = self.processor.convert_page_to_image(0, save_to_file=True)
        
        assert result == b"converted_image_data"
        mock_page.get_pixmap.assert_called_once()
        mock_pil_image.save.assert_called_once()
    
    @patch('src.core.pdf_processor.Image')
    @patch('src.core.pdf_processor.fitz')
    def test_convert_page_large_image_resize(self, mock_fitz, mock_image):
        """Test page conversion with large image that needs resizing."""
        # Setup mocks for large image
        mock_page = Mock()
        mock_pix = Mock()
        mock_pix.tobytes.return_value = b"fake_image_data"
        mock_page.get_pixmap.return_value = mock_pix
        
        mock_doc = Mock()
        mock_doc.__getitem__.return_value = mock_page
        
        mock_pil_image = Mock()
        mock_pil_image.size = (4000, 3000)  # Large image
        mock_pil_image.mode = "RGB"
        mock_pil_image.width = 4000
        mock_pil_image.height = 3000
        
        # Mock resize
        mock_resized = Mock()
        mock_pil_image.resize.return_value = mock_resized
        mock_image.open.return_value = mock_pil_image
        
        self.processor.doc = mock_doc
        self.processor.page_count = 1
        
        with patch('io.BytesIO') as mock_bytesio:
            mock_buffer = Mock()
            mock_buffer.getvalue.return_value = b"resized_image_data"
            mock_bytesio.return_value = mock_buffer
            
            result = self.processor.convert_page_to_image(0)
        
        # Should call resize for large image
        mock_pil_image.resize.assert_called_once()
        mock_resized.save.assert_called_once()
    
    def test_process_all_pages_not_loaded(self):
        """Test processing all pages when PDF is not loaded."""
        with pytest.raises(PDFProcessingError, match="PDF not loaded"):
            list(self.processor.process_all_pages())
    
    @patch.object(PDFProcessor, 'convert_page_to_image')
    def test_process_all_pages_success(self, mock_convert):
        """Test successful processing of all pages."""
        self.processor.doc = Mock()
        self.processor.page_count = 3
        
        mock_convert.side_effect = [b"page0", b"page1", b"page2"]
        
        results = list(self.processor.process_all_pages())
        
        assert len(results) == 3
        assert results[0] == (0, b"page0")
        assert results[1] == (1, b"page1")
        assert results[2] == (2, b"page2")
        assert mock_convert.call_count == 3
    
    @patch.object(PDFProcessor, 'convert_page_to_image')
    def test_process_all_pages_with_errors(self, mock_convert):
        """Test processing all pages with some errors."""
        self.processor.doc = Mock()
        self.processor.page_count = 3
        
        # Second page fails
        mock_convert.side_effect = [
            b"page0",
            PDFProcessingError("Page 1 failed"),
            b"page2"
        ]
        
        results = list(self.processor.process_all_pages())
        
        assert len(results) == 2  # Only successful pages
        assert results[0] == (0, b"page0")
        assert results[1] == (2, b"page2")
    
    def test_get_page_info_not_loaded(self):
        """Test getting page info when PDF is not loaded."""
        with pytest.raises(PDFProcessingError, match="PDF not loaded"):
            self.processor.get_page_info(0)
    
    def test_get_page_info_invalid_page(self):
        """Test getting page info with invalid page number."""
        self.processor.doc = Mock()
        self.processor.page_count = 5
        
        with pytest.raises(PDFProcessingError, match="Page number .* out of range"):
            self.processor.get_page_info(-1)
    
    def test_get_page_info_success(self):
        """Test successful page info retrieval."""
        mock_rect = Mock()
        mock_rect.width = 612
        mock_rect.height = 792
        mock_rect.x0 = 0
        mock_rect.y0 = 0
        mock_rect.x1 = 612
        mock_rect.y1 = 792
        
        mock_page = Mock()
        mock_page.rect = mock_rect
        mock_page.rotation = 0
        mock_page.get_text.return_value = "Some text content"
        mock_page.get_images.return_value = ["image1"]
        
        mock_doc = Mock()
        mock_doc.__getitem__.return_value = mock_page
        
        self.processor.doc = mock_doc
        self.processor.page_count = 5
        
        info = self.processor.get_page_info(0)
        
        expected = {
            "page_number": 0,
            "width": 612,
            "height": 792,
            "rotation": 0,
            "has_text": True,
            "has_images": True,
            "media_box": (0, 0, 612, 792)
        }
        
        assert info == expected
    
    def test_cleanup_temp_files(self):
        """Test cleanup of temporary files."""
        # Create fake temp files
        temp_files = [
            self.processor.temp_dir / "page_0001.png",
            self.processor.temp_dir / "page_0002.png"
        ]
        
        self.processor.temp_dir.mkdir(exist_ok=True, parents=True)
        for temp_file in temp_files:
            temp_file.touch()
        
        # Verify files exist
        for temp_file in temp_files:
            assert temp_file.exists()
        
        self.processor.cleanup_temp_files()
        
        # Verify files are deleted
        for temp_file in temp_files:
            assert not temp_file.exists()
    
    def test_close(self):
        """Test closing PDF document."""
        mock_doc = Mock()
        self.processor.doc = mock_doc
        
        self.processor.close()
        
        mock_doc.close.assert_called_once()
        assert self.processor.doc is None
    
    @patch.object(PDFProcessor, 'load_pdf')
    @patch.object(PDFProcessor, 'close')
    @patch.object(PDFProcessor, 'cleanup_temp_files')
    def test_context_manager(self, mock_cleanup, mock_close, mock_load):
        """Test PDFProcessor as context manager."""
        with self.processor as proc:
            assert proc == self.processor
        
        mock_load.assert_called_once()
        mock_close.assert_called_once()
        mock_cleanup.assert_called_once()
    
    @patch.object(PDFProcessor, 'load_pdf')
    @patch.object(PDFProcessor, 'close')
    @patch.object(PDFProcessor, 'cleanup_temp_files')
    def test_context_manager_with_exception(self, mock_cleanup, mock_close, mock_load):
        """Test PDFProcessor context manager with exception."""
        mock_load.side_effect = Exception("Load failed")
        
        with pytest.raises(Exception, match="Load failed"):
            with self.processor:
                pass
        
        mock_load.assert_called_once()
        mock_close.assert_called_once()
        mock_cleanup.assert_called_once()


class TestPDFProcessingError:
    """Tests for PDFProcessingError exception."""
    
    def test_pdf_processing_error_creation(self):
        """Test creating PDFProcessingError."""
        error = PDFProcessingError("Test error message")
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)
    
    def test_pdf_processing_error_inheritance(self):
        """Test PDFProcessingError inheritance."""
        error = PDFProcessingError("Test error")
        assert isinstance(error, Exception)
        assert error.__class__.__name__ == "PDFProcessingError" 