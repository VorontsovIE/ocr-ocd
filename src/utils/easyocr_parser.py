"""
Parser for EasyOCR TSV data to extract text information for specific pages.
"""

import csv
from typing import Dict, List, Any, Optional
from pathlib import Path
from dataclasses import dataclass
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class OCRWord:
    """Represents a single OCR word with coordinates and confidence."""
    text: str
    left: float
    top: float
    width: float
    height: float
    confidence: int
    word_num: int
    line_num: int
    block_num: int
    par_num: int


@dataclass
class OCRLine:
    """Represents a line of OCR text."""
    words: List[OCRWord]
    line_num: int
    block_num: int
    par_num: int
    
    @property
    def text(self) -> str:
        """Get full line text."""
        return " ".join(word.text for word in self.words)
    
    @property
    def confidence(self) -> float:
        """Get average confidence for the line."""
        if not self.words:
            return 0.0
        return sum(word.confidence for word in self.words) / len(self.words)


@dataclass 
class OCRPage:
    """Represents OCR data for a complete page."""
    page_number: int
    lines: List[OCRLine]
    
    @property
    def text(self) -> str:
        """Get full page text."""
        return "\n".join(line.text for line in self.lines if line.text.strip())
    
    @property
    def word_count(self) -> int:
        """Get total word count."""
        return sum(len(line.words) for line in self.lines)
    
    @property
    def avg_confidence(self) -> float:
        """Get average confidence for the page."""
        if not self.lines:
            return 0.0
        confidences = [line.confidence for line in self.lines if line.confidence > 0]
        return sum(confidences) / len(confidences) if confidences else 0.0
    
    def get_high_confidence_text(self, min_confidence: int = 80) -> str:
        """Get text with high confidence only."""
        high_conf_lines = []
        for line in self.lines:
            high_conf_words = [
                word.text for word in line.words 
                if word.confidence >= min_confidence and word.text.strip()
            ]
            if high_conf_words:
                high_conf_lines.append(" ".join(high_conf_words))
        return "\n".join(high_conf_lines)
    
    def get_numbers_and_operators(self) -> List[str]:
        """Extract numbers and mathematical operators."""
        math_elements = []
        for line in self.lines:
            for word in line.words:
                text = word.text.strip()
                # Check for numbers, operators, and mathematical symbols
                if (text.isdigit() or 
                    text in ['+', '-', '=', '>', '<', '×', '÷', ':', '.', ','] or
                    any(char.isdigit() for char in text)):
                    math_elements.append(text)
        return math_elements


class EasyOCRParser:
    """Parser for EasyOCR TSV output files."""
    
    def __init__(self, ocr_file_path: str):
        """Initialize parser with OCR file path.
        
        Args:
            ocr_file_path: Path to the TSV file with OCR data
        """
        self.ocr_file_path = Path(ocr_file_path)
        self.pages_cache: Dict[int, OCRPage] = {}
        
        if not self.ocr_file_path.exists():
            raise FileNotFoundError(f"OCR file not found: {ocr_file_path}")
        
        logger.info(f"EasyOCRParser initialized with file: {ocr_file_path}")
    
    def parse_page(self, page_number: int) -> Optional[OCRPage]:
        """Parse OCR data for a specific page.
        
        Args:
            page_number: Page number to extract
            
        Returns:
            OCRPage object with parsed data or None if page not found
        """
        if page_number in self.pages_cache:
            return self.pages_cache[page_number]
        
        try:
            page_lines = {}  # group by (par_num, block_num, line_num)
            
            with open(self.ocr_file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter='\t')
                
                for row in reader:
                    # Skip non-word entries (level != 5)
                    if row['level'] != '5':
                        continue
                    
                    # Check if this row is for our target page
                    if int(row['page_num']) != page_number:
                        continue
                    
                    # Skip entries without actual text
                    text = row['text'].strip()
                    if not text or text in ['###PAGE###', '###FLOW###', '###LINE###']:
                        continue
                    
                    # Create OCR word
                    try:
                        word = OCRWord(
                            text=text,
                            left=float(row['left']),
                            top=float(row['top']),
                            width=float(row['width']),
                            height=float(row['height']),
                            confidence=int(row['conf']) if row['conf'] != '-1' else 0,
                            word_num=int(row['word_num']),
                            line_num=int(row['line_num']),
                            block_num=int(row['block_num']),
                            par_num=int(row['par_num'])
                        )
                        
                        # Group words by line
                        line_key = (word.par_num, word.block_num, word.line_num)
                        if line_key not in page_lines:
                            page_lines[line_key] = []
                        page_lines[line_key].append(word)
                        
                    except (ValueError, KeyError) as e:
                        logger.warning(f"Error parsing OCR row for page {page_number}: {e}")
                        continue
            
            if not page_lines:
                logger.warning(f"No OCR data found for page {page_number}")
                return None
            
            # Create OCRLine objects
            lines = []
            for (par_num, block_num, line_num), words in page_lines.items():
                # Sort words by word_num to maintain order
                words.sort(key=lambda w: w.word_num)
                
                line = OCRLine(
                    words=words,
                    line_num=line_num,
                    block_num=block_num,
                    par_num=par_num
                )
                lines.append(line)
            
            # Sort lines by position (par_num, block_num, line_num)
            lines.sort(key=lambda l: (l.par_num, l.block_num, l.line_num))
            
            # Create OCRPage
            page = OCRPage(page_number=page_number, lines=lines)
            
            # Cache the result
            self.pages_cache[page_number] = page
            
            logger.debug(
                f"Parsed page {page_number}: {len(lines)} lines, "
                f"{page.word_count} words, avg_confidence: {page.avg_confidence:.1f}%"
            )
            
            return page
            
        except Exception as e:
            logger.error(f"Error parsing OCR data for page {page_number}: {e}")
            return None
    
    def get_page_summary(self, page_number: int) -> Dict[str, Any]:
        """Get summary information about OCR data for a page.
        
        Args:
            page_number: Page number to analyze
            
        Returns:
            Dictionary with summary statistics
        """
        page = self.parse_page(page_number)
        
        if not page:
            return {
                "page_number": page_number,
                "has_ocr_data": False,
                "error": "No OCR data found"
            }
        
        numbers = page.get_numbers_and_operators()
        high_conf_text = page.get_high_confidence_text()
        
        return {
            "page_number": page_number,
            "has_ocr_data": True,
            "total_words": page.word_count,
            "total_lines": len(page.lines),
            "avg_confidence": round(page.avg_confidence, 1),
            "full_text_length": len(page.text),
            "high_confidence_text_length": len(high_conf_text),
            "mathematical_elements": numbers[:20],  # First 20 math elements
            "sample_text": page.text[:200] + "..." if len(page.text) > 200 else page.text
        }
    
    def get_available_pages(self) -> List[int]:
        """Get list of available page numbers in OCR data.
        
        Returns:
            List of page numbers found in the OCR file
        """
        pages = set()
        
        try:
            with open(self.ocr_file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter='\t')
                
                for row in reader:
                    if row['level'] == '1':  # Page level
                        pages.add(int(row['page_num']))
                        
        except Exception as e:
            logger.error(f"Error reading available pages: {e}")
            return []
        
        return sorted(list(pages))
    
    def create_vision_prompt_supplement(self, page_number: int) -> str:
        """Create supplementary text for GPT-4 Vision prompt using OCR data.
        
        Args:
            page_number: Page number to process
            
        Returns:
            Formatted text to add to Vision API prompt
        """
        page = self.parse_page(page_number)
        
        if not page:
            return ""
        
        # Get high confidence text
        high_conf_text = page.get_high_confidence_text(min_confidence=85)
        
        # Get mathematical elements
        math_elements = page.get_numbers_and_operators()
        
        # Create supplement
        supplement = f"""
ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ ИЗ OCR:
Для уточнения распознавания используй этот текст, найденный на странице {page_number}:

Высокоточный текст (confidence ≥85%):
{high_conf_text[:500]}

Найденные числа и математические символы:
{' '.join(math_elements[:30])}

(Используй эту информацию как подсказку, но доверяй больше тому, что видишь на изображении)
"""
        
        return supplement.strip()


def test_ocr_parser():
    """Test function for OCR parser."""
    try:
        parser = EasyOCRParser("/home/vorontsovie/programming/math_textbooks/book_ocr.txt")
        
        print("🔍 Тестирование EasyOCR парсера...")
        
        # Test available pages
        pages = parser.get_available_pages()
        print(f"📄 Доступные страницы: {pages[:10]}... (всего {len(pages)})")
        
        # Test specific page
        test_page = 1
        summary = parser.get_page_summary(test_page)
        print(f"📊 Страница {test_page}: {summary}")
        
        # Test prompt supplement
        supplement = parser.create_vision_prompt_supplement(test_page)
        print(f"📝 Дополнение к промпту ({len(supplement)} символов):")
        print(supplement[:300] + "...")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
        return False


if __name__ == "__main__":
    test_ocr_parser() 