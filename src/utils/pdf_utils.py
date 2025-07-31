"""PDF utilities for handling file operations and temporary directory management."""

import hashlib
from pathlib import Path
from typing import Optional
import os

from src.utils.logger import get_logger

logger = get_logger(__name__)


def calculate_file_md5(file_path: Path, chunk_size: int = 8192) -> str:
    """Calculate MD5 hash of file contents.
    
    Args:
        file_path: Path to the file
        chunk_size: Size of chunks to read (for memory efficiency)
        
    Returns:
        MD5 hash as hexadecimal string
        
    Raises:
        FileNotFoundError: If file doesn't exist
        OSError: If file cannot be read
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    md5_hash = hashlib.md5()
    
    try:
        with open(file_path, 'rb') as f:
            # Read file in chunks to handle large files efficiently
            while chunk := f.read(chunk_size):
                md5_hash.update(chunk)
        
        result = md5_hash.hexdigest()
        logger.debug(f"Calculated MD5 for {file_path}: {result[:8]}...")
        return result
        
    except OSError as e:
        logger.error(f"Failed to read file {file_path}: {e}")
        raise


def generate_unique_temp_dir(pdf_path: Path, base_temp_dir: Path = Path("temp")) -> Path:
    """Generate unique temporary directory for PDF file.
    
    Creates directory name using PDF basename + MD5 hash of file contents.
    Format: {basename_without_extension}_{md5_hash[:8]}
    
    Args:
        pdf_path: Path to the PDF file
        base_temp_dir: Base directory for temporary files
        
    Returns:
        Path to unique temporary directory
        
    Raises:
        FileNotFoundError: If PDF file doesn't exist
        OSError: If file cannot be read or directory cannot be created
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    # Get PDF basename without extension
    pdf_basename = pdf_path.stem
    
    # Calculate MD5 hash of file contents
    file_md5 = calculate_file_md5(pdf_path)
    
    # Create unique directory name
    # Use first 8 characters of MD5 for readability
    unique_dir_name = f"{pdf_basename}_{file_md5[:8]}"
    
    # Create full path
    temp_dir = base_temp_dir / unique_dir_name
    
    # Ensure directory exists
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Created unique temp directory: {temp_dir}")
    logger.debug(f"PDF: {pdf_path.name}, MD5: {file_md5[:8]}, Dir: {unique_dir_name}")
    
    return temp_dir


def get_pdf_unique_identifier(pdf_path: Path) -> str:
    """Get unique identifier for PDF file (basename + MD5 hash).
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Unique identifier string in format: {basename}_{md5_hash_8chars}
        
    Raises:
        FileNotFoundError: If PDF file doesn't exist
        OSError: If file cannot be read
    """
    pdf_basename = pdf_path.stem
    file_md5 = calculate_file_md5(pdf_path)
    return f"{pdf_basename}_{file_md5[:8]}"


def cleanup_temp_dir(temp_dir: Path, keep_processed_files: bool = False) -> None:
    """Clean up temporary directory.
    
    Args:
        temp_dir: Path to temporary directory
        keep_processed_files: If True, keep processed JSON files
    """
    try:
        if not temp_dir.exists():
            logger.debug(f"Temp directory doesn't exist: {temp_dir}")
            return
        
        files_removed = 0
        
        if keep_processed_files:
            # Remove only image files, keep JSON files
            for pattern in ["*.png", "*.jpg", "*.jpeg"]:
                for file in temp_dir.glob(pattern):
                    file.unlink()
                    files_removed += 1
        else:
            # Remove all files in directory
            for file in temp_dir.iterdir():
                if file.is_file():
                    file.unlink()
                    files_removed += 1
            
            # Try to remove directory if empty
            try:
                temp_dir.rmdir()
                logger.debug(f"Removed empty temp directory: {temp_dir}")
            except OSError:
                # Directory not empty, that's ok
                pass
        
        if files_removed > 0:
            logger.debug(f"Cleaned up {files_removed} files from {temp_dir}")
            
    except Exception as e:
        logger.warning(f"Failed to cleanup temp directory {temp_dir}: {e}")


def validate_pdf_file(pdf_path: Path) -> bool:
    """Validate that file exists and appears to be a PDF.
    
    Args:
        pdf_path: Path to check
        
    Returns:
        True if file appears to be a valid PDF
    """
    if not pdf_path.exists():
        logger.error(f"PDF file not found: {pdf_path}")
        return False
    
    if not pdf_path.is_file():
        logger.error(f"Path is not a file: {pdf_path}")
        return False
    
    # Check file size (should be > 0)
    if pdf_path.stat().st_size == 0:
        logger.error(f"PDF file is empty: {pdf_path}")
        return False
    
    # Check file extension
    if pdf_path.suffix.lower() != '.pdf':
        logger.warning(f"File doesn't have .pdf extension: {pdf_path}")
    
    # Basic file signature check (PDF files start with %PDF)
    try:
        with open(pdf_path, 'rb') as f:
            header = f.read(4)
            if not header.startswith(b'%PDF'):
                logger.warning(f"File doesn't appear to be a PDF (invalid header): {pdf_path}")
                return False
    except OSError as e:
        logger.error(f"Cannot read file: {pdf_path}, error: {e}")
        return False
    
    logger.debug(f"PDF file validation passed: {pdf_path}")
    return True 