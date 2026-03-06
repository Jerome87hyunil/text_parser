"""
HWP5 binary to HWPX (OWPML) converter.

HWP5 OLE Compound File에서 텍스트를 추출하여 HWPX ZIP 포맷으로 변환합니다.
변환된 HWPX는 통합 HWPX 파서로 파싱할 수 있어 단일 파이프라인을 구현합니다.

HWP5 레코드 구조:
  4바이트 헤더 (little-endian):
    bits  0-9 : Tag ID  (HWPTAG_PARA_TEXT = 0x42)
    bits 10-19: Level
    bits 20-31: Size (0xFFF이면 다음 4바이트가 실제 크기)

PARA_TEXT 디코딩 (UTF-16LE):
  code < 0x20: 제어 문자
    1-10, 11-18, 21-23: 인라인 컨트롤 데이터 12바이트 스킵
    24: 14바이트 스킵
    13: 줄바꿈
    9: 탭
    0: 텍스트 종료
  code >= 0x20: 일반 유니코드 문자
"""
import os
import struct
import tempfile
import zipfile
import zlib
from typing import Optional, List

import structlog

try:
    from lxml import etree
except ImportError:
    etree = None  # type: ignore[assignment]

try:
    import olefile
except ImportError:
    olefile = None  # type: ignore[assignment]

logger = structlog.get_logger()

# HWP5 레코드 태그 ID
HWPTAG_PARA_TEXT = 0x42

# 인라인 컨트롤 문자별 추가 스킵 바이트 수
_INLINE_SKIP_12 = frozenset(range(1, 11)) | frozenset(range(11, 19)) | frozenset({21, 22, 23})
_INLINE_SKIP_14 = frozenset({24})

# OWPML 네임스페이스
_HP_NS = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_HS_NS = "http://www.hancom.co.kr/hwpml/2011/section"
_HH_NS = "http://www.hancom.co.kr/hwpml/2011/head"
_HA_NS = "http://www.hancom.co.kr/hwpml/2011/app"
_HPF_NS = "http://www.hancom.co.kr/schema/2011/hpf"
_HC_NS = "http://www.hancom.co.kr/hwpml/2011/core"

# A4 page dimensions in HWPML units (1/7200 inch)
# A4 = 210mm x 297mm = 59528 x 84188 hwpml units
_A4_WIDTH = "59528"
_A4_HEIGHT = "84188"
_MARGIN_LEFT = "8504"
_MARGIN_RIGHT = "8504"
_MARGIN_TOP = "5668"
_MARGIN_BOTTOM = "4252"
_MARGIN_HEADER = "4252"
_MARGIN_FOOTER = "4252"


def _xml_escape(text: str) -> str:
    """XML 특수문자 이스케이프."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


class HwpToHwpxConverter:
    """HWP5 바이너리 파일을 HWPX (OWPML XML in ZIP) 포맷으로 변환합니다."""

    def convert(self, hwp_path: str) -> Optional[str]:
        """
        HWP5 파일을 HWPX로 변환합니다.

        Args:
            hwp_path: HWP 파일 경로

        Returns:
            변환된 HWPX 임시 파일 경로. 실패 시 None.
            호출자가 임시 파일 삭제를 담당합니다.
        """
        if olefile is None:
            logger.error("olefile 라이브러리가 설치되지 않았습니다")
            return None

        if etree is None:
            logger.error("lxml 라이브러리가 설치되지 않았습니다")
            return None

        if not os.path.isfile(hwp_path):
            logger.error("HWP 파일을 찾을 수 없습니다", path=hwp_path)
            return None

        try:
            logger.info("HWP→HWPX 변환 시작", path=hwp_path)

            # 1. OLE 파일 열기 및 압축 플래그 확인
            ole = olefile.OleFileIO(hwp_path)
            try:
                is_compressed = self._check_compressed(ole)
                logger.debug("압축 플래그 확인", compressed=is_compressed)

                # 2. 섹션별 텍스트 추출
                sections_text = self._extract_all_sections(ole, is_compressed)
                logger.info(
                    "텍스트 추출 완료",
                    section_count=len(sections_text),
                    total_chars=sum(len(s) for s in sections_text),
                )

                if not sections_text or all(not s.strip() for s in sections_text):
                    logger.warning("추출된 텍스트가 없습니다", path=hwp_path)
                    return None

            finally:
                ole.close()

            # 3. HWPX ZIP 패키징
            hwpx_path = self._package_hwpx(sections_text)
            logger.info("HWP→HWPX 변환 완료", output=hwpx_path)
            return hwpx_path

        except Exception as e:
            logger.error("HWP→HWPX 변환 실패", path=hwp_path, error=str(e))
            return None

    # ──────────────────────────────────────────────
    # HWP5 바이너리 파싱
    # ──────────────────────────────────────────────

    def _check_compressed(self, ole: "olefile.OleFileIO") -> bool:
        """FileHeader에서 압축 플래그 확인 (byte 32, bit 0)."""
        try:
            header_data = ole.openstream("FileHeader").read()
            if len(header_data) > 36:
                flags = struct.unpack_from("<I", header_data, 32)[0]
                return bool(flags & 0x01)
        except Exception as e:
            logger.warning("FileHeader 읽기 실패, 압축 가정", error=str(e))
        return True  # 기본값: 압축됨

    def _extract_all_sections(
        self, ole: "olefile.OleFileIO", is_compressed: bool
    ) -> List[str]:
        """BodyText/Section0, Section1, ... 스트림에서 텍스트 추출."""
        sections_text: List[str] = []
        section_idx = 0

        while True:
            stream_name = f"BodyText/Section{section_idx}"
            if not ole.exists(stream_name):
                break

            try:
                raw = ole.openstream(stream_name).read()
                data = self._decompress(raw, is_compressed)
                text = self._parse_records(data)
                sections_text.append(text)
                logger.debug(
                    "섹션 텍스트 추출",
                    section=section_idx,
                    raw_size=len(raw),
                    text_len=len(text),
                )
            except Exception as e:
                logger.warning(
                    "섹션 추출 실패, 건너뜀",
                    section=section_idx,
                    error=str(e),
                )
                sections_text.append("")

            section_idx += 1

        return sections_text

    def _decompress(self, data: bytes, is_compressed: bool) -> bytes:
        """데이터 압축 해제. 압축되지 않았으면 그대로 반환."""
        if not is_compressed:
            return data

        try:
            return zlib.decompress(data, -15)
        except zlib.error:
            try:
                return zlib.decompress(data)
            except zlib.error:
                logger.warning("압축 해제 실패, 원본 데이터 사용")
                return data

    def _parse_records(self, data: bytes) -> str:
        """HWP5 레코드 구조를 파싱하여 PARA_TEXT 텍스트 추출."""
        paragraphs: List[str] = []
        offset = 0
        data_len = len(data)

        while offset + 4 <= data_len:
            try:
                header = struct.unpack_from("<I", data, offset)[0]
                offset += 4

                tag_id = header & 0x3FF
                size = (header >> 20) & 0xFFF

                # 확장 크기: 0xFFF이면 다음 4바이트가 실제 크기
                if size == 0xFFF:
                    if offset + 4 > data_len:
                        break
                    size = struct.unpack_from("<I", data, offset)[0]
                    offset += 4

                # 레코드 데이터 범위 확인
                if offset + size > data_len:
                    logger.debug(
                        "레코드 범위 초과, 파싱 종료",
                        offset=offset,
                        size=size,
                        data_len=data_len,
                    )
                    break

                # PARA_TEXT 레코드에서만 텍스트 추출
                if tag_id == HWPTAG_PARA_TEXT:
                    record_data = data[offset : offset + size]
                    text = self._decode_para_text(record_data)
                    if text.strip():
                        paragraphs.append(text)

                offset += size

            except struct.error:
                logger.debug("레코드 헤더 파싱 실패, 건너뜀", offset=offset)
                break
            except Exception as e:
                logger.debug("레코드 처리 오류, 건너뜀", offset=offset, error=str(e))
                offset += 1  # 1바이트씩 전진하여 복구 시도

        return "\n".join(paragraphs)

    def _decode_para_text(self, record_data: bytes) -> str:
        """
        PARA_TEXT 레코드를 UTF-16LE로 디코딩합니다.

        제어 문자 처리:
          code < 0x20:
            codes {1..10, 11..18, 21..23}: 12바이트 추가 스킵
            code 24: 14바이트 추가 스킵
            code 13: 줄바꿈
            code 9: 탭
            code 0: 텍스트 종료
          code >= 0x20: 일반 유니코드 문자
        """
        chars: List[str] = []
        pos = 0
        length = len(record_data)

        while pos + 1 < length:
            code = struct.unpack_from("<H", record_data, pos)[0]
            pos += 2

            if code == 0:
                # 텍스트 종료
                break
            elif code < 0x20:
                # 제어 문자 처리
                if code in _INLINE_SKIP_12:
                    pos += 12
                elif code in _INLINE_SKIP_14:
                    pos += 14
                elif code == 13:
                    chars.append("\n")
                elif code == 9:
                    chars.append("\t")
                # 그 외 제어 문자는 무시
            else:
                # 일반 유니코드 문자
                chars.append(chr(code))

        return "".join(chars)

    # ──────────────────────────────────────────────
    # HWPX ZIP 패키징
    # ──────────────────────────────────────────────

    def _package_hwpx(self, sections_text: List[str]) -> str:
        """추출된 텍스트를 OWPML 구조의 HWPX ZIP으로 패키징합니다."""
        tmp = tempfile.NamedTemporaryFile(suffix=".hwpx", delete=False)
        tmp_path = tmp.name
        tmp.close()

        try:
            with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
                # mimetype은 첫 번째 엔트리, 비압축
                zf.writestr(
                    zipfile.ZipInfo("mimetype"),
                    "application/hwp+zip",
                    compress_type=zipfile.ZIP_STORED,
                )

                # version.xml
                zf.writestr("version.xml", self._build_version_xml())

                # META-INF/container.xml
                zf.writestr(
                    "META-INF/container.xml", self._build_container_xml()
                )

                # Contents/header.xml
                zf.writestr("Contents/header.xml", self._build_header_xml())

                # Contents/section{N}.xml
                section_files: List[str] = []
                for idx, text in enumerate(sections_text):
                    filename = f"Contents/section{idx}.xml"
                    section_files.append(filename)
                    zf.writestr(filename, self._build_section_xml(text))

                # Contents/content.hpf (manifest)
                zf.writestr(
                    "Contents/content.hpf",
                    self._build_content_hpf(section_files),
                )

        except Exception:
            # 실패 시 임시 파일 정리
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

        return tmp_path

    def _build_version_xml(self) -> str:
        """version.xml 생성."""
        root = etree.Element(
            "{%s}HWPVersion" % _HA_NS,
            nsmap={"ha": _HA_NS},
        )
        root.set("version", "1.1.0.0")
        return etree.tostring(
            root, xml_declaration=True, encoding="UTF-8", pretty_print=True
        ).decode("utf-8")

    def _build_container_xml(self) -> str:
        """META-INF/container.xml 생성."""
        container_ns = "urn:oasis:names:tc:opendocument:xmlns:container"
        root = etree.Element(
            "{%s}container" % container_ns,
            nsmap={None: container_ns},
        )
        root.set("version", "1.0")

        rootfiles = etree.SubElement(root, "{%s}rootfiles" % container_ns)
        rootfile = etree.SubElement(rootfiles, "{%s}rootfile" % container_ns)
        rootfile.set("full-path", "Contents/content.hpf")
        rootfile.set("media-type", "application/hwp+zip")

        return etree.tostring(
            root, xml_declaration=True, encoding="UTF-8", pretty_print=True
        ).decode("utf-8")

    def _build_header_xml(self) -> str:
        """Contents/header.xml (최소한의 스타일 정의) 생성."""
        root = etree.Element(
            "{%s}head" % _HH_NS,
            nsmap={
                "hh": _HH_NS,
                "hp": _HP_NS,
                "hc": _HC_NS,
            },
        )
        root.set("version", "1.1.0.0")

        # 기본 폰트 참조
        mapping_table = etree.SubElement(root, "{%s}mappingTable" % _HH_NS)
        face_name_list = etree.SubElement(
            mapping_table, "{%s}faceNameList" % _HH_NS
        )
        face_name = etree.SubElement(face_name_list, "{%s}faceName" % _HH_NS)
        face_name.set("name", "함초롬바탕")
        face_name.set("id", "0")

        return etree.tostring(
            root, xml_declaration=True, encoding="UTF-8", pretty_print=True
        ).decode("utf-8")

    def _build_section_xml(self, text: str) -> str:
        """Contents/section{N}.xml 생성. 텍스트를 단락으로 변환합니다."""
        nsmap = {
            "hp": _HP_NS,
            "hs": _HS_NS,
            "hc": _HC_NS,
        }

        root = etree.Element("{%s}sec" % _HS_NS, nsmap=nsmap)

        paragraphs = text.split("\n") if text.strip() else [""]

        for para_idx, para_text in enumerate(paragraphs):
            p_elem = etree.SubElement(root, "{%s}p" % _HP_NS)
            p_elem.set("paraPrIDRef", "0")
            p_elem.set("styleIDRef", "0")

            # 첫 번째 단락에 secPr (섹션 속성 - A4 페이지 설정) 포함
            if para_idx == 0:
                sec_pr = etree.SubElement(p_elem, "{%s}secPr" % _HP_NS)

                # 페이지 설정
                page_pr = etree.SubElement(sec_pr, "{%s}pagePr" % _HP_NS)
                page_pr.set("width", _A4_WIDTH)
                page_pr.set("height", _A4_HEIGHT)
                page_pr.set("gutterType", "LEFT_ONLY")

                # 여백 설정
                page_margin = etree.SubElement(
                    sec_pr, "{%s}pageMargin" % _HP_NS
                )
                page_margin.set("left", _MARGIN_LEFT)
                page_margin.set("right", _MARGIN_RIGHT)
                page_margin.set("top", _MARGIN_TOP)
                page_margin.set("bottom", _MARGIN_BOTTOM)
                page_margin.set("header", _MARGIN_HEADER)
                page_margin.set("footer", _MARGIN_FOOTER)

            # 텍스트 run 추가
            if para_text.strip():
                run_elem = etree.SubElement(p_elem, "{%s}run" % _HP_NS)
                t_elem = etree.SubElement(run_elem, "{%s}t" % _HP_NS)
                t_elem.text = _xml_escape(para_text)

        return etree.tostring(
            root, xml_declaration=True, encoding="UTF-8", pretty_print=True
        ).decode("utf-8")

    def _build_content_hpf(self, section_files: List[str]) -> str:
        """Contents/content.hpf (매니페스트) 생성."""
        root = etree.Element(
            "{%s}package" % _HPF_NS,
            nsmap={"hpf": _HPF_NS},
        )
        root.set("version", "1.1.0.0")
        root.set("uniqueIdentifier", "converted-hwp")

        # 메타데이터
        metadata = etree.SubElement(root, "{%s}metadata" % _HPF_NS)
        title = etree.SubElement(metadata, "{%s}title" % _HPF_NS)
        title.text = "Converted from HWP"

        # 매니페스트
        manifest = etree.SubElement(root, "{%s}manifest" % _HPF_NS)

        # header.xml
        item_header = etree.SubElement(manifest, "{%s}item" % _HPF_NS)
        item_header.set("id", "header")
        item_header.set("href", "header.xml")
        item_header.set("media-type", "application/xml")

        # 섹션 파일들
        for idx, sf in enumerate(section_files):
            item = etree.SubElement(manifest, "{%s}item" % _HPF_NS)
            item.set("id", f"section{idx}")
            # href는 Contents/ 기준 상대 경로
            item.set("href", sf.replace("Contents/", ""))
            item.set("media-type", "application/xml")

        # spine (읽기 순서)
        spine = etree.SubElement(root, "{%s}spine" % _HPF_NS)
        for idx in range(len(section_files)):
            itemref = etree.SubElement(spine, "{%s}itemref" % _HPF_NS)
            itemref.set("idref", f"section{idx}")

        return etree.tostring(
            root, xml_declaration=True, encoding="UTF-8", pretty_print=True
        ).decode("utf-8")


def convert_hwp_to_hwpx(hwp_path: str) -> Optional[str]:
    """
    모듈 레벨 편의 함수: HWP5 파일을 HWPX로 변환합니다.

    Args:
        hwp_path: HWP 파일 경로

    Returns:
        변환된 HWPX 임시 파일 경로. 실패 시 None.
        호출자가 임시 파일 삭제를 담당합니다.
    """
    converter = HwpToHwpxConverter()
    return converter.convert(hwp_path)
