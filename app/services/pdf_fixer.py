"""
PDF Fixer for corrupted Korean PDFs.
Attempts to extract and re-encode text properly.
"""
import structlog
from typing import Optional
import fitz  # PyMuPDF
from pathlib import Path

logger = structlog.get_logger()


class PDFFixer:
    """
    Fix corrupted PDFs with encoding issues.
    """
    
    def __init__(self):
        self.font_paths = self._find_korean_fonts()
    
    def _find_korean_fonts(self) -> list:
        """Find available Korean fonts on the system."""
        font_candidates = [
            # macOS
            "/System/Library/Fonts/AppleSDGothicNeo.ttc",
            "/Library/Fonts/NanumGothic.ttf",
            "/Library/Fonts/NanumMyeongjo.ttf",
            # Linux
            "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
            "/usr/share/fonts/truetype/nanum/NanumMyeongjo.ttf",
            "/usr/share/fonts/truetype/unfonts-core/UnBatang.ttf",
            # Windows
            "C:/Windows/Fonts/malgun.ttf",
            "C:/Windows/Fonts/batang.ttc",
        ]
        
        available_fonts = []
        for font_path in font_candidates:
            if Path(font_path).exists():
                available_fonts.append(font_path)
        
        return available_fonts
    
    def fix_pdf(self, input_path: str, output_path: str) -> bool:
        """
        Fix a corrupted PDF with encoding issues.
        
        Args:
            input_path: Path to corrupted PDF
            output_path: Path for fixed PDF
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Open the corrupted PDF
            doc = fitz.open(input_path)
            
            # Create a new PDF
            new_doc = fitz.open()
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Extract text with various methods
                text = self._extract_text_safely(page)
                
                # Create new page with same dimensions
                new_page = new_doc.new_page(
                    width=page.rect.width,
                    height=page.rect.height
                )
                
                # Try to preserve layout and formatting
                self._recreate_page_content(page, new_page, text)
            
            # Save the fixed PDF
            new_doc.save(output_path)
            new_doc.close()
            doc.close()
            
            logger.info(f"PDF fixed and saved to: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to fix PDF: {e}")
            return False
    
    def _extract_text_safely(self, page) -> str:
        """
        Extract text from page using multiple methods.
        
        Args:
            page: PyMuPDF page object
            
        Returns:
            Extracted text
        """
        # Try different extraction methods
        methods = [
            lambda: page.get_text("text"),
            lambda: page.get_text("blocks"),
            lambda: page.get_text("words"),
            lambda: page.get_text("html"),
            lambda: page.get_text("dict"),
        ]
        
        extracted_text = ""
        
        for method in methods:
            try:
                result = method()
                
                if isinstance(result, str):
                    extracted_text = result
                elif isinstance(result, list):
                    # Process blocks or words
                    for item in result:
                        if isinstance(item, tuple) and len(item) > 4:
                            # Block format: (x0, y0, x1, y1, text, ...)
                            extracted_text += str(item[4]) + "\n"
                        elif isinstance(item, dict):
                            extracted_text += item.get("text", "") + "\n"
                elif isinstance(result, dict):
                    # Process dict format
                    blocks = result.get("blocks", [])
                    for block in blocks:
                        if block.get("type") == 0:  # Text block
                            for line in block.get("lines", []):
                                for span in line.get("spans", []):
                                    extracted_text += span.get("text", "")
                                extracted_text += "\n"
                
                if extracted_text and not all(c in "■□" for c in extracted_text.strip()):
                    break
                    
            except Exception as e:
                logger.warning(f"Text extraction method failed: {e}")
                continue
        
        # Try to fix common encoding issues
        if "■" in extracted_text:
            # Attempt to decode as different encodings
            encodings = ['utf-8', 'cp949', 'euc-kr', 'iso-8859-1', 'utf-16']
            for encoding in encodings:
                try:
                    # This is a heuristic approach
                    fixed_text = extracted_text.encode('latin-1').decode(encoding, errors='ignore')
                    if "■" not in fixed_text:
                        extracted_text = fixed_text
                        break
                except:
                    continue
        
        return extracted_text
    
    def _recreate_page_content(self, old_page, new_page, text: str):
        """
        Recreate page content with proper encoding.
        
        Args:
            old_page: Original page
            new_page: New page to write to
            text: Extracted text
        """
        try:
            # Get page dimensions
            rect = old_page.rect
            
            # Try to preserve original layout
            blocks = old_page.get_text("dict").get("blocks", [])
            
            for block in blocks:
                if block.get("type") == 0:  # Text block
                    x = block["bbox"][0]
                    y = block["bbox"][1]
                    
                    block_text = ""
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            block_text += span.get("text", "")
                        block_text += "\n"
                    
                    # Insert text with proper font
                    if block_text.strip() and not all(c in "■□" for c in block_text.strip()):
                        fontsize = 11
                        if block.get("lines"):
                            if block["lines"][0].get("spans"):
                                fontsize = block["lines"][0]["spans"][0].get("size", 11)
                        
                        # Try to use a Korean font if available
                        fontname = "helv"
                        if self.font_paths:
                            try:
                                new_page.insert_font(
                                    fontname="korean",
                                    fontfile=self.font_paths[0]
                                )
                                fontname = "korean"
                            except:
                                pass
                        
                        new_page.insert_text(
                            (x, y),
                            block_text,
                            fontsize=fontsize,
                            fontname=fontname
                        )
                elif block.get("type") == 1:  # Image block
                    # Copy images
                    try:
                        img = old_page.get_pixmap(clip=fitz.Rect(block["bbox"]))
                        new_page.insert_image(
                            fitz.Rect(block["bbox"]),
                            pixmap=img
                        )
                    except:
                        pass
        
        except Exception as e:
            logger.error(f"Failed to recreate page content: {e}")
            # Fallback: just insert the text
            if text.strip():
                new_page.insert_text(
                    (50, 50),
                    text,
                    fontsize=11
                )