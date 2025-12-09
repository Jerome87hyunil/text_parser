"""
Enhanced HWP Parser with complete text extraction capabilities.
Implements multiple parsing strategies with fallback mechanisms.

v2.0: 노이즈 문자 제거, 텍스트 정제 파이프라인 강화
v3.0: HWP 레코드 파싱 완전 재작성 - HWPTAG_PARA_TEXT(0x42)에서만 텍스트 추출
      바이너리 노이즈(CJK, Cyrillic 등) 완전 제거
v3.1: ASCII 반복 패턴 노이즈 제거 (LLLLLL, KKKKKK 등)
v3.2: 스마트 폴백 - BodyText 한글 비율 낮으면 PrvText로 자동 전환
      특정 HWP 파일에서 PARA_TEXT 추출 실패 시 PrvText 우선 사용
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

# HWP 레코드 태그 ID (HWP 5.0 스펙)
HWPTAG_PARA_TEXT = 0x42  # 문단 텍스트 레코드

# 텍스트에서 허용할 유니코드 범위 (엄격한 필터)
ALLOWED_UNICODE_RANGES = [
    (0x0020, 0x007E),   # ASCII 기본 (공백, 알파벳, 숫자, 구두점)
    (0x00A0, 0x00FF),   # Latin-1 Supplement (©, ®, ° 등)
    (0x2000, 0x206F),   # General Punctuation (…, –, — 등)
    (0x2190, 0x21FF),   # Arrows (→, ← 등)
    (0x2200, 0x22FF),   # Mathematical Operators
    (0x2460, 0x24FF),   # Enclosed Alphanumerics (①, ② 등)
    (0x3000, 0x303F),   # CJK Symbols and Punctuation
    (0x3130, 0x318F),   # Hangul Compatibility Jamo
    (0xAC00, 0xD7A3),   # Hangul Syllables (가-힣)
    (0xFF01, 0xFF5E),   # Fullwidth ASCII
]

# 바이너리 노이즈 패턴 (HWP 레코드 헤더/포맷팅 데이터)
BINARY_NOISE_PATTERNS = [
    r'[䀀-俿]',         # CJK Extension B (HWP 바이너리 마커)
    r'[耀-耿]',         # CJK Unified (HWP 레코드)
    r'[蠀-蠿]',         # CJK Unified (HWP 레코드)
    r'[褀-褿]',         # CJK Unified (HWP 포맷)
    r'[\u0400-\u04FF]', # Cyrillic (HWP 바이너리)
    r'[\u0100-\u017F]', # Latin Extended-A (노이즈)
    r'[\u0180-\u024F]', # Latin Extended-B (노이즈)
    r'[\u0840-\u085F]', # Mandaic (HWP 노이즈)
    r'[\u0900-\u097F]', # Devanagari (HWP 노이즈)
    r'[\ue000-\uf8ff]', # Private Use Area
    r'[\u0000-\u001f]', # Control characters
    r'[\u007f-\u009f]', # Control characters
    r'[\ufff0-\uffff]', # Specials
    r'[贀-贿]+',        # 연속된 CJK 노이즈
    r'[谀-谿]+',        # 연속된 CJK 노이즈
    r'[捀-捿]+',        # CJK (HWP 레코드 헤더)
    r'[勀-勿]+',        # CJK 노이즈
]

# ASCII 반복 패턴 노이즈 (이미지/바이너리 데이터)
ASCII_REPEAT_PATTERNS = [
    r'(.)\1{3,}',                    # 같은 문자 4회 이상 반복 (LLLL)
    r'[A-Z]{8,}',                    # 대문자만 8개 이상 연속
    r'[a-z]{10,}',                   # 소문자만 10개 이상 연속
    r'[A-Za-z]{15,}',                # 알파벳만 15개 이상 연속
    r'[#$%&*+\-=<>?!@\'\"]{3,}',     # 기호 3개 이상 연속
    r'[0-9#$%&*+\-=]{10,}',          # 숫자/기호 혼합 10자 이상
    r'[\(\)\[\]\{\}]{3,}',           # 괄호 3개 이상 연속
    r'[,\.]{3,}',                    # 쉼표/마침표 3개 이상 연속
    r'[A-Za-z0-9#$%&*+\-=<>?!@\'"(){}\[\],\.;:]{30,}',  # 한글 없이 30자 이상 연속
]

# 컴파일된 노이즈 패턴
COMPILED_NOISE_PATTERNS = [re.compile(p) for p in BINARY_NOISE_PATTERNS]
COMPILED_ASCII_PATTERNS = [re.compile(p) for p in ASCII_REPEAT_PATTERNS]


def remove_ascii_noise(text: str) -> str:
    """ASCII 반복 패턴 노이즈 제거

    v3.1: 이미지/바이너리 데이터에서 발생하는 ASCII 반복 패턴 제거
    예: LLLLLLLLL, KKKKKKKK, ##$$%%&& 등

    Args:
        text: 정제할 텍스트

    Returns:
        ASCII 노이즈가 제거된 텍스트
    """
    if not text:
        return ""

    # ASCII 반복 패턴 제거
    for pattern in COMPILED_ASCII_PATTERNS:
        text = pattern.sub('', text)

    return text


def split_and_clean_chunks(text: str) -> str:
    """긴 텍스트를 청크로 분할하고 노이즈 청크 제거

    공백이 없는 긴 문자열에서 한글과 노이즈가 섞인 경우를 처리합니다.

    Args:
        text: 정제할 텍스트

    Returns:
        정제된 텍스트
    """
    if not text:
        return ""

    # 한글 문자를 기준으로 청크 분할
    result_parts = []
    current_chunk = []
    prev_korean = False

    for c in text:
        is_korean = is_valid_korean_char(c)

        # 한글과 비한글 경계에서 분할
        if is_korean != prev_korean and current_chunk:
            chunk = ''.join(current_chunk)
            if prev_korean:
                # 한글 청크는 유지
                result_parts.append(chunk)
            else:
                # 비한글 청크는 짧은 것만 유지 (10자 이하)
                if len(chunk) <= 10:
                    result_parts.append(chunk)
            current_chunk = []

        current_chunk.append(c)
        prev_korean = is_korean

    # 마지막 청크 처리
    if current_chunk:
        chunk = ''.join(current_chunk)
        if prev_korean:
            result_parts.append(chunk)
        elif len(chunk) <= 10:
            result_parts.append(chunk)

    return ''.join(result_parts)


def is_meaningful_token(token: str) -> bool:
    """토큰이 의미 있는 텍스트인지 확인

    v3.1: 더 공격적인 노이즈 필터링

    Args:
        token: 검사할 토큰

    Returns:
        의미 있으면 True, 노이즈면 False
    """
    if not token:
        return False

    # 한글이 포함되어 있으면 유의미
    korean_count = sum(1 for c in token if is_valid_korean_char(c))
    if korean_count > 0:
        # 한글 비율이 너무 낮으면 (10% 미만) 노이즈 가능성
        if len(token) > 10 and korean_count / len(token) < 0.1:
            return False
        return True

    # 한글 없는 토큰 검증 (더 엄격)

    # 토큰 길이가 너무 길면 (10자 초과) 노이즈 가능성
    if len(token) > 10:
        return False

    # 반복 문자 비율 체크
    if len(token) > 4:
        unique_chars = len(set(token))
        repeat_ratio = 1 - (unique_chars / len(token))
        # 반복 비율이 50% 이상이면 노이즈
        if repeat_ratio > 0.5:
            return False

    # 숫자만 포함 (날짜, 전화번호 등) - 허용
    if token.isdigit():
        return True

    # 짧은 영숫자 (10자 이하) - 허용
    stripped = token.replace('.', '').replace(',', '').replace('-', '').replace(':', '').replace('/', '')
    if stripped.isalnum() and len(stripped) <= 10:
        return True

    # 특수 기호만으로 구성된 토큰 - 2자 이하만 허용
    if all(c in '#$%&*+=-<>?!@\'\"()[]{}.,;:' for c in token):
        return len(token) <= 2

    return False


def is_garbage_chunk(text: str, min_korean_ratio: float = 0.05) -> bool:
    """텍스트 청크가 전체적으로 노이즈인지 확인

    Args:
        text: 검사할 텍스트 청크
        min_korean_ratio: 최소 한글 비율 (기본 5%)

    Returns:
        노이즈면 True, 유의미하면 False
    """
    if not text or len(text) < 10:
        return True

    # 한글 비율 계산
    korean_count = sum(1 for c in text if is_valid_korean_char(c))
    non_space = sum(1 for c in text if not c.isspace())

    if non_space == 0:
        return True

    korean_ratio = korean_count / non_space

    # 한글 비율이 최소 기준 미만이면 노이즈
    if korean_ratio < min_korean_ratio:
        return True

    return False


def is_valid_korean_char(c: str) -> bool:
    """한글 문자인지 확인"""
    code = ord(c)
    # 한글 음절 (가-힣)
    if 0xAC00 <= code <= 0xD7A3:
        return True
    # 한글 자모
    if 0x3130 <= code <= 0x318F:
        return True
    return False


def is_allowed_char(c: str) -> bool:
    """허용된 문자 범위인지 확인 (엄격)"""
    code = ord(c)
    for start, end in ALLOWED_UNICODE_RANGES:
        if start <= code <= end:
            return True
    # 탭, 줄바꿈 허용
    if c in '\n\r\t':
        return True
    return False


def calculate_korean_ratio(text: str) -> float:
    """텍스트 내 한글 비율 계산"""
    if not text:
        return 0.0
    korean_count = sum(1 for c in text if is_valid_korean_char(c))
    # 공백 제외한 문자 수
    non_space = sum(1 for c in text if not c.isspace())
    if non_space == 0:
        return 0.0
    return korean_count / non_space


def clean_hwp_text(text: str) -> str:
    """HWP 텍스트 공격적 정제 (바이너리 노이즈 완전 제거)

    v3.0: 바이너리 패턴 기반 노이즈 제거로 완전히 재작성
    v3.1: ASCII 반복 패턴 노이즈 제거 추가 (LLLLLL, KKKKKK 등)

    Args:
        text: 추출된 원본 텍스트

    Returns:
        정제된 텍스트 (한글/영문/숫자/기본구두점만 포함)
    """
    if not text:
        return ""

    # 1단계: 바이너리 노이즈 패턴 제거 (CJK, Cyrillic 등)
    for pattern in COMPILED_NOISE_PATTERNS:
        text = pattern.sub('', text)

    # 1.5단계: ASCII 반복 패턴 노이즈 제거 (LLLLL, KKKKK 등)
    text = remove_ascii_noise(text)

    # 1.7단계: 한글/비한글 청크 분할 및 긴 비한글 청크 제거
    text = split_and_clean_chunks(text)

    # 2단계: 허용된 문자만 유지 (매우 엄격)
    cleaned_chars = []
    for c in text:
        if is_allowed_char(c):
            cleaned_chars.append(c)
        elif c.isspace():
            cleaned_chars.append(' ')
        # 그 외 문자는 무시

    result = ''.join(cleaned_chars)

    # 3단계: 의미 없는 토큰 제거 (is_meaningful_token 사용)
    tokens = result.split()
    cleaned_tokens = []
    for token in tokens:
        if is_meaningful_token(token):
            cleaned_tokens.append(token)
        elif token in ['○', '●', '◎', '△', '▲', '□', '■', '※', '☎', '→', '←', '↔', '⇒']:
            cleaned_tokens.append(token)
        # 무의미한 토큰은 무시

    result = ' '.join(cleaned_tokens)

    # 3.5단계: 노이즈 청크 검증 (한글 비율 5% 미만이면 폐기)
    if is_garbage_chunk(result, min_korean_ratio=0.05):
        return ""

    # 4단계: 공백 정리
    result = re.sub(r'[ \t]+', ' ', result)
    result = re.sub(r'\n[ \t]+', '\n', result)
    result = re.sub(r'[ \t]+\n', '\n', result)
    result = re.sub(r'\n{3,}', '\n\n', result)

    return result.strip()


def extract_clean_text_from_hwp_data(data: bytes) -> str:
    """HWP 레코드에서 순수 텍스트만 추출

    HWP 5.0 레코드 구조를 파싱하여 HWPTAG_PARA_TEXT(0x42) 레코드에서만
    텍스트를 추출합니다.

    Args:
        data: 압축 해제된 BodyText 스트림 데이터

    Returns:
        추출된 순수 텍스트
    """
    text_parts = []
    offset = 0

    while offset < len(data) - 4:
        # 레코드 헤더 읽기 (4바이트)
        try:
            record_header = struct.unpack_from('<I', data, offset)[0]
        except struct.error:
            break

        tag_id = record_header & 0x3FF        # bits 0-9
        level = (record_header >> 10) & 0x3FF  # bits 10-19
        size = (record_header >> 20) & 0xFFF   # bits 20-31

        # 확장 크기 처리
        if size == 0xFFF:
            if offset + 8 > len(data):
                break
            size = struct.unpack_from('<I', data, offset + 4)[0]
            data_offset = offset + 8
        else:
            data_offset = offset + 4

        # 데이터 범위 확인
        if data_offset + size > len(data):
            break

        # HWPTAG_PARA_TEXT (0x42 = 66) 레코드에서만 텍스트 추출
        if tag_id == HWPTAG_PARA_TEXT:
            record_data = data[data_offset:data_offset + size]
            text = _decode_para_text(record_data)
            if text:
                text_parts.append(text)

        # 다음 레코드로 이동
        offset = data_offset + size

    return '\n'.join(text_parts)


def _decode_para_text(data: bytes) -> str:
    """HWP 문단 텍스트 레코드 디코딩

    HWP 문단 텍스트는 UTF-16LE로 인코딩되어 있으며,
    특수 제어 문자(0x00-0x1F)가 포함될 수 있습니다.

    Args:
        data: HWPTAG_PARA_TEXT 레코드 데이터

    Returns:
        디코딩된 텍스트
    """
    if len(data) < 2:
        return ""

    try:
        # UTF-16LE 디코딩
        text = data.decode('utf-16le', errors='ignore')
    except:
        return ""

    # HWP 특수 제어 문자 처리
    cleaned = []
    i = 0
    while i < len(text):
        c = text[i]
        code = ord(c)

        # HWP 제어 문자 (0x00-0x1F)
        if code < 0x20:
            if code == 0x0A:  # 줄바꿈
                cleaned.append('\n')
            elif code == 0x0D:  # 캐리지 리턴
                pass  # 무시
            elif code == 0x09:  # 탭
                cleaned.append(' ')
            # 기타 제어 문자는 무시 (필드 시작, 그림 등)
            i += 1
            continue

        # 일반 텍스트
        if is_allowed_char(c):
            cleaned.append(c)

        i += 1

    return ''.join(cleaned).strip()


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
        """Extract text from a section stream using proper HWP record parsing.

        v3.0: HWP 레코드 구조를 정확히 파싱하여 노이즈 없는 텍스트 추출
        """
        text_parts = []
        paragraphs = []

        try:
            # Read and decompress section data
            compressed_data = section_data.read()

            # HWP5 sections are zlib compressed
            try:
                decompressed = zlib.decompress(compressed_data, -15)
            except:
                try:
                    decompressed = zlib.decompress(compressed_data)
                except:
                    return "", []

            # HWP 레코드 파싱 함수 사용 (HWPTAG_PARA_TEXT만 추출)
            extracted_text = extract_clean_text_from_hwp_data(decompressed)

            if extracted_text:
                # 추가 텍스트 정제
                cleaned_text = clean_hwp_text(extracted_text)

                if cleaned_text:
                    text_parts = [cleaned_text]
                    paragraphs = [{"text": para.strip()}
                                for para in cleaned_text.split('\n')
                                if para.strip()]

        except Exception as e:
            logger.debug(f"Error extracting section text: {e}")

        return "\n".join(text_parts), paragraphs

    def _decode_text(self, data: bytes) -> str:
        """Decode text data from HWP format (레거시 메서드, _decode_para_text 권장)."""
        return _decode_para_text(data)


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
        """Parse a BodyText stream using proper HWP record parsing.

        v3.0: HWP 레코드 구조를 정확히 파싱하여 HWPTAG_PARA_TEXT(0x42)
        레코드에서만 텍스트를 추출합니다. 바이너리 노이즈가 완전히 제거됩니다.
        """
        text_parts = []
        paragraphs = []

        try:
            # 1단계: 압축 해제
            try:
                decompressed = zlib.decompress(data, -15)
            except:
                try:
                    decompressed = zlib.decompress(data)
                except:
                    # 압축되지 않은 데이터
                    decompressed = data

            # 2단계: HWP 레코드 파싱 (HWPTAG_PARA_TEXT만 추출)
            # 이 함수는 바이너리 노이즈 없이 순수 텍스트만 추출합니다
            extracted_text = extract_clean_text_from_hwp_data(decompressed)

            if extracted_text:
                # 3단계: 추가 텍스트 정제
                cleaned_text = clean_hwp_text(extracted_text)

                if cleaned_text:
                    text_parts = [cleaned_text]
                    paragraphs = [{"text": para.strip()}
                                for para in cleaned_text.split('\n')
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

    # v3.2: 스마트 폴백을 위한 최소 한글 비율 임계값
    MIN_KOREAN_RATIO_FOR_BODYTEXT = 0.10  # 10% 미만이면 PrvText로 폴백

    def __init__(self):
        """Initialize parser with all available strategies."""
        # Order strategies by effectiveness and completeness
        self.strategies = [
            BodyTextDirectParser(),      # Most complete extraction (8000+ chars)
            HWP5CLIStrategy(),           # Good fallback with hwp5txt
            HWP5PythonAPIStrategy(),     # When properly configured
            EnhancedPrvTextStrategy()    # Last resort (only ~1000 chars)
        ]
        # PrvText 전용 전략 (스마트 폴백용)
        self.prvtext_strategy = EnhancedPrvTextStrategy()
        logger.info("EnhancedHWPParser initialized",
                   strategy_count=len(self.strategies))
    
    def parse(self, file_path: str) -> Dict[str, Any]:
        """
        Parse HWP file using available strategies in order.

        v2.0: 텍스트 정제 파이프라인 추가
        v3.2: 스마트 폴백 - BodyText 한글 비율 검증 후 PrvText 우선 사용

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

                            # v3.2: 스마트 폴백 - 한글 비율 검증
                            korean_ratio = calculate_korean_ratio(cleaned_text)

                            # BodyText 추출 결과가 한글 비율이 너무 낮으면 PrvText 시도
                            if (isinstance(strategy, BodyTextDirectParser) and
                                korean_ratio < self.MIN_KOREAN_RATIO_FOR_BODYTEXT):

                                logger.warning(
                                    f"BodyText Korean ratio too low ({korean_ratio:.1%}), "
                                    f"trying PrvText fallback",
                                    cleaned_length=len(cleaned_text)
                                )

                                # PrvText 추출 시도
                                prvtext_result = self._try_prvtext_fallback(file_path)
                                if prvtext_result:
                                    prvtext_korean_ratio = calculate_korean_ratio(
                                        prvtext_result.get("text", "")
                                    )

                                    # PrvText가 더 나은 한글 비율을 가지면 사용
                                    if prvtext_korean_ratio > korean_ratio:
                                        logger.info(
                                            f"Using PrvText fallback "
                                            f"(Korean ratio: {prvtext_korean_ratio:.1%} > {korean_ratio:.1%})",
                                            prvtext_length=len(prvtext_result.get("text", ""))
                                        )
                                        prvtext_result["parsing_method"] = "prvtext_smart_fallback"
                                        prvtext_result["bodytext_korean_ratio"] = korean_ratio
                                        prvtext_result["prvtext_korean_ratio"] = prvtext_korean_ratio
                                        return prvtext_result

                            # 정제된 텍스트가 비어있으면 다음 전략 시도
                            if not cleaned_text or len(cleaned_text) < 100:
                                logger.warning(
                                    f"{strategy.__class__.__name__} text cleaned to "
                                    f"insufficient length ({len(cleaned_text)} chars), "
                                    f"trying next strategy"
                                )
                                continue

                            result["text"] = cleaned_text
                            result["original_length"] = text_length
                            result["cleaned_length"] = len(cleaned_text)
                            result["korean_ratio"] = korean_ratio

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
                                      korean_ratio=f"{korean_ratio:.1%}",
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

    def _try_prvtext_fallback(self, file_path: str) -> Optional[Dict[str, Any]]:
        """PrvText 스마트 폴백 시도

        v3.2: BodyText 추출 실패 시 PrvText로 폴백

        Args:
            file_path: HWP 파일 경로

        Returns:
            PrvText 추출 결과 또는 None
        """
        try:
            if self.prvtext_strategy.can_parse(file_path):
                result = self.prvtext_strategy.parse(file_path)
                if result and result.get("text"):
                    text = result.get("text", "")
                    if len(text) > 100:
                        # 정제 적용
                        cleaned = clean_hwp_text(text)
                        if cleaned and len(cleaned) > 50:
                            result["text"] = cleaned
                            result["original_length"] = len(text)
                            result["cleaned_length"] = len(cleaned)
                            return result
        except Exception as e:
            logger.debug(f"PrvText fallback failed: {e}")
        return None
    
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