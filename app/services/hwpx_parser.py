"""
HWPX Parser implementation.
HWPX is the new XML-based format for HWP files.
개선된 버전: 정확한 네임스페이스 처리 및 텍스트 추출
v2.0: hp10 네임스페이스 지원, 텍스트 정제 개선, 테이블 추출 강화
"""
import structlog
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional, Set
import os
import re

logger = structlog.get_logger()


class HWPXParser:
    """Parser for HWPX (XML-based HWP) files."""

    # HWPX 네임스페이스 정의 (2011/2016 버전 모두 지원)
    NAMESPACES = {
        'hp': 'http://www.hancom.co.kr/hwpml/2011/paragraph',
        'hp10': 'http://www.hancom.co.kr/hwpml/2016/paragraph',
        'hs': 'http://www.hancom.co.kr/hwpml/2011/section',
        'hc': 'http://www.hancom.co.kr/hwpml/2011/core',
        'hh': 'http://www.hancom.co.kr/hwpml/2011/head',
        'ha': 'http://www.hancom.co.kr/hwpml/2011/app',
        'hm': 'http://www.hancom.co.kr/hwpml/2011/master-page',
        'hpf': 'http://www.hancom.co.kr/schema/2011/hpf',
        'dc': 'http://purl.org/dc/elements/1.1/',
    }

    # 텍스트를 추출할 네임스페이스 URI 목록
    TEXT_NS_URIS: Set[str] = {
        'http://www.hancom.co.kr/hwpml/2011/paragraph',
        'http://www.hancom.co.kr/hwpml/2016/paragraph',
    }

    def __init__(self):
        # ElementTree에서 네임스페이스 프리픽스 등록
        for prefix, uri in self.NAMESPACES.items():
            try:
                ET.register_namespace(prefix, uri)
            except ValueError:
                pass

    def parse(self, file_path: str) -> Dict[str, Any]:
        """
        Parse HWPX file and extract content.

        Args:
            file_path: Path to HWPX file

        Returns:
            Dict containing extracted content
        """
        result = {
            "paragraphs": [],
            "tables": [],
            "images": [],
            "metadata": {},
            "text": "",
            "structure": {
                "sections": [],
                "total_sections": 0
            }
        }

        try:
            logger.info("HWPX 파싱 시작", file_path=file_path)

            with zipfile.ZipFile(file_path, 'r') as zip_file:
                # 메타데이터 추출
                result["metadata"] = self._extract_metadata(zip_file)

                # Preview/PrvText.txt 먼저 시도 (빠른 추출)
                preview_text = self._extract_preview_text(zip_file)

                # 섹션에서 콘텐츠 추출
                sections_data = self._extract_sections(zip_file)

                all_texts = []
                all_paragraphs = []
                all_tables = []

                for section_idx, section_root in enumerate(sections_data):
                    section_info = {
                        "section_id": f"section{section_idx}",
                        "paragraph_count": 0,
                        "table_count": 0
                    }

                    # 텍스트 추출 (새로운 방식)
                    section_texts = self._extract_all_text_from_section(section_root)
                    all_texts.extend(section_texts)

                    # 단락 구조 추출
                    paragraphs = self._extract_paragraphs_from_section(section_root)
                    section_info["paragraph_count"] = len(paragraphs)
                    all_paragraphs.extend(paragraphs)

                    # 테이블 추출
                    tables = self._extract_tables_from_section(section_root)
                    section_info["table_count"] = len(tables)
                    all_tables.extend(tables)

                    result["structure"]["sections"].append(section_info)

                result["structure"]["total_sections"] = len(sections_data)
                result["paragraphs"] = all_paragraphs
                result["tables"] = all_tables

                # 텍스트 결합
                combined_text = '\n'.join(all_texts)

                # Preview 텍스트와 비교하여 더 나은 결과 선택
                if preview_text and len(preview_text) > len(combined_text):
                    logger.info("Preview 텍스트 사용",
                               preview_len=len(preview_text),
                               parsed_len=len(combined_text))
                    result["text"] = preview_text
                else:
                    result["text"] = combined_text

                logger.info("HWPX 파싱 완료",
                           text_length=len(result["text"]),
                           paragraph_count=len(all_paragraphs),
                           table_count=len(all_tables))

        except Exception as e:
            logger.error("HWPX 파싱 오류", error=str(e), file_path=file_path)
            raise

        return result

    def _extract_preview_text(self, zip_file: zipfile.ZipFile) -> str:
        """Preview/PrvText.txt에서 텍스트 추출 (한글에서 자동 생성하는 미리보기 텍스트)"""
        try:
            if 'Preview/PrvText.txt' in zip_file.namelist():
                with zip_file.open('Preview/PrvText.txt') as f:
                    content = f.read()
                    # UTF-8 또는 EUC-KR로 디코딩 시도
                    try:
                        text = content.decode('utf-8')
                    except UnicodeDecodeError:
                        text = content.decode('euc-kr', errors='ignore')
                    # 텍스트 정제
                    cleaned = self._clean_preview_text(text)
                    return cleaned
        except Exception as e:
            logger.debug("Preview 텍스트 추출 실패", error=str(e))
        return ""

    def _clean_preview_text(self, text: str) -> str:
        """Preview 텍스트 정제 (구분자 제거, 포맷 정리)

        v2.0: 더 정교한 <> 구분자 처리
        """
        if not text:
            return ""

        # <구분자> 형식 처리
        # 먼저 ><를 줄바꿈으로 변환
        cleaned = re.sub(r'>\s*<', '\n', text)

        # 남은 < 와 > 모두 제거
        cleaned = re.sub(r'[<>]', '', cleaned)

        # 연속 공백 정리
        cleaned = re.sub(r'[ \t]+', ' ', cleaned)

        # 각 줄 앞뒤 공백 제거
        lines = [line.strip() for line in cleaned.split('\n')]
        cleaned = '\n'.join(lines)

        # 연속 줄바꿈 정리 (3개 이상 → 2개)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)

        # 빈 줄 제거 (연속 줄바꿈만 제거하지 않고 빈 줄도 정리)
        cleaned = re.sub(r'\n\s*\n', '\n', cleaned)

        return cleaned.strip()

    def _extract_metadata(self, zip_file: zipfile.ZipFile) -> Dict[str, Any]:
        """Extract metadata from HWPX file."""
        metadata = {}

        try:
            # version.xml에서 버전 정보
            if 'version.xml' in zip_file.namelist():
                with zip_file.open('version.xml') as f:
                    content = f.read().decode('utf-8')
                    # 간단히 버전 정보 추출
                    version_match = re.search(r'version="([^"]*)"', content)
                    if version_match:
                        metadata['hwp_version'] = version_match.group(1)

            # Contents/header.xml에서 문서 정보
            if 'Contents/header.xml' in zip_file.namelist():
                with zip_file.open('Contents/header.xml') as f:
                    tree = ET.parse(f)
                    root = tree.getroot()
                    metadata['has_header'] = True

        except Exception as e:
            logger.warning("메타데이터 추출 실패", error=str(e))

        return metadata

    def _extract_sections(self, zip_file: zipfile.ZipFile) -> List[ET.Element]:
        """Extract all section data from HWPX."""
        sections = []

        try:
            # Contents 디렉토리에서 section 파일 찾기
            section_files = sorted([
                f for f in zip_file.namelist()
                if f.startswith('Contents/section') and f.endswith('.xml')
            ])

            logger.debug("섹션 파일 발견", count=len(section_files), files=section_files)

            for section_file in section_files:
                try:
                    with zip_file.open(section_file) as sf:
                        content = sf.read()
                        root = ET.fromstring(content)
                        sections.append(root)
                        logger.debug("섹션 파싱 성공", file=section_file)
                except ET.ParseError as e:
                    logger.warning("섹션 XML 파싱 오류", file=section_file, error=str(e))

        except Exception as e:
            logger.error("섹션 추출 실패", error=str(e))

        return sections

    def _extract_all_text_from_section(self, section_root: ET.Element) -> List[str]:
        """
        섹션에서 모든 텍스트 추출 (개선된 방식).

        HWPX 구조:
        - <hp:p> 또는 <hp10:p> (paragraph)
          - <hp:run> (text run)
            - <hp:t> (text content)
        - <hp:tbl> (table)
          - <hp:tr> (table row)
            - <hp:tc> (table cell)
              - <hp:subList>
                - <hp:p> (paragraph in cell)

        v2.0: hp10 네임스페이스 (2016) 지원 추가
        """
        texts = []

        # 모든 <hp:t> 또는 <hp10:t> (텍스트) 요소에서 직접 텍스트 추출
        for elem in section_root.iter():
            tag = elem.tag

            # 네임스페이스가 있는 경우 로컬 이름 추출
            if tag.startswith('{'):
                ns_end = tag.find('}')
                ns_uri = tag[1:ns_end]
                local_name = tag[ns_end + 1:]

                # hp 또는 hp10 네임스페이스의 't' 요소 (텍스트)
                if local_name == 't' and ns_uri in self.TEXT_NS_URIS:
                    if elem.text and elem.text.strip():
                        # 노이즈 문자 정제
                        cleaned = self._clean_text_content(elem.text.strip())
                        if cleaned:
                            texts.append(cleaned)

        return texts

    def _clean_text_content(self, text: str) -> str:
        """텍스트 콘텐츠 정제 (노이즈 문자 제거)"""
        if not text:
            return ""

        # 제어 문자 및 특수 노이즈 제거 (한글/영어/숫자/기본 문장부호 유지)
        # 특수 노이즈 패턴: ​ (ZWSP), ‌ (ZWNJ) 등
        cleaned = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', text)

        # 연속 공백 정리
        cleaned = re.sub(r'\s+', ' ', cleaned)

        return cleaned.strip()

    def _extract_paragraphs_from_section(self, section_root: ET.Element) -> List[Dict[str, Any]]:
        """Extract paragraphs from a section element (구조 보존).

        v2.0: hp10 네임스페이스 지원 추가
        """
        paragraphs = []

        # hp:p 또는 hp10:p 요소 찾기
        for elem in section_root.iter():
            tag = elem.tag

            if tag.startswith('{'):
                ns_end = tag.find('}')
                ns_uri = tag[1:ns_end]
                local_name = tag[ns_end + 1:]

                # hp 또는 hp10 네임스페이스의 'p' 요소 (paragraph)
                if local_name == 'p' and ns_uri in self.TEXT_NS_URIS:
                    para_text = self._extract_text_from_paragraph(elem)
                    if para_text.strip():
                        paragraphs.append({
                            "text": self._clean_text_content(para_text.strip()),
                            "style": self._extract_style_from_element(elem)
                        })

        return paragraphs

    def _extract_text_from_paragraph(self, para_elem: ET.Element) -> str:
        """단락 요소에서 텍스트 추출 (hp:run/hp:t 또는 hp10:run/hp10:t 구조 처리).

        v2.0: hp10 네임스페이스 지원 추가
        """
        texts = []

        for elem in para_elem.iter():
            tag = elem.tag

            if tag.startswith('{'):
                ns_end = tag.find('}')
                ns_uri = tag[1:ns_end]
                local_name = tag[ns_end + 1:]

                # hp:t 또는 hp10:t 요소의 텍스트 추출
                if local_name == 't' and ns_uri in self.TEXT_NS_URIS:
                    if elem.text:
                        texts.append(elem.text)

        return ''.join(texts)

    def _extract_tables_from_section(self, section_root: ET.Element) -> List[Dict[str, Any]]:
        """Extract tables from a section element.

        v2.0: hp10 네임스페이스 지원 추가
        """
        tables = []

        for elem in section_root.iter():
            tag = elem.tag

            if tag.startswith('{'):
                ns_end = tag.find('}')
                ns_uri = tag[1:ns_end]
                local_name = tag[ns_end + 1:]

                # hp:tbl 또는 hp10:tbl 요소 (table)
                if local_name == 'tbl' and ns_uri in self.TEXT_NS_URIS:
                    table_data = self._parse_table_element(elem)
                    if table_data:
                        tables.append(table_data)

        return tables

    def _extract_style_from_element(self, element: ET.Element) -> Dict[str, Any]:
        """Extract style information from an element."""
        style = {}

        try:
            # 속성에서 스타일 정보 추출
            if 'paraPrIDRef' in element.attrib:
                style['para_style_ref'] = element.attrib['paraPrIDRef']
            if 'styleIDRef' in element.attrib:
                style['style_ref'] = element.attrib['styleIDRef']
        except Exception as e:
            logger.debug("스타일 추출 실패", error=str(e))

        return style

    def _parse_table_element(self, table_elem: ET.Element) -> Optional[Dict[str, Any]]:
        """Parse a table element and extract its data.

        v2.0: hp10 네임스페이스 지원 추가
        """
        try:
            rows = []

            # hp:tr 또는 hp10:tr (table row) 요소 찾기
            for elem in table_elem.iter():
                tag = elem.tag

                if not tag.startswith('{'):
                    continue

                ns_end = tag.find('}')
                ns_uri = tag[1:ns_end]
                local_name = tag[ns_end + 1:]

                # hp:tr 또는 hp10:tr 요소 (table row)
                if local_name == 'tr' and ns_uri in self.TEXT_NS_URIS:
                    cells = []

                    # hp:tc 또는 hp10:tc (table cell) 요소 찾기
                    for cell_elem in elem.iter():
                        cell_tag = cell_elem.tag

                        if not cell_tag.startswith('{'):
                            continue

                        cell_ns_end = cell_tag.find('}')
                        cell_ns_uri = cell_tag[1:cell_ns_end]
                        cell_local_name = cell_tag[cell_ns_end + 1:]

                        # hp:tc 또는 hp10:tc 요소
                        if cell_local_name == 'tc' and cell_ns_uri in self.TEXT_NS_URIS:
                            cell_text = self._extract_text_from_cell(cell_elem)
                            cleaned = self._clean_text_content(cell_text)
                            cells.append(cleaned)

                    if cells:
                        rows.append(cells)

            if rows:
                return {
                    "rows": rows,
                    "row_count": len(rows),
                    "col_count": max(len(row) for row in rows) if rows else 0
                }

        except Exception as e:
            logger.warning("테이블 파싱 실패", error=str(e))

        return None

    def _extract_text_from_cell(self, cell_elem: ET.Element) -> str:
        """테이블 셀에서 텍스트 추출.

        v2.0: hp10 네임스페이스 지원 추가
        """
        texts = []

        for elem in cell_elem.iter():
            tag = elem.tag

            if tag.startswith('{'):
                ns_end = tag.find('}')
                ns_uri = tag[1:ns_end]
                local_name = tag[ns_end + 1:]

                # hp:t 또는 hp10:t 요소의 텍스트 추출
                if local_name == 't' and ns_uri in self.TEXT_NS_URIS:
                    if elem.text:
                        texts.append(elem.text)

        return ' '.join(texts)


def parse(file_path: str) -> Dict[str, Any]:
    """
    Parse HWPX file using HWPXParser.

    Args:
        file_path: Path to HWPX file

    Returns:
        Dict containing extracted content
    """
    parser = HWPXParser()
    return parser.parse(file_path)
