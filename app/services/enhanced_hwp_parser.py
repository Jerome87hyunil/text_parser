"""
Enhanced HWP Parser with complete text extraction capabilities.
Implements multiple parsing strategies with fallback mechanisms.

v2.0: 노이즈 문자 제거, 텍스트 정제 파이프라인 강화
"""
import os
import re
import zlib
import struct
import subprocess
import tempfile
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Set
from pathlib import Path
import structlog
import olefile

logger = structlog.get_logger()

# 노이즈 문자 패턴 정의 (HWP에서 자주 발생하는 인코딩 깨짐)
NOISE_CHARS: Set[str] = {
    'ࡂ', 'ृ', 'ƀ', 'ą', '褀', '褅', '耈', '蠂',  # 문서에서 언급된 패턴
    '\x00', '\x01', '\x02', '\x03', '\x04', '\x05',  # 제어 문자
    '\u200b', '\u200c', '\u200d', '\ufeff',  # 제로폭 문자
}

# 유효한 한글/영문/숫자/기본문장부호 유니코드 범위
VALID_CHAR_RANGES = [
    (0x0020, 0x007E),  # ASCII 문자
    (0x00A0, 0x00FF),  # Latin-1 Supplement
    (0xAC00, 0xD7A3),  # 한글 음절
    (0x1100, 0x11FF),  # 한글 자모
    (0x3130, 0x318F),  # 한글 호환 자모
    (0x3000, 0x303F),  # CJK 기호 및 문장 부호
    (0xFF00, 0xFFEF),  # 반각 및 전각 형태
]


def is_valid_char(c: str) -> bool:
    """문자가 유효한 범위인지 확인"""
    code = ord(c)
    for start, end in VALID_CHAR_RANGES:
        if start <= code <= end:
            return True
    return False


def clean_hwp_text(text: str) -> str:
    """HWP 텍스트에서 노이즈 문자 제거 및 정제

    Args:
        text: 추출된 원본 텍스트

    Returns:
        정제된 텍스트
    """
    if not text:
        return ""

    # 노이즈 문자 집합 제거
    for noise_char in NOISE_CHARS:
        text = text.replace(noise_char, '')

    # 유효하지 않은 문자 필터링 (한글, 영어, 숫자, 기본 문장부호만 유지)
    cleaned_chars = []
    for c in text:
        if is_valid_char(c) or c in '\n\r\t':
            cleaned_chars.append(c)
        # 일부 유효하지 않은 문자는 공백으로 대체
        elif ord(c) >= 32:
            # 스킵하지 않고 일단 유지 (너무 많이 제거하면 정보 손실)
            cleaned_chars.append(c)

    result = ''.join(cleaned_chars)

    # 연속 공백 정리
    result = re.sub(r'[ \t]+', ' ', result)
    # 연속 줄바꿈 정리 (3개 이상 → 2개)
    result = re.sub(r'\n{3,}', '\n\n', result)
    # 앞뒤 공백 제거
    result = result.strip()

    return result


class IHWPParsingStrategy(ABC):
    """Interface for HWP parsing strategies."""
    
    @abstractmethod
    def parse(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Parse HWP file and return extracted content."""
        pass
    
    @abstractmethod
    def can_parse(self, file_path: str) -> bool:
        """Check if this strategy can parse the given file."""
        pass


class HWP5PythonAPIStrategy(IHWPParsingStrategy):
    """Strategy using hwp5 Python API for full text extraction."""
    
    def can_parse(self, file_path: str) -> bool:
        """Check if hwp5 library is available and file is valid."""
        try:
            import hwp5
            return os.path.exists(file_path) and file_path.lower().endswith('.hwp')
        except ImportError:
            return False
    
    def parse(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Parse using hwp5 Python API."""
        try:
            import hwp5
            from hwp5.dataio import ParseError
            from hwp5.xmlmodel import Hwp5File
            
            logger.info("Parsing with HWP5 Python API", file=file_path)
            
            result = {
                "text": "",
                "paragraphs": [],
                "tables": [],
                "metadata": {},
                "parsing_method": "hwp5_python_api"
            }
            
            # Open HWP file
            with hwp5.dataio.open_storage_or_stream(file_path) as hwp:
                # Extract metadata
                if hasattr(hwp, 'header'):
                    result["metadata"] = self._extract_metadata(hwp.header)
                
                # Extract text from all sections
                all_text = []
                all_paragraphs = []
                
                # Get bodytext sections
                for section_name in hwp.list_streams():
                    if section_name.startswith('BodyText/Section'):
                        section_data = hwp.open_stream(section_name)
                        text, paragraphs = self._extract_section_text(section_data)
                        all_text.append(text)
                        all_paragraphs.extend(paragraphs)
                
                result["text"] = "\n\n".join(all_text)
                result["paragraphs"] = all_paragraphs
                
                logger.info("Successfully parsed with HWP5 API", 
                          text_length=len(result["text"]))
                return result
                
        except Exception as e:
            logger.warning(f"HWP5 Python API strategy failed: {e}")
            return None
    
    def _extract_metadata(self, header) -> Dict[str, Any]:
        """Extract metadata from HWP header."""
        metadata = {}
        try:
            if hasattr(header, 'summary'):
                metadata['title'] = getattr(header.summary, 'title', '')
                metadata['author'] = getattr(header.summary, 'author', '')
                metadata['subject'] = getattr(header.summary, 'subject', '')
                metadata['keywords'] = getattr(header.summary, 'keywords', '')
        except:
            pass
        return metadata
    
    def _extract_section_text(self, section_data) -> tuple:
        """Extract text from a section stream."""
        text_parts = []
        paragraphs = []
        
        try:
            # Read and decompress section data
            compressed_data = section_data.read()
            
            # HWP5 sections are zlib compressed
            try:
                decompressed = zlib.decompress(compressed_data, -15)
            except:
                # Try with different window bits
                try:
                    decompressed = zlib.decompress(compressed_data)
                except:
                    return "", []
            
            # Parse records from decompressed data
            offset = 0
            while offset < len(decompressed):
                if offset + 4 > len(decompressed):
                    break
                    
                # Read record header (4 bytes)
                record_header = struct.unpack_from('<I', decompressed, offset)[0]
                tag_id = record_header & 0x3FF
                level = (record_header >> 10) & 0x3FF
                size = (record_header >> 20) & 0xFFF
                
                if size == 0xFFF:
                    # Extended size
                    if offset + 8 > len(decompressed):
                        break
                    size = struct.unpack_from('<I', decompressed, offset + 4)[0]
                    data_offset = offset + 8
                else:
                    data_offset = offset + 4
                
                # HWPTAG_PARA_TEXT = 0x42
                if tag_id == 0x42:
                    # Extract text from paragraph
                    if data_offset + size <= len(decompressed):
                        text_data = decompressed[data_offset:data_offset + size]
                        text = self._decode_text(text_data)
                        if text:
                            text_parts.append(text)
                            paragraphs.append({"text": text, "level": level})
                
                offset = data_offset + size
                
        except Exception as e:
            logger.debug(f"Error extracting section text: {e}")
        
        return "\n".join(text_parts), paragraphs
    
    def _decode_text(self, data: bytes) -> str:
        """Decode text data from HWP format."""
        try:
            # HWP uses UTF-16LE for text
            text = data.decode('utf-16le', errors='ignore')
            # Remove control characters
            text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\r\t')
            return text.strip()
        except:
            return ""


class HWP5CLIStrategy(IHWPParsingStrategy):
    """Strategy using hwp5txt command-line tool."""
    
    def can_parse(self, file_path: str) -> bool:
        """Check if hwp5txt command is available."""
        try:
            result = subprocess.run(['which', 'hwp5txt'], 
                                  capture_output=True, timeout=2)
            return result.returncode == 0
        except:
            return False
    
    def parse(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Parse using hwp5txt CLI tool."""
        try:
            logger.info("Parsing with hwp5txt CLI", file=file_path)
            
            # Run hwp5txt command
            cmd = ['hwp5txt', file_path]
            result = subprocess.run(cmd, capture_output=True, text=True, 
                                  timeout=30, encoding='utf-8')
            
            if result.returncode == 0 and result.stdout:
                text = result.stdout
                
                # Split into paragraphs
                paragraphs = [
                    {"text": para.strip()} 
                    for para in text.split('\n\n') 
                    if para.strip()
                ]
                
                return {
                    "text": text,
                    "paragraphs": paragraphs,
                    "tables": [],
                    "metadata": {},
                    "parsing_method": "hwp5txt_cli"
                }
            
            logger.warning("hwp5txt CLI returned no output")
            return None
            
        except subprocess.TimeoutExpired:
            logger.warning("hwp5txt CLI timeout")
            return None
        except Exception as e:
            logger.warning(f"hwp5txt CLI strategy failed: {e}")
            return None


class BodyTextDirectParser(IHWPParsingStrategy):
    """Strategy for direct BodyText stream parsing."""
    
    def can_parse(self, file_path: str) -> bool:
        """Check if file can be opened with olefile."""
        try:
            return olefile.isOleFile(file_path)
        except:
            return False
    
    def parse(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Parse BodyText streams directly."""
        try:
            logger.info("Parsing BodyText directly", file=file_path)
            
            with olefile.OleFileIO(file_path) as ole:
                result = {
                    "text": "",
                    "paragraphs": [],
                    "tables": [],
                    "metadata": self._extract_metadata(ole),
                    "parsing_method": "bodytext_direct"
                }
                
                all_text = []
                all_paragraphs = []
                
                # Find all BodyText sections
                for entry in ole.listdir():
                    if len(entry) == 2 and entry[0] == 'BodyText':
                        section_name = '/'.join(entry)
                        try:
                            stream = ole.openstream(entry)
                            text, paragraphs = self._parse_bodytext_stream(stream.read())
                            if text:
                                all_text.append(text)
                                all_paragraphs.extend(paragraphs)
                        except Exception as e:
                            logger.debug(f"Error parsing {section_name}: {e}")
                
                result["text"] = "\n\n".join(all_text)
                result["paragraphs"] = all_paragraphs
                
                if result["text"]:
                    logger.info("Successfully parsed BodyText", 
                              text_length=len(result["text"]))
                    return result
                
            return None
            
        except Exception as e:
            logger.warning(f"BodyText direct parser failed: {e}")
            return None
    
    def _extract_metadata(self, ole) -> Dict[str, Any]:
        """Extract metadata from OLE file."""
        metadata = {}
        try:
            if ole.exists('\x05HwpSummaryInformation'):
                summary = ole.getproperties('\x05HwpSummaryInformation')
                metadata['title'] = summary.get(2, '')
                metadata['subject'] = summary.get(3, '')
                metadata['author'] = summary.get(4, '')
                metadata['keywords'] = summary.get(5, '')
        except:
            pass
        return metadata
    
    def _parse_bodytext_stream(self, data: bytes) -> tuple:
        """Parse a BodyText stream."""
        text_parts = []
        paragraphs = []
        
        try:
            # Try to decompress
            try:
                decompressed = zlib.decompress(data, -15)
            except:
                try:
                    decompressed = zlib.decompress(data)
                except:
                    # Not compressed or different format
                    decompressed = data
            
            # Extract text using pattern matching
            # Look for Unicode text patterns
            text_chunks = []
            i = 0
            while i < len(decompressed) - 1:
                # Look for potential UTF-16LE text
                if i + 1 < len(decompressed):
                    char = decompressed[i:i+2]
                    try:
                        decoded = char.decode('utf-16le', errors='ignore')
                        if decoded and ord(decoded) >= 32:
                            # Start of text block
                            text_block = bytearray()
                            while i < len(decompressed) - 1:
                                text_block.extend(decompressed[i:i+2])
                                i += 2
                                # Check for end of text
                                if i < len(decompressed) - 1:
                                    next_char = decompressed[i:i+2]
                                    try:
                                        next_decoded = next_char.decode('utf-16le', errors='ignore')
                                        if not next_decoded or ord(next_decoded) < 32:
                                            break
                                    except:
                                        break
                            
                            text = text_block.decode('utf-16le', errors='ignore').strip()
                            if text and len(text) > 2:
                                text_chunks.append(text)
                    except:
                        pass
                i += 2
            
            # Combine text chunks
            if text_chunks:
                full_text = ' '.join(text_chunks)
                # Clean up text
                full_text = ''.join(char for char in full_text 
                                  if ord(char) >= 32 or char in '\n\r\t')
                
                text_parts = [full_text]
                paragraphs = [{"text": para.strip()} 
                            for para in full_text.split('\n') 
                            if para.strip()]
            
        except Exception as e:
            logger.debug(f"Error parsing BodyText stream: {e}")
        
        return "\n".join(text_parts), paragraphs


class EnhancedPrvTextStrategy(IHWPParsingStrategy):
    """Enhanced PrvText extraction with better handling."""
    
    def can_parse(self, file_path: str) -> bool:
        """Always returns True as last resort."""
        return os.path.exists(file_path)
    
    def parse(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Parse using enhanced PrvText extraction."""
        try:
            logger.info("Using enhanced PrvText extraction", file=file_path)
            
            # Try multiple methods to extract PrvText
            text = self._extract_with_hwp5proc(file_path)
            
            if not text:
                text = self._extract_with_olefile(file_path)
            
            if text:
                paragraphs = [
                    {"text": para.strip()} 
                    for para in text.split('\n\n') 
                    if para.strip()
                ]
                
                return {
                    "text": text,
                    "paragraphs": paragraphs,
                    "tables": [],
                    "metadata": {},
                    "parsing_method": "prvtext_enhanced"
                }
            
            return None
            
        except Exception as e:
            logger.warning(f"Enhanced PrvText strategy failed: {e}")
            return None
    
    def _extract_with_hwp5proc(self, file_path: str) -> Optional[str]:
        """Extract using hwp5proc command."""
        try:
            cmd = ["hwp5proc", "cat", "--vstreams", file_path, "PrvText.utf8"]
            result = subprocess.run(cmd, capture_output=True, text=True, 
                                  timeout=30, encoding='utf-8')
            if result.returncode == 0 and result.stdout:
                return result.stdout
        except:
            pass
        return None
    
    def _extract_with_olefile(self, file_path: str) -> Optional[str]:
        """Extract PrvText using olefile."""
        try:
            with olefile.OleFileIO(file_path) as ole:
                if ole.exists('PrvText'):
                    stream = ole.openstream('PrvText')
                    data = stream.read()
                    # Try various encodings
                    for encoding in ['utf-16le', 'utf-8', 'cp949', 'euc-kr']:
                        try:
                            text = data.decode(encoding, errors='ignore')
                            if text and len(text) > 100:
                                return text
                        except:
                            continue
        except:
            pass
        return None


class EnhancedHWPParser:
    """Enhanced HWP parser with multiple strategies and fallback mechanisms."""
    
    def __init__(self):
        """Initialize parser with all available strategies."""
        # Order strategies by effectiveness and completeness
        self.strategies = [
            BodyTextDirectParser(),      # Most complete extraction (8000+ chars)
            HWP5CLIStrategy(),           # Good fallback with hwp5txt
            HWP5PythonAPIStrategy(),     # When properly configured
            EnhancedPrvTextStrategy()    # Last resort (only ~1000 chars)
        ]
        logger.info("EnhancedHWPParser initialized", 
                   strategy_count=len(self.strategies))
    
    def parse(self, file_path: str) -> Dict[str, Any]:
        """
        Parse HWP file using available strategies in order.

        v2.0: 텍스트 정제 파이프라인 추가

        Args:
            file_path: Path to HWP file

        Returns:
            Dict containing extracted content
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        errors = []

        # Try each strategy in order
        for strategy in self.strategies:
            try:
                if strategy.can_parse(file_path):
                    logger.info(f"Trying {strategy.__class__.__name__}",
                              file=file_path)
                    result = strategy.parse(file_path)
                    if result and result.get("text"):
                        text = result.get("text", "")
                        text_length = len(text)

                        # For AI analysis, prioritize text volume over quality
                        # Accept any result with substantial text (>500 chars)
                        if text_length > 500:
                            # v2.0: 텍스트 정제 적용
                            cleaned_text = clean_hwp_text(text)
                            result["text"] = cleaned_text
                            result["original_length"] = text_length
                            result["cleaned_length"] = len(cleaned_text)

                            # 단락도 정제
                            if result.get("paragraphs"):
                                result["paragraphs"] = [
                                    {"text": clean_hwp_text(p.get("text", "")), **{k: v for k, v in p.items() if k != "text"}}
                                    if isinstance(p, dict) else {"text": clean_hwp_text(str(p))}
                                    for p in result["paragraphs"]
                                ]

                            logger.info(f"Successfully parsed with {strategy.__class__.__name__}",
                                      original_length=text_length,
                                      cleaned_length=len(cleaned_text),
                                      method=result.get("parsing_method"))
                            return result
                        else:
                            logger.warning(f"{strategy.__class__.__name__} produced insufficient text ({text_length} chars), trying next strategy")
            except Exception as e:
                error_msg = f"{strategy.__class__.__name__} failed: {str(e)}"
                errors.append(error_msg)
                logger.warning(error_msg)

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
    
    def _is_valid_result(self, text: str) -> bool:
        """
        Check if extracted text is valid and not garbled.
        
        Args:
            text: Extracted text to validate
            
        Returns:
            True if text seems valid, False otherwise
        """
        if not text or len(text) < 10:
            return False
        
        # Count character types
        korean_chars = sum(1 for c in text if '가' <= c <= '힣')
        english_chars = sum(1 for c in text if ('a' <= c <= 'z') or ('A' <= c <= 'Z'))
        digit_chars = sum(1 for c in text if '0' <= c <= '9')
        space_chars = sum(1 for c in text if c in ' \n\r\t')
        
        # Valid characters (Korean, English, digits, spaces, common punctuation)
        valid_chars = korean_chars + english_chars + digit_chars + space_chars
        valid_chars += sum(1 for c in text if c in '.,!?()-[]{}:;"\'/+-=@#$%^&*_~`')
        
        total_chars = len(text)
        valid_ratio = valid_chars / total_chars if total_chars > 0 else 0
        
        # Check for common garbled patterns
        garbled_patterns = ['ࡂ', 'ृ', 'ƀ', 'ą', '褀', '褅', '耈', '蠂']
        garbled_count = sum(text.count(pattern) for pattern in garbled_patterns)
        garbled_ratio = garbled_count / total_chars if total_chars > 0 else 0
        
        # Text is valid if:
        # 1. Has reasonable amount of valid characters (>50%)
        # 2. Not too much garbled text (<10%)
        # 3. Has some Korean or English content
        is_valid = (valid_ratio > 0.5 and 
                   garbled_ratio < 0.1 and 
                   (korean_chars > 10 or english_chars > 20))
        
        if not is_valid:
            logger.debug(f"Text validation failed - valid: {valid_ratio:.2%}, "
                        f"garbled: {garbled_ratio:.2%}, "
                        f"korean: {korean_chars}, english: {english_chars}")
        
        return is_valid
    
    def extract_text(self, file_path: str) -> str:
        """
        Extract plain text from HWP file.
        
        Args:
            file_path: Path to HWP file
            
        Returns:
            Extracted text as string
        """
        result = self.parse(file_path)
        return result.get("text", "")


# Export parser instance
enhanced_parser = EnhancedHWPParser()