"""Tests for PDF utilities module."""

import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open

from src.utils.pdf_utils import (
    calculate_file_md5,
    generate_unique_temp_dir,
    get_pdf_unique_identifier,
    cleanup_temp_dir,
    validate_pdf_file
)


class TestCalculateFileMD5:
    """Test MD5 calculation functionality."""
    
    def test_calculate_md5_success(self):
        """Test MD5 calculation for a file."""
        # Create a temporary file with known content
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            content = b"test content for md5 calculation"
            tmp_file.write(content)
            tmp_file.flush()
            
            file_path = Path(tmp_file.name)
            
            # Calculate MD5
            md5_hash = calculate_file_md5(file_path)
            
            # Verify it's a valid MD5 hash (32 hex characters)
            assert len(md5_hash) == 32
            assert all(c in '0123456789abcdef' for c in md5_hash)
            
            # Cleanup
            file_path.unlink()
    
    def test_calculate_md5_nonexistent_file(self):
        """Test MD5 calculation for non-existent file."""
        nonexistent_file = Path("nonexistent_file.pdf")
        
        with pytest.raises(FileNotFoundError):
            calculate_file_md5(nonexistent_file)
    
    def test_calculate_md5_consistent_results(self):
        """Test that MD5 calculation is consistent."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            content = b"consistent content"
            tmp_file.write(content)
            tmp_file.flush()
            
            file_path = Path(tmp_file.name)
            
            # Calculate MD5 twice
            md5_1 = calculate_file_md5(file_path)
            md5_2 = calculate_file_md5(file_path)
            
            assert md5_1 == md5_2
            
            # Cleanup
            file_path.unlink()


class TestGenerateUniqueTempDir:
    """Test unique temporary directory generation."""
    
    def test_generate_unique_temp_dir_success(self):
        """Test successful generation of unique temp directory."""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            content = b"%PDF-1.4\ntest pdf content"
            tmp_file.write(content)
            tmp_file.flush()
            
            pdf_path = Path(tmp_file.name)
            
            with tempfile.TemporaryDirectory() as temp_base:
                base_temp_dir = Path(temp_base)
                
                # Generate unique temp directory
                unique_dir = generate_unique_temp_dir(pdf_path, base_temp_dir)
                
                # Verify directory was created
                assert unique_dir.exists()
                assert unique_dir.is_dir()
                
                # Verify naming format
                expected_basename = pdf_path.stem
                dir_name = unique_dir.name
                assert dir_name.startswith(expected_basename)
                assert '_' in dir_name
                assert len(dir_name.split('_')[-1]) == 8  # 8-char MD5 prefix
                
            # Cleanup
            pdf_path.unlink()
    
    def test_generate_unique_temp_dir_nonexistent_pdf(self):
        """Test with non-existent PDF file."""
        nonexistent_pdf = Path("nonexistent.pdf")
        
        with pytest.raises(FileNotFoundError):
            generate_unique_temp_dir(nonexistent_pdf)
    
    def test_generate_unique_temp_dir_consistent_naming(self):
        """Test that same PDF generates same directory name."""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            content = b"%PDF-1.4\nsame content"
            tmp_file.write(content)
            tmp_file.flush()
            
            pdf_path = Path(tmp_file.name)
            
            with tempfile.TemporaryDirectory() as temp_base:
                base_temp_dir = Path(temp_base)
                
                # Generate twice
                dir1 = generate_unique_temp_dir(pdf_path, base_temp_dir)
                dir2 = generate_unique_temp_dir(pdf_path, base_temp_dir)
                
                # Should be same directory
                assert dir1 == dir2
                
            # Cleanup
            pdf_path.unlink()


class TestGetPDFUniqueIdentifier:
    """Test PDF unique identifier generation."""
    
    def test_get_unique_identifier_success(self):
        """Test successful generation of unique identifier."""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            content = b"%PDF-1.4\nidentifier test"
            tmp_file.write(content)
            tmp_file.flush()
            
            pdf_path = Path(tmp_file.name)
            
            # Get identifier
            identifier = get_pdf_unique_identifier(pdf_path)
            
            # Verify format
            expected_basename = pdf_path.stem
            assert identifier.startswith(expected_basename)
            assert '_' in identifier
            assert len(identifier.split('_')[-1]) == 8  # 8-char MD5 prefix
            
            # Cleanup
            pdf_path.unlink()
    
    def test_get_unique_identifier_nonexistent_pdf(self):
        """Test with non-existent PDF file."""
        nonexistent_pdf = Path("nonexistent.pdf")
        
        with pytest.raises(FileNotFoundError):
            get_pdf_unique_identifier(nonexistent_pdf)


class TestCleanupTempDir:
    """Test temporary directory cleanup."""
    
    def test_cleanup_temp_dir_all_files(self):
        """Test cleanup of all files in directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test files
            (temp_path / "test.png").write_text("image")
            (temp_path / "test.json").write_text("data")
            (temp_path / "test.txt").write_text("text")
            
            # Cleanup all files
            cleanup_temp_dir(temp_path, keep_processed_files=False)
            
            # Directory should be empty (or removed)
            if temp_path.exists():
                assert len(list(temp_path.iterdir())) == 0
    
    def test_cleanup_temp_dir_keep_processed(self):
        """Test cleanup keeping processed JSON files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test files
            png_file = temp_path / "test.png"
            json_file = temp_path / "test.json"
            
            png_file.write_text("image")
            json_file.write_text("data")
            
            # Cleanup keeping processed files
            cleanup_temp_dir(temp_path, keep_processed_files=True)
            
            # PNG should be removed, JSON should remain
            assert not png_file.exists()
            assert json_file.exists()
    
    def test_cleanup_nonexistent_dir(self):
        """Test cleanup of non-existent directory."""
        nonexistent_dir = Path("nonexistent_directory")
        
        # Should not raise an exception
        cleanup_temp_dir(nonexistent_dir)


class TestValidatePDFFile:
    """Test PDF file validation."""
    
    def test_validate_pdf_file_success(self):
        """Test validation of valid PDF file."""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            # Write PDF header
            content = b"%PDF-1.4\nvalid pdf content"
            tmp_file.write(content)
            tmp_file.flush()
            
            pdf_path = Path(tmp_file.name)
            
            # Validate
            assert validate_pdf_file(pdf_path) is True
            
            # Cleanup
            pdf_path.unlink()
    
    def test_validate_pdf_file_nonexistent(self):
        """Test validation of non-existent file."""
        nonexistent_file = Path("nonexistent.pdf")
        
        assert validate_pdf_file(nonexistent_file) is False
    
    def test_validate_pdf_file_empty(self):
        """Test validation of empty file."""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            # Empty file
            tmp_file.flush()
            
            pdf_path = Path(tmp_file.name)
            
            assert validate_pdf_file(pdf_path) is False
            
            # Cleanup
            pdf_path.unlink()
    
    def test_validate_pdf_file_invalid_header(self):
        """Test validation of file with invalid PDF header."""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            # Invalid header
            content = b"Not a PDF file content"
            tmp_file.write(content)
            tmp_file.flush()
            
            pdf_path = Path(tmp_file.name)
            
            assert validate_pdf_file(pdf_path) is False
            
            # Cleanup
            pdf_path.unlink()
    
    def test_validate_pdf_file_wrong_extension(self):
        """Test validation of file with wrong extension."""
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmp_file:
            # Valid PDF content but wrong extension
            content = b"%PDF-1.4\nvalid pdf content"
            tmp_file.write(content)
            tmp_file.flush()
            
            pdf_path = Path(tmp_file.name)
            
            # Should still pass (warning logged but validation succeeds)
            assert validate_pdf_file(pdf_path) is True
            
            # Cleanup
            pdf_path.unlink()


class TestIntegration:
    """Integration tests for PDF utilities."""
    
    def test_full_workflow(self):
        """Test complete workflow from PDF to cleanup."""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            content = b"%PDF-1.4\nintegration test content"
            tmp_file.write(content)
            tmp_file.flush()
            
            pdf_path = Path(tmp_file.name)
            
            with tempfile.TemporaryDirectory() as temp_base:
                base_temp_dir = Path(temp_base)
                
                # Step 1: Validate PDF
                assert validate_pdf_file(pdf_path) is True
                
                # Step 2: Generate unique directory
                unique_dir = generate_unique_temp_dir(pdf_path, base_temp_dir)
                assert unique_dir.exists()
                
                # Step 3: Create some files in directory
                (unique_dir / "page_001.png").write_text("image")
                (unique_dir / "page_001.json").write_text("processed data")
                
                # Step 4: Get identifier
                identifier = get_pdf_unique_identifier(pdf_path)
                assert unique_dir.name == identifier
                
                # Step 5: Cleanup
                cleanup_temp_dir(unique_dir, keep_processed_files=True)
                
                # Verify JSON kept, PNG removed
                assert (unique_dir / "page_001.json").exists()
                assert not (unique_dir / "page_001.png").exists()
                
            # Cleanup
            pdf_path.unlink() 