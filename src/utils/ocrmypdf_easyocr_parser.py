"""
Optimized parser for OCRmyPDF-EasyOCR TSV output.
Handles the specific structure: OCRmyPDF + EasyOCR plugin → pdftotext -tsv
"""

import csv
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class OCRWord:
    """Represents a single word from OCRmyPDF-EasyOCR processing."""
    text: str
    left: float
    top: float
    width: float
    height: float
    confidence: int  # Always 100 for EasyOCR plugin
    word_num: int
    line_num: int
    block_num: int
    par_num: int
    
    @property
    def bbox(self) -> Tuple[float, float, float, float]:
        """Get bounding box coordinates (left, top, right, bottom)."""
        return (self.left, self.top, self.left + self.width, self.top + self.height)
    
    @property
    def center(self) -> Tuple[float, float]:
        """Get center coordinates."""
        return (self.left + self.width/2, self.top + self.height/2)


@dataclass
class OCRTextBlock:
    """Represents a text block (par_num, block_num combination)."""
    par_num: int
    block_num: int
    words: List[OCRWord]
    
    @property
    def text(self) -> str:
        """Get combined text of all words in block."""
        # Sort by line_num, then word_num to maintain reading order
        sorted_words = sorted(self.words, key=lambda w: (w.line_num, w.word_num))
        
        # Group by lines
        lines = {}
        for word in sorted_words:
            if word.line_num not in lines:
                lines[word.line_num] = []
            lines[word.line_num].append(word.text)
        
        # Join words in lines, then join lines
        line_texts = []
        for line_num in sorted(lines.keys()):
            line_texts.append(' '.join(lines[line_num]))
        
        return '\n'.join(line_texts)
    
    @property
    def bbox(self) -> Tuple[float, float, float, float]:
        """Get bounding box of entire block."""
        if not self.words:
            return (0, 0, 0, 0)
        
        lefts = [w.left for w in self.words]
        tops = [w.top for w in self.words]
        rights = [w.left + w.width for w in self.words]
        bottoms = [w.top + w.height for w in self.words]
        
        return (min(lefts), min(tops), max(rights), max(bottoms))
    
    @property
    def line_count(self) -> int:
        """Get number of lines in block."""
        return len(set(w.line_num for w in self.words))
    
    @property
    def word_count(self) -> int:
        """Get number of words in block."""
        return len(self.words)


@dataclass 
class OCRPage:
    """Represents OCRmyPDF-EasyOCR data for a complete page."""
    page_number: int
    text_blocks: List[OCRTextBlock]
    
    @property
    def text(self) -> str:
        """Get full page text with block separation."""
        block_texts = []
        for block in sorted(self.text_blocks, key=lambda b: (b.par_num, b.block_num)):
            block_text = block.text.strip()
            if block_text:
                block_texts.append(block_text)
        return '\n\n'.join(block_texts)
    
    @property
    def word_count(self) -> int:
        """Get total word count."""
        return sum(block.word_count for block in self.text_blocks)
    
    @property
    def block_count(self) -> int:
        """Get number of text blocks."""
        return len(self.text_blocks)
    
    @property
    def avg_confidence(self) -> float:
        """Get average confidence (always 100.0 for EasyOCR plugin)."""
        return 100.0
    
    def get_numbers_and_operators(self) -> List[str]:
        """Extract numbers and mathematical operators from all blocks."""
        math_elements = []
        for block in self.text_blocks:
            for word in block.words:
                text = word.text.strip()
                # Check for numbers, operators, and mathematical symbols
                if (text.isdigit() or 
                    text in ['+', '-', '=', '>', '<', '×', '÷', ':', '.', ',', '?'] or
                    any(char.isdigit() for char in text) or
                    any(math_char in text for math_char in ['№', '№.', 'см', 'м'])):
                    math_elements.append(text)
        return math_elements
    
    def get_math_blocks(self) -> List[OCRTextBlock]:
        """Get text blocks that likely contain mathematical content."""
        math_blocks = []
        
        for block in self.text_blocks:
            block_text = block.text.lower()
            numbers = self.get_numbers_and_operators()
            
            # Check if block contains mathematical indicators
            has_math = (
                any(num in block.text for num in numbers if num.isdigit()) or
                any(keyword in block_text for keyword in [
                    'сколько', 'найди', 'реши', 'вычисли', 'посчитай',
                    'больше', 'меньше', 'длиннее', 'короче',
                    'задач', 'пример', 'упражнение'
                ]) or
                any(char in block.text for char in ['+', '-', '=', '>', '<', '×', '÷'])
            )
            
            if has_math:
                math_blocks.append(block)
        
        return math_blocks
    
    def get_question_blocks(self) -> List[OCRTextBlock]:
        """Get text blocks that contain questions."""
        question_blocks = []
        
        for block in self.text_blocks:
            if '?' in block.text:
                question_blocks.append(block)
        
        return question_blocks


class OCRmyPDFEasyOCRParser:
    """Optimized parser for OCRmyPDF-EasyOCR TSV output files."""
    
    def __init__(self, ocr_file_path: str):
        """Initialize parser with OCRmyPDF-EasyOCR TSV file path.
        
        Args:
            ocr_file_path: Path to the TSV file with OCRmyPDF-EasyOCR data
        """
        self.ocr_file_path = Path(ocr_file_path)
        self.pages_cache: Dict[int, OCRPage] = {}
        
        if not self.ocr_file_path.exists():
            raise FileNotFoundError(f"OCRmyPDF-EasyOCR file not found: {ocr_file_path}")
        
        logger.info(f"OCRmyPDF-EasyOCR Parser initialized with file: {ocr_file_path}")
    
    def parse_page(self, page_number: int) -> Optional[OCRPage]:
        """Parse OCRmyPDF-EasyOCR data for a specific page.
        
        Args:
            page_number: Page number to extract
            
        Returns:
            OCRPage object with parsed data or None if page not found
        """
        if page_number in self.pages_cache:
            return self.pages_cache[page_number]
        
        try:
            # Group words by (par_num, block_num)
            blocks_data = {}
            
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
                            confidence=int(row['conf']) if row['conf'] != '-1' else 100,
                            word_num=int(row['word_num']),
                            line_num=int(row['line_num']),
                            block_num=int(row['block_num']),
                            par_num=int(row['par_num'])
                        )
                        
                        # Group words by text block
                        block_key = (word.par_num, word.block_num)
                        if block_key not in blocks_data:
                            blocks_data[block_key] = []
                        blocks_data[block_key].append(word)
                        
                    except (ValueError, KeyError) as e:
                        logger.warning(f"Error parsing OCRmyPDF row for page {page_number}: {e}")
                        continue
            
            if not blocks_data:
                logger.warning(f"No OCRmyPDF-EasyOCR data found for page {page_number}")
                return None
            
            # Create OCRTextBlock objects
            text_blocks = []
            for (par_num, block_num), words in blocks_data.items():
                block = OCRTextBlock(
                    par_num=par_num,
                    block_num=block_num,
                    words=words
                )
                text_blocks.append(block)
            
            # Create OCRPage
            page = OCRPage(page_number=page_number, text_blocks=text_blocks)
            
            # Cache the result
            self.pages_cache[page_number] = page
            
            logger.debug(
                f"Parsed OCRmyPDF page {page_number}: {len(text_blocks)} blocks, "
                f"{page.word_count} words, avg_confidence: {page.avg_confidence:.1f}%"
            )
            
            return page
            
        except Exception as e:
            logger.error(f"Error parsing OCRmyPDF data for page {page_number}: {e}")
            return None
    
    def get_page_summary(self, page_number: int) -> Dict[str, Any]:
        """Get summary information about OCRmyPDF-EasyOCR data for a page.
        
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
                "error": "No OCRmyPDF-EasyOCR data found"
            }
        
        numbers = page.get_numbers_and_operators()
        math_blocks = page.get_math_blocks()
        question_blocks = page.get_question_blocks()
        
        return {
            "page_number": page_number,
            "has_ocr_data": True,
            "total_words": page.word_count,
            "total_blocks": page.block_count,
            "avg_confidence": page.avg_confidence,
            "full_text_length": len(page.text),
            "mathematical_elements": numbers[:20],  # First 20 math elements
            "math_blocks_count": len(math_blocks),
            "question_blocks_count": len(question_blocks),
            "sample_text": page.text[:200] + "..." if len(page.text) > 200 else page.text,
            "ocr_engine": "OCRmyPDF-EasyOCR",
            "structure_type": "hierarchical_blocks"
        }
    
    def get_available_pages(self) -> List[int]:
        """Get list of available page numbers in OCRmyPDF-EasyOCR data.
        
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
        """Create supplementary text for GPT-4 Vision prompt using OCRmyPDF-EasyOCR data.
        
        Args:
            page_number: Page number to process
            
        Returns:
            Formatted text to add to Vision API prompt
        """
        page = self.parse_page(page_number)
        
        if not page:
            return ""
        
        # Get mathematical blocks
        math_blocks = page.get_math_blocks()
        question_blocks = page.get_question_blocks()
        
        # Get mathematical elements
        math_elements = page.get_numbers_and_operators()
        
        # Create enhanced supplement
        supplement_parts = [
            f"ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ ИЗ OCRmyPDF-EasyOCR:",
            f"Высокоточное распознавание (EasyOCR через GPU) для страницы {page_number}:"
        ]
        
        if math_blocks:
            supplement_parts.append(f"\nМатематические блоки ({len(math_blocks)} найдено):")
            for i, block in enumerate(math_blocks[:3], 1):  # First 3 math blocks
                block_text = block.text.replace('\n', ' ')[:100]
                supplement_parts.append(f"{i}. {block_text}")
        
        if question_blocks:
            supplement_parts.append(f"\nВопросы и задачи ({len(question_blocks)} найдено):")
            for i, block in enumerate(question_blocks[:3], 1):  # First 3 questions
                block_text = block.text.replace('\n', ' ')[:100]
                supplement_parts.append(f"{i}. {block_text}")
        
        if math_elements:
            supplement_parts.append(f"\nЧисла и операторы: {' '.join(math_elements[:15])}")
        
        supplement_parts.append(f"\n(Структурированная OCR информация: {page.block_count} блоков, {page.word_count} слов)")
        supplement_parts.append("(Используй эту информацию как высокоточную подсказку)")
        
        return '\n'.join(supplement_parts)


def test_ocrmypdf_parser():
    """Test function for OCRmyPDF-EasyOCR parser."""
    try:
        parser = OCRmyPDFEasyOCRParser("/home/vorontsovie/programming/math_textbooks/book_ocr.txt")
        
        print("🔍 Тестирование OCRmyPDF-EasyOCR парсера...")
        
        # Test available pages
        pages = parser.get_available_pages()
        print(f"📄 Доступные страницы: {pages[:10]}... (всего {len(pages)})")
        
        # Test specific page
        test_page = 4
        summary = parser.get_page_summary(test_page)
        print(f"📊 Страница {test_page}: {summary}")
        
        # Test prompt supplement
        supplement = parser.create_vision_prompt_supplement(test_page)
        print(f"📝 Дополнение к промпту ({len(supplement)} символов):")
        print(supplement[:400] + "...")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
        return False


if __name__ == "__main__":
    test_ocrmypdf_parser() 