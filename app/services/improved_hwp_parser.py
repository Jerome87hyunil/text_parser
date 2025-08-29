"""
Improved HWP Parser with accurate encoding handling.
Implements precise record parsing and text extraction.
"""
import os
import re
import zlib
import struct
import subprocess
import unicodedata
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import structlog
import olefile

logger = structlog.get_logger()


class HWPRecordParser:
    """Precise HWP record structure parser."""
    
    # HWP Tag definitions
    HWPTAG_DOCUMENT_PROPERTIES = 0x10
    HWPTAG_ID_MAPPINGS = 0x11
    HWPTAG_BIN_DATA = 0x12
    HWPTAG_FACE_NAME = 0x13
    HWPTAG_BORDER_FILL = 0x14
    HWPTAG_CHAR_SHAPE = 0x15
    HWPTAG_TAB_DEF = 0x16
    HWPTAG_NUMBERING = 0x17
    HWPTAG_BULLET = 0x18
    HWPTAG_PARA_SHAPE = 0x19
    HWPTAG_STYLE = 0x1A
    HWPTAG_DOC_DATA = 0x1B
    HWPTAG_DISTRIBUTE_DOC_DATA = 0x1C
    HWPTAG_COMPATIBLE_DOCUMENT = 0x20
    HWPTAG_LAYOUT_COMPATIBILITY = 0x21
    HWPTAG_TRACKCHANGE = 0x22
    HWPTAG_MEMO_SHAPE = 0x23
    HWPTAG_FORBIDDEN_CHAR = 0x5E
    HWPTAG_TRACK_CHANGE_AUTHOR = 0x60
    
    # Paragraph tags
    HWPTAG_PARA_HEADER = 0x43
    HWPTAG_PARA_TEXT = 0x42
    HWPTAG_PARA_CHAR_SHAPE = 0x44
    HWPTAG_PARA_LINE_SEG = 0x45
    HWPTAG_PARA_RANGE_TAG = 0x46
    HWPTAG_CTRL_HEADER = 0x47
    HWPTAG_LIST_HEADER = 0x48
    HWPTAG_PAGE_DEF = 0x49
    HWPTAG_FOOTNOTE_SHAPE = 0x4A
    HWPTAG_PAGE_BORDER_FILL = 0x4B
    HWPTAG_SHAPE_COMPONENT = 0x4C
    HWPTAG_TABLE = 0x4D
    HWPTAG_SHAPE_COMPONENT_LINE = 0x4E
    HWPTAG_SHAPE_COMPONENT_RECTANGLE = 0x4F
    HWPTAG_SHAPE_COMPONENT_ELLIPSE = 0x50
    HWPTAG_SHAPE_COMPONENT_ARC = 0x51
    HWPTAG_SHAPE_COMPONENT_POLYGON = 0x52
    HWPTAG_SHAPE_COMPONENT_CURVE = 0x53
    HWPTAG_SHAPE_COMPONENT_OLE = 0x54
    HWPTAG_SHAPE_COMPONENT_PICTURE = 0x55
    HWPTAG_SHAPE_COMPONENT_CONTAINER = 0x56
    HWPTAG_CTRL_DATA = 0x57
    HWPTAG_EQEDIT = 0x58
    HWPTAG_SHAPE_COMPONENT_TEXTART = 0x5A
    HWPTAG_FORM_OBJECT = 0x5B
    HWPTAG_MEMO_LIST = 0x5C
    HWPTAG_CHART_DATA = 0x5D
    HWPTAG_VIDEO_DATA = 0x5F
    HWPTAG_SHAPE_COMPONENT_UNKNOWN = 0x61
    
    @staticmethod
    def parse_record_header(data: bytes, offset: int) -> Tuple[int, int, int, int]:
        """
        Parse HWP record header.
        
        Returns:
            Tuple of (tag_id, level, size, next_offset)
        """
        if offset + 4 > len(data):
            return None, None, None, offset
        
        # Read 4-byte header
        header = struct.unpack_from('<I', data, offset)[0]
        
        # Extract fields from header
        tag_id = header & 0x3FF           # bits 0-9 (10 bits)
        level = (header >> 10) & 0x3FF    # bits 10-19 (10 bits)
        size = (header >> 20) & 0xFFF     # bits 20-31 (12 bits)
        
        # Check for extended size
        if size == 0xFFF:
            if offset + 8 > len(data):
                return None, None, None, offset
            size = struct.unpack_from('<I', data, offset + 4)[0]
            next_offset = offset + 8 + size
        else:
            next_offset = offset + 4 + size
        
        return tag_id, level, size, next_offset
    
    @staticmethod
    def extract_text_from_record(data: bytes, size: int) -> str:
        """
        Extract text from HWPTAG_PARA_TEXT record.
        
        Args:
            data: Record data
            size: Size of the record
            
        Returns:
            Extracted text string
        """
        if size == 0:
            return ""
        
        try:
            # HWP uses UTF-16LE for text
            text = data[:size].decode('utf-16le', errors='ignore')
            
            # Filter control characters
            filtered_text = []
            for char in text:
                code = ord(char)
                
                # Skip HWP control characters
                if code < 0x20 and code not in (0x09, 0x0A, 0x0D):
                    continue
                    
                # Special handling for HWP inline controls
                if 0x0001 <= code <= 0x001F:
                    # These are inline control characters
                    if code == 0x0D:  # Paragraph break
                        filtered_text.append('\n')
                    elif code == 0x0A:  # Line break
                        filtered_text.append('\n')
                    elif code == 0x09:  # Tab
                        filtered_text.append('\t')
                    # Skip other control characters
                    continue
                
                # Skip other non-printable characters
                if code == 0xFFFE or code == 0xFFFF:
                    continue
                
                filtered_text.append(char)
            
            return ''.join(filtered_text)
            
        except Exception as e:
            logger.debug(f"Error extracting text from record: {e}")
            return ""


class HWPTextExtractor:
    """Advanced text extraction with encoding fixes."""
    
    def __init__(self):
        self.record_parser = HWPRecordParser()
        
        # Common noise patterns in HWP files
        self.noise_patterns = [
            re.compile(r'[ࡂृ࡚]+'),  # Common noise characters
            re.compile(r'[\x00-\x08\x0B\x0C\x0E-\x1F]'),  # Control characters
            re.compile(r'[\uFFF0-\uFFFF]'),  # Specials block
            re.compile(r'[\u0080-\u009F]'),  # C1 control characters
        ]
        
        # Character replacements for better readability
        self.char_replacements = {
            '\u0001': '',  # Start of heading
            '\u0002': '',  # Start of text
            '\u0003': '',  # End of text
            '\u0004': '',  # End of transmission
            '\u0005': '',  # Enquiry
            '\u0006': '',  # Acknowledge
            '\u0007': '',  # Bell
            '\u0008': '',  # Backspace
            '\u000B': ' ',  # Vertical tab -> space
            '\u000C': '\n',  # Form feed -> newline
            '\u000E': '',  # Shift out
            '\u000F': '',  # Shift in
            '\u0010': '',  # Data link escape
            '\u0011': '',  # Device control 1
            '\u0012': '',  # Device control 2
            '\u0013': '',  # Device control 3
            '\u0014': '',  # Device control 4
            '\u0015': '',  # Negative acknowledge
            '\u0016': '',  # Synchronous idle
            '\u0017': '',  # End of transmission block
            '\u0018': '',  # Cancel
            '\u0019': '',  # End of medium
            '\u001A': '',  # Substitute
            '\u001B': '',  # Escape
            '\u001C': '',  # File separator
            '\u001D': '',  # Group separator
            '\u001E': '',  # Record separator
            '\u001F': '',  # Unit separator
        }
    
    def extract_from_bodytext(self, data: bytes) -> Tuple[str, List[Dict]]:
        """
        Extract text from BodyText stream with proper record parsing.
        
        Args:
            data: Compressed BodyText data
            
        Returns:
            Tuple of (text, paragraphs)
        """
        text_parts = []
        paragraphs = []
        
        try:
            # Decompress the data
            try:
                # Try with -15 window bits (raw deflate)
                decompressed = zlib.decompress(data, -15)
            except:
                try:
                    # Try with default window bits
                    decompressed = zlib.decompress(data)
                except:
                    # Not compressed or different format
                    decompressed = data
            
            # Parse records
            offset = 0
            while offset < len(decompressed):
                tag_id, level, size, next_offset = self.record_parser.parse_record_header(
                    decompressed, offset
                )
                
                if tag_id is None:
                    break
                
                # Extract data for this record
                if size > 0 and offset + 4 < len(decompressed):
                    if tag_id == HWPRecordParser.HWPTAG_PARA_TEXT:
                        # Extract text from paragraph text record
                        if size == 0xFFF:
                            # Extended size
                            record_data = decompressed[offset + 8:next_offset]
                        else:
                            record_data = decompressed[offset + 4:next_offset]
                        
                        text = self.record_parser.extract_text_from_record(record_data, len(record_data))
                        if text:
                            # Clean the text
                            cleaned_text = self.clean_text(text)
                            if cleaned_text:
                                text_parts.append(cleaned_text)
                                paragraphs.append({
                                    "text": cleaned_text,
                                    "level": level
                                })
                
                offset = next_offset
            
        except Exception as e:
            logger.debug(f"Error extracting from BodyText: {e}")
        
        return '\n\n'.join(text_parts), paragraphs
    
    def clean_text(self, text: str) -> str:
        """
        Clean extracted text by removing noise and normalizing.
        
        Args:
            text: Raw extracted text
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        # Apply character replacements
        for old, new in self.char_replacements.items():
            text = text.replace(old, new)
        
        # Remove noise patterns
        for pattern in self.noise_patterns:
            text = pattern.sub('', text)
        
        # Unicode normalization
        text = unicodedata.normalize('NFC', text)
        
        # Remove zero-width characters
        text = text.replace('\u200B', '')  # Zero-width space
        text = text.replace('\u200C', '')  # Zero-width non-joiner
        text = text.replace('\u200D', '')  # Zero-width joiner
        text = text.replace('\uFEFF', '')  # Zero-width no-break space
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)  # Multiple spaces to single
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)  # Multiple newlines to double
        
        # Remove leading/trailing whitespace from each line
        lines = text.split('\n')
        lines = [line.strip() for line in lines]
        text = '\n'.join(lines)
        
        return text.strip()


class ImprovedBodyTextParser:
    """Improved BodyText parser with accurate encoding."""
    
    def __init__(self):
        self.text_extractor = HWPTextExtractor()
    
    def parse(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Parse HWP file with improved encoding handling."""
        try:
            logger.info("Parsing with ImprovedBodyTextParser", file=file_path)
            
            with olefile.OleFileIO(file_path) as ole:
                result = {
                    "text": "",
                    "paragraphs": [],
                    "tables": [],
                    "metadata": self._extract_metadata(ole),
                    "parsing_method": "improved_bodytext"
                }
                
                all_text = []
                all_paragraphs = []
                
                # Process all BodyText sections
                for entry in ole.listdir():
                    if len(entry) == 2 and entry[0] == 'BodyText':
                        section_name = '/'.join(entry)
                        try:
                            stream = ole.openstream(entry)
                            data = stream.read()
                            
                            # Extract text with improved method
                            text, paragraphs = self.text_extractor.extract_from_bodytext(data)
                            
                            if text:
                                all_text.append(text)
                                all_paragraphs.extend(paragraphs)
                                
                        except Exception as e:
                            logger.debug(f"Error processing {section_name}: {e}")
                
                # Combine all text
                result["text"] = '\n\n'.join(all_text)
                result["paragraphs"] = all_paragraphs
                
                # Final cleanup
                result["text"] = self.text_extractor.clean_text(result["text"])
                
                if result["text"]:
                    logger.info("Successfully parsed with improved method", 
                              text_length=len(result["text"]))
                    return result
                
            return None
            
        except Exception as e:
            logger.warning(f"ImprovedBodyTextParser failed: {e}")
            return None
    
    def _extract_metadata(self, ole) -> Dict[str, Any]:
        """Extract metadata from OLE file."""
        metadata = {}
        try:
            if ole.exists('\x05HwpSummaryInformation'):
                try:
                    summary = ole.getproperties('\x05HwpSummaryInformation')
                    metadata['title'] = summary.get(2, '')
                    metadata['subject'] = summary.get(3, '')
                    metadata['author'] = summary.get(4, '')
                    metadata['keywords'] = summary.get(5, '')
                    metadata['created'] = str(summary.get(12, ''))
                    metadata['modified'] = str(summary.get(13, ''))
                except:
                    pass
        except:
            pass
        return metadata


class HWP5LibraryParser:
    """Improved hwp5 library integration."""
    
    def parse(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Parse using hwp5 library with better integration."""
        try:
            # Try different import methods
            try:
                # Method 1: Use hwp5 directly
                import hwp5
                
                logger.info("Parsing with hwp5 library", file=file_path)
                
                result = {
                    "text": "",
                    "paragraphs": [],
                    "tables": [],
                    "metadata": {},
                    "parsing_method": "hwp5_library"
                }
                
                # Open HWP file
                hwp = hwp5.filestructure.Hwp5File(file_path)
                
                # Extract text
                text_parts = []
                paragraphs = []
                
                # Get text from all paragraphs
                if hasattr(hwp, 'bodytext'):
                    for section in hwp.bodytext.sections:
                        for paragraph in section:
                            try:
                                para_text = paragraph.text
                                if para_text:
                                    # Clean the text
                                    extractor = HWPTextExtractor()
                                    cleaned = extractor.clean_text(para_text)
                                    if cleaned:
                                        text_parts.append(cleaned)
                                        paragraphs.append({"text": cleaned})
                            except:
                                pass
                
                result["text"] = '\n\n'.join(text_parts)
                result["paragraphs"] = paragraphs
                
                if result["text"]:
                    logger.info("Successfully parsed with hwp5", 
                              text_length=len(result["text"]))
                    return result
                    
            except ImportError:
                pass
            
            # Method 2: Try subprocess with hwp5-text
            try:
                cmd = ['hwp5-text', file_path]
                process = subprocess.run(cmd, capture_output=True, text=True, 
                                       timeout=30, encoding='utf-8')
                
                if process.returncode == 0 and process.stdout:
                    extractor = HWPTextExtractor()
                    text = extractor.clean_text(process.stdout)
                    
                    return {
                        "text": text,
                        "paragraphs": [{"text": p.strip()} 
                                     for p in text.split('\n\n') if p.strip()],
                        "tables": [],
                        "metadata": {},
                        "parsing_method": "hwp5_cli"
                    }
            except:
                pass
            
            return None
            
        except Exception as e:
            logger.warning(f"HWP5LibraryParser failed: {e}")
            return None


class ImprovedHWPParser:
    """Main improved HWP parser with better encoding handling."""
    
    def __init__(self):
        """Initialize with improved strategies."""
        self.strategies = [
            ImprovedBodyTextParser(),
            HWP5LibraryParser(),
        ]
        
        # Also keep original strategies as fallback
        try:
            from .enhanced_hwp_parser import (
                HWP5CLIStrategy,
                EnhancedPrvTextStrategy
            )
            self.strategies.extend([
                HWP5CLIStrategy(),
                EnhancedPrvTextStrategy()
            ])
        except:
            pass
        
        logger.info("ImprovedHWPParser initialized", 
                   strategy_count=len(self.strategies))
    
    def parse(self, file_path: str) -> Dict[str, Any]:
        """Parse HWP file with improved encoding handling."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        errors = []
        
        # Try each strategy
        for strategy in self.strategies:
            try:
                result = strategy.parse(file_path)
                if result and result.get("text"):
                    logger.info(f"Successfully parsed with {strategy.__class__.__name__}", 
                              text_length=len(result["text"]),
                              method=result.get("parsing_method"))
                    return result
            except Exception as e:
                error_msg = f"{strategy.__class__.__name__} failed: {str(e)}"
                errors.append(error_msg)
                logger.debug(error_msg)
        
        # If all strategies failed, return minimal result
        logger.error("All parsing strategies failed", errors=errors)
        return {
            "text": "",
            "paragraphs": [],
            "tables": [],
            "metadata": {},
            "errors": errors,
            "parsing_method": "failed"
        }
    
    def extract_text(self, file_path: str) -> str:
        """Extract plain text from HWP file."""
        result = self.parse(file_path)
        return result.get("text", "")


# Export parser instance
improved_parser = ImprovedHWPParser()