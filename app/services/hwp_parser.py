import structlog
from typing import Dict, List, Optional, Any
import os

logger = structlog.get_logger()


class HWPParser:
    """
    HWP file parser to extract content.
    Tries multiple methods to parse HWP files.
    """
    
    def __init__(self):
        self.parsers = []
        self._init_parsers()
    
    def _init_parsers(self):
        """Initialize available parsers based on installed libraries."""
        # Try enhanced parser first (highest priority)
        try:
            from .enhanced_hwp_parser import enhanced_parser
            self.parsers.append(("enhanced", enhanced_parser.parse))
            logger.info("Enhanced HWP parser initialized")
        except ImportError as e:
            logger.warning("Enhanced parser not available", error=str(e))
        
        # Try hwp5
        try:
            from . import hwp5_parser
            self.parsers.append(("hwp5", hwp5_parser.parse))
            logger.info("hwp5 parser initialized")
        except ImportError as e:
            logger.warning("hwp5 parser not available", error=str(e))
        
        # Try pyhwp
        try:
            from . import pyhwp_parser
            self.parsers.append(("pyhwp", pyhwp_parser.parse))
            logger.info("pyhwp parser initialized")
        except ImportError as e:
            logger.warning("pyhwp parser not available", error=str(e))
        
        # Fallback to olefile-based parser
        try:
            from . import olefile_parser
            self.parsers.append(("olefile", olefile_parser.parse))
            logger.info("olefile parser initialized")
        except ImportError as e:
            logger.warning("olefile parser not available", error=str(e))
    
    def parse(self, file_path: str) -> Dict[str, Any]:
        """
        Parse HWP file and extract content.
        
        Args:
            file_path: Path to HWP file
            
        Returns:
            Dict containing extracted content
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Check file extension
        file_ext = file_path.lower()
        
        # Handle HWPX files
        if file_ext.endswith('.hwpx'):
            try:
                from . import hwpx_parser
                logger.info("Parsing HWPX file", file=file_path)
                result = hwpx_parser.parse(file_path)
                logger.info("Successfully parsed HWPX", file=file_path)
                return result
            except Exception as e:
                logger.error("HWPX parser failed", error=str(e), file=file_path)
                raise
        
        # Handle PDF files
        elif file_ext.endswith('.pdf'):
            try:
                from . import pdf_parser
                logger.info("Parsing PDF file", file=file_path)
                result = pdf_parser.parse(file_path)
                logger.info("Successfully parsed PDF", file=file_path)
                return result
            except Exception as e:
                logger.error("PDF parser failed", error=str(e), file=file_path)
                raise
        
        # Regular HWP file parsing
        errors = []
        
        for parser_name, parser_func in self.parsers:
            try:
                logger.info(f"Trying {parser_name} parser", file=file_path)
                result = parser_func(file_path)
                logger.info(f"Successfully parsed with {parser_name}", file=file_path)
                return result
            except Exception as e:
                error_msg = f"{parser_name} failed: {str(e)}"
                errors.append(error_msg)
                logger.warning(error_msg, file=file_path)
                continue
        
        # If all parsers failed
        raise Exception(f"All parsers failed. Errors: {'; '.join(errors)}")
    
    def extract_text(self, file_path: str) -> str:
        """
        Extract plain text from HWP file.
        
        Args:
            file_path: Path to HWP file
            
        Returns:
            Extracted text as string
        """
        content = self.parse(file_path)
        
        # Extract text from parsed content
        text_parts = []
        
        # First check if there's already a combined text field
        # (some parsers provide this)
        if "text" in content and content["text"]:
            # If text field exists and has content, use it directly
            # to avoid duplication
            return content["text"]
        
        # Otherwise, extract from paragraphs
        if "paragraphs" in content:
            for para in content["paragraphs"]:
                if isinstance(para, dict) and "text" in para:
                    text_parts.append(para["text"])
                elif isinstance(para, str):
                    text_parts.append(para)
        
        # Also check tables for text content
        if "tables" in content:
            for table in content["tables"]:
                if isinstance(table, dict) and "rows" in table:
                    for row in table["rows"]:
                        if isinstance(row, list):
                            for cell in row:
                                if cell and isinstance(cell, str):
                                    text_parts.append(cell)
        
        return "\n\n".join(text_parts)