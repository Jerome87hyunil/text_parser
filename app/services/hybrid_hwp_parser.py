"""
Hybrid HWP Parser - Combines comprehensive extraction with clean output.
Achieves optimal balance between text quantity and quality.
"""
import os
import re
import zlib
import struct
import subprocess
import unicodedata
from typing import Dict, Any, Optional, List, Tuple, Set
from pathlib import Path
import structlog
import olefile

logger = structlog.get_logger()


class HybridRecordExtractor:
    """Enhanced record extraction with multiple record type support."""
    
    # Comprehensive list of text-containing HWP tags
    TEXT_TAGS = {
        0x42: 'HWPTAG_PARA_TEXT',          # Main paragraph text
        0x43: 'HWPTAG_PARA_HEADER',        # Paragraph headers
        0x44: 'HWPTAG_PARA_CHAR_SHAPE',    # Character shape (may contain text)
        0x47: 'HWPTAG_CTRL_HEADER',        # Control headers (may contain text)
        0x4D: 'HWPTAG_TABLE',               # Table content
        0x57: 'HWPTAG_CTRL_DATA',           # Control data (may contain text)
        0x58: 'HWPTAG_EQEDIT',              # Equation text
        0x5C: 'HWPTAG_MEMO_LIST',           # Memo/comment text
    }
    
    def parse_records(self, data: bytes) -> List[Tuple[int, bytes]]:
        """
        Parse all records from decompressed BodyText data.
        
        Returns:
            List of (tag_id, record_data) tuples
        """
        records = []
        offset = 0
        
        while offset < len(data) - 4:
            # Parse record header
            header = struct.unpack_from('<I', data, offset)[0]
            tag_id = header & 0x3FF           # bits 0-9
            level = (header >> 10) & 0x3FF    # bits 10-19
            size = (header >> 20) & 0xFFF     # bits 20-31
            
            # Handle extended size
            if size == 0xFFF:
                if offset + 8 > len(data):
                    break
                size = struct.unpack_from('<I', data, offset + 4)[0]
                record_start = offset + 8
            else:
                record_start = offset + 4
            
            # Extract record data if it's a text-containing tag
            if tag_id in self.TEXT_TAGS:
                record_end = record_start + size
                if record_end <= len(data):
                    record_data = data[record_start:record_end]
                    records.append((tag_id, record_data))
                    logger.debug(f"Extracted {self.TEXT_TAGS[tag_id]}: {size} bytes")
            
            # Move to next record
            offset = record_start + size
        
        return records


class SmartTextDecoder:
    """Intelligent text decoding with Korean preservation."""
    
    def __init__(self):
        # Korean Unicode ranges
        self.HANGUL_SYLLABLES = (0xAC00, 0xD7AF)  # 가-힣
        self.HANGUL_JAMO = (0x1100, 0x11FF)       # ᄀ-ᇿ
        self.HANGUL_COMPAT = (0x3130, 0x318F)     # ㄱ-㆏
        
        # Valid character ranges
        self.valid_ranges = [
            (0x0020, 0x007E),  # Basic Latin (printable)
            (0x00A0, 0x00FF),  # Latin-1 Supplement
            (0xAC00, 0xD7AF),  # Hangul Syllables
            (0x1100, 0x11FF),  # Hangul Jamo
            (0x3130, 0x318F),  # Hangul Compatibility Jamo
            (0x3040, 0x309F),  # Hiragana
            (0x30A0, 0x30FF),  # Katakana
            (0x4E00, 0x9FFF),  # CJK Unified Ideographs
            (0x3400, 0x4DBF),  # CJK Extension A
        ]
    
    def decode_text(self, data: bytes) -> str:
        """
        Decode text data with proper Korean character preservation.
        
        Args:
            data: Raw bytes from HWP record
            
        Returns:
            Decoded text string
        """
        if not data:
            return ""
        
        # Try UTF-16LE first (standard for HWP)
        try:
            text = data.decode('utf-16le', errors='ignore')
        except:
            # Fallback to UTF-8
            try:
                text = data.decode('utf-8', errors='ignore')
            except:
                return ""
        
        # Filter characters while preserving Korean
        filtered_chars = []
        for char in text:
            code = ord(char)
            
            # Check if character is in valid ranges
            is_valid = False
            for start, end in self.valid_ranges:
                if start <= code <= end:
                    is_valid = True
                    break
            
            # Also keep common whitespace and newlines
            if is_valid or char in '\n\r\t ':
                filtered_chars.append(char)
            # Convert other whitespace to space
            elif char.isspace():
                filtered_chars.append(' ')
        
        return ''.join(filtered_chars)
    
    def is_korean_char(self, char: str) -> bool:
        """Check if a character is Korean."""
        code = ord(char)
        return (
            self.HANGUL_SYLLABLES[0] <= code <= self.HANGUL_SYLLABLES[1] or
            self.HANGUL_JAMO[0] <= code <= self.HANGUL_JAMO[1] or
            self.HANGUL_COMPAT[0] <= code <= self.HANGUL_COMPAT[1]
        )


class IntelligentNoiseCleaner:
    """Smart noise removal with text structure preservation."""
    
    def __init__(self):
        # Specific noise characters to remove
        self.noise_chars = {
            0x0842: 'ࡂ',  # Common noise character
            0x0943: 'ृ',  # Another common noise character
            0xFFFE: '',   # Byte order marks
            0xFFFF: '',   # Invalid Unicode
            0x0000: '',   # Null character
        }
        
        # Noise patterns (compiled regexes)
        self.noise_patterns = [
            re.compile(r'[ࡂृ]+'),                    # Specific noise chars
            re.compile(r'[\x00-\x08\x0B\x0C\x0E-\x1F]'),  # Control chars (except tab/newline)
            re.compile(r'[\uFFF0-\uFFFF]'),          # Specials block
            re.compile(r'B[ƀ]+'),                    # Common binary artifact pattern
            re.compile(r'䤀耈蠂'),                    # Another common artifact
        ]
        
        # Replacement patterns for cleaning
        self.replacements = {
            '　': ' ',    # Full-width space to normal space
            '＃': '#',    # Full-width to half-width
            '（': '(',    # Full-width parentheses
            '）': ')',
            '［': '[',
            '］': ']',
        }
    
    def clean_text(self, text: str) -> str:
        """
        Clean text while preserving structure and Korean content.
        
        Args:
            text: Text to clean
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        # Apply character replacements
        for old, new in self.replacements.items():
            text = text.replace(old, new)
        
        # Remove specific noise patterns
        for pattern in self.noise_patterns:
            text = pattern.sub('', text)
        
        # Remove specific noise characters
        for code, char in self.noise_chars.items():
            if char:
                text = text.replace(char, '')
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)  # Multiple spaces to single
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)  # Multiple newlines to double
        
        # Clean up each line
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if line and not self._is_noise_line(line):
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def _is_noise_line(self, line: str) -> bool:
        """Check if a line is mostly noise."""
        if len(line) < 3:
            return False  # Keep short lines
        
        # Count meaningful characters
        korean_count = sum(1 for c in line if 0xAC00 <= ord(c) <= 0xD7AF)
        english_count = sum(1 for c in line if c.isalpha() and ord(c) < 128)
        number_count = sum(1 for c in line if c.isdigit())
        
        meaningful = korean_count + english_count + number_count
        
        # If less than 20% meaningful characters, consider it noise
        return meaningful < len(line) * 0.2


class HybridBodyTextExtractor:
    """Main extraction engine combining all components."""
    
    def __init__(self):
        self.record_extractor = HybridRecordExtractor()
        self.text_decoder = SmartTextDecoder()
        self.noise_cleaner = IntelligentNoiseCleaner()
    
    def extract_from_stream(self, data: bytes) -> Tuple[str, List[Dict]]:
        """
        Extract text from a BodyText stream.
        
        Args:
            data: Compressed BodyText stream data
            
        Returns:
            Tuple of (extracted_text, paragraphs_list)
        """
        text_parts = []
        paragraphs = []
        
        # Decompress the data
        try:
            decompressed = zlib.decompress(data, -15)
        except:
            try:
                decompressed = zlib.decompress(data)
            except:
                # Try as uncompressed
                decompressed = data
        
        # Extract all text records
        records = self.record_extractor.parse_records(decompressed)
        
        for tag_id, record_data in records:
            # Decode text from record
            text = self.text_decoder.decode_text(record_data)
            
            if text:
                # Clean the text
                cleaned = self.noise_cleaner.clean_text(text)
                
                if cleaned:
                    text_parts.append(cleaned)
                    paragraphs.append({
                        'text': cleaned,
                        'tag_type': self.record_extractor.TEXT_TAGS.get(tag_id, 'unknown')
                    })
        
        # Combine all text parts
        full_text = '\n\n'.join(text_parts)
        
        return full_text, paragraphs


class HybridHWPParser:
    """
    Hybrid HWP Parser combining comprehensive extraction with clean output.
    
    Features:
    - Extracts from multiple record types for complete coverage
    - Preserves Korean text properly
    - Removes noise while maintaining structure
    - Achieves optimal balance between quantity and quality
    """
    
    def __init__(self):
        self.extractor = HybridBodyTextExtractor()
        logger.info("HybridHWPParser initialized")
    
    def parse(self, file_path: str) -> Dict[str, Any]:
        """
        Parse HWP file with hybrid approach.
        
        Args:
            file_path: Path to HWP file
            
        Returns:
            Dictionary containing extracted content
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        try:
            logger.info("Parsing with HybridHWPParser", file=file_path)
            
            with olefile.OleFileIO(file_path) as ole:
                result = {
                    "text": "",
                    "paragraphs": [],
                    "tables": [],
                    "metadata": self._extract_metadata(ole),
                    "parsing_method": "hybrid",
                    "statistics": {}
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
                            
                            # Extract text using hybrid method
                            text, paragraphs = self.extractor.extract_from_stream(data)
                            
                            if text:
                                all_text.append(text)
                                all_paragraphs.extend(paragraphs)
                                logger.debug(f"Extracted from {section_name}", 
                                           text_length=len(text))
                        except Exception as e:
                            logger.debug(f"Error processing {section_name}: {e}")
                
                # Combine all text
                result["text"] = '\n\n'.join(all_text)
                result["paragraphs"] = all_paragraphs
                
                # Final cleanup pass
                result["text"] = self.extractor.noise_cleaner.clean_text(result["text"])
                
                # Calculate statistics
                result["statistics"] = self._calculate_statistics(result["text"])
                
                logger.info("Successfully parsed with hybrid method",
                          text_length=len(result["text"]),
                          korean_ratio=result["statistics"].get("korean_ratio", 0))
                
                return result
                
        except Exception as e:
            logger.error(f"HybridHWPParser failed: {e}")
            return {
                "text": "",
                "paragraphs": [],
                "tables": [],
                "metadata": {},
                "error": str(e),
                "parsing_method": "hybrid_failed"
            }
    
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
    
    def _calculate_statistics(self, text: str) -> Dict[str, Any]:
        """Calculate text quality statistics."""
        if not text:
            return {'quality_score': 0}
        
        # Count different character types
        korean_chars = sum(1 for c in text if 0xAC00 <= ord(c) <= 0xD7AF)
        english_chars = sum(1 for c in text if c.isalpha() and ord(c) < 128)
        numbers = sum(1 for c in text if c.isdigit())
        spaces = text.count(' ')
        newlines = text.count('\n')
        
        # Count potential noise
        noise_chars = sum(1 for c in text if c in 'ࡂृ')
        control_chars = sum(1 for c in text if ord(c) < 32 and c not in '\n\r\t')
        
        total_chars = len(text)
        readable_chars = korean_chars + english_chars + numbers + spaces + newlines
        noise_total = noise_chars + control_chars
        
        return {
            'total_chars': total_chars,
            'korean_chars': korean_chars,
            'english_chars': english_chars,
            'numbers': numbers,
            'korean_ratio': (korean_chars / total_chars * 100) if total_chars > 0 else 0,
            'noise_ratio': (noise_total / total_chars * 100) if total_chars > 0 else 0,
            'quality_score': (readable_chars / total_chars * 100) if total_chars > 0 else 0
        }
    
    def extract_text(self, file_path: str) -> str:
        """Extract plain text from HWP file."""
        result = self.parse(file_path)
        return result.get("text", "")


# Export parser instance
hybrid_parser = HybridHWPParser()