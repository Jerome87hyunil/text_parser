"""
HWPX Parser implementation using lxml.

HWPX is the XML-based format for Hancom Office documents (OWPML spec).
v3.0: lxml + XPath rewrite, markdown output, cell span extraction,
      no Preview text fallback.
"""
import re
import zipfile
from typing import Any, Dict, List, Optional

import structlog
from lxml import etree

logger = structlog.get_logger()

# OWPML namespace map (2011 + 2016 variants)
NS = {
    "hp": "http://www.hancom.co.kr/hwpml/2011/paragraph",
    "hp10": "http://www.hancom.co.kr/hwpml/2016/paragraph",
    "hs": "http://www.hancom.co.kr/hwpml/2011/section",
    "hh": "http://www.hancom.co.kr/hwpml/2011/head",
    "hc": "http://www.hancom.co.kr/hwpml/2011/core",
}

# Full URIs for the two paragraph namespaces we care about
_HP_URI = NS["hp"]
_HP10_URI = NS["hp10"]

# Zero-width / invisible characters to strip
_ZW_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")


def _find_elements(root: etree._Element, local_name: str) -> List[etree._Element]:
    """Find elements matching *local_name* in both hp (2011) and hp10 (2016) namespaces."""
    results: List[etree._Element] = []
    results.extend(root.xpath(f".//hp:{local_name}", namespaces=NS))
    results.extend(root.xpath(f".//hp10:{local_name}", namespaces=NS))
    return results


def _local_tag(elem: etree._Element) -> str:
    """Return the local tag name (without namespace URI)."""
    tag = elem.tag
    if isinstance(tag, str) and tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag if isinstance(tag, str) else ""


def _tag_ns_uri(elem: etree._Element) -> str:
    """Return the namespace URI portion of the tag."""
    tag = elem.tag
    if isinstance(tag, str) and tag.startswith("{"):
        return tag[1:].split("}", 1)[0]
    return ""


def _is_paragraph_ns(elem: etree._Element) -> bool:
    """Check whether the element belongs to hp or hp10 namespace."""
    uri = _tag_ns_uri(elem)
    return uri in (_HP_URI, _HP10_URI)


def _clean_text(text: str) -> str:
    """Remove zero-width chars and collapse whitespace."""
    if not text:
        return ""
    cleaned = _ZW_RE.sub("", text)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _table_to_markdown(table: Dict[str, Any]) -> str:
    """Convert a parsed table dict to a markdown table string.

    The first row is treated as the header.  All cells are padded to equal
    column widths for readability.
    """
    rows: List[List[Dict[str, Any]]] = table.get("rows", [])
    if not rows:
        return ""

    col_count = table.get("col_count", 0)
    if col_count == 0:
        return ""

    # Flatten cell text into a simple 2-D string grid, respecting col_count
    str_rows: List[List[str]] = []
    for row in rows:
        cells = [cell.get("text", "") for cell in row]
        # Pad or trim to col_count
        while len(cells) < col_count:
            cells.append("")
        str_rows.append(cells[:col_count])

    # Compute column widths (minimum 3 for the separator)
    col_widths = [3] * col_count
    for row in str_rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(cell))

    def _fmt_row(cells: List[str]) -> str:
        padded = [c.ljust(w) for c, w in zip(cells, col_widths)]
        return "| " + " | ".join(padded) + " |"

    lines: List[str] = []
    # Header
    lines.append(_fmt_row(str_rows[0]))
    # Separator
    sep = ["-" * w for w in col_widths]
    lines.append("| " + " | ".join(sep) + " |")
    # Body
    for row in str_rows[1:]:
        lines.append(_fmt_row(row))

    return "\n".join(lines)


class HWPXParser:
    """Parser for HWPX (XML-based HWP) files using lxml + XPath."""

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse(self, file_path: str) -> Dict[str, Any]:
        """Parse an HWPX file and return structured content.

        Returns a dict with keys: paragraphs, tables, metadata, text,
        markdown, structure.
        """
        result: Dict[str, Any] = {
            "paragraphs": [],
            "tables": [],
            "metadata": {},
            "text": "",
            "markdown": "",
            "structure": {"sections": [], "total_sections": 0},
        }

        try:
            logger.info("HWPX 파싱 시작", file_path=file_path)

            with zipfile.ZipFile(file_path, "r") as zf:
                result["metadata"] = self._extract_metadata(zf)

                section_roots = self._load_sections(zf)

                all_paragraphs: List[Dict[str, Any]] = []
                all_tables: List[Dict[str, Any]] = []

                for idx, root in enumerate(section_roots):
                    paragraphs = self._extract_paragraphs(root)
                    tables = self._extract_tables(root)

                    result["structure"]["sections"].append(
                        {
                            "section_id": f"section{idx}",
                            "paragraph_count": len(paragraphs),
                            "table_count": len(tables),
                        }
                    )

                    all_paragraphs.extend(paragraphs)
                    all_tables.extend(tables)

                result["structure"]["total_sections"] = len(section_roots)
                result["paragraphs"] = all_paragraphs
                result["tables"] = all_tables

                # Plain text: paragraph texts joined by newline
                result["text"] = "\n".join(
                    p["text"] for p in all_paragraphs if p["text"]
                )

                # Markdown output
                result["markdown"] = self._build_markdown(all_paragraphs, all_tables)

                logger.info(
                    "HWPX 파싱 완료",
                    text_length=len(result["text"]),
                    paragraph_count=len(all_paragraphs),
                    table_count=len(all_tables),
                )

        except Exception as e:
            logger.error("HWPX 파싱 오류", error=str(e), file_path=file_path)
            raise

        return result

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def _extract_metadata(self, zf: zipfile.ZipFile) -> Dict[str, Any]:
        """Extract metadata from version.xml and Contents/header.xml."""
        metadata: Dict[str, Any] = {}

        try:
            if "version.xml" in zf.namelist():
                with zf.open("version.xml") as f:
                    content = f.read().decode("utf-8", errors="ignore")
                    match = re.search(r'version="([^"]*)"', content)
                    if match:
                        metadata["hwp_version"] = match.group(1)

            if "Contents/header.xml" in zf.namelist():
                with zf.open("Contents/header.xml") as f:
                    etree.parse(f)  # validate parseable
                    metadata["has_header"] = True
        except Exception as e:
            logger.warning("메타데이터 추출 실패", error=str(e))

        return metadata

    # ------------------------------------------------------------------
    # Section loading
    # ------------------------------------------------------------------

    def _load_sections(self, zf: zipfile.ZipFile) -> List[etree._Element]:
        """Load and parse all Contents/sectionN.xml files."""
        section_files = sorted(
            f
            for f in zf.namelist()
            if f.startswith("Contents/section") and f.endswith(".xml")
        )

        logger.debug("섹션 파일 발견", count=len(section_files), files=section_files)

        roots: List[etree._Element] = []
        for sf in section_files:
            try:
                with zf.open(sf) as fh:
                    tree = etree.parse(fh)
                    roots.append(tree.getroot())
                    logger.debug("섹션 파싱 성공", file=sf)
            except etree.XMLSyntaxError as e:
                logger.warning("섹션 XML 파싱 오류", file=sf, error=str(e))

        return roots

    # ------------------------------------------------------------------
    # Paragraph extraction
    # ------------------------------------------------------------------

    def _extract_paragraphs(
        self, section_root: etree._Element
    ) -> List[Dict[str, Any]]:
        """Extract top-level paragraphs from a section, skipping those inside subList (table cells)."""
        paragraphs: List[Dict[str, Any]] = []

        # Find all <hp:p> / <hp10:p> elements
        all_p = _find_elements(section_root, "p")

        for p_elem in all_p:
            # Skip paragraphs nested inside a subList (they belong to table cells)
            if self._is_inside_sublist(p_elem):
                continue

            runs = self._extract_runs(p_elem)
            full_text = "".join(r["text"] for r in runs)
            full_text = _clean_text(full_text)

            if not full_text:
                continue

            has_emphasis = any(r.get("bold") or r.get("italic") for r in runs)

            paragraphs.append(
                {
                    "text": full_text,
                    "style": self._extract_style(p_elem),
                    "has_emphasis": has_emphasis,
                }
            )

        return paragraphs

    def _is_inside_sublist(self, elem: etree._Element) -> bool:
        """Return True if *elem* has an ancestor with local name 'subList'."""
        parent = elem.getparent()
        while parent is not None:
            if _local_tag(parent) == "subList":
                return True
            parent = parent.getparent()
        return False

    def _extract_runs(self, p_elem: etree._Element) -> List[Dict[str, Any]]:
        """Extract run-level data from a paragraph element.

        Each run may contain character properties (charPr) indicating bold/italic.
        """
        runs: List[Dict[str, Any]] = []

        run_elems = _find_elements(p_elem, "run")
        for run_el in run_elems:
            # Only consider direct children of this paragraph
            if run_el.getparent() is not p_elem:
                # Check if the run is a direct child or nested via another p
                ancestor_p = run_el.getparent()
                while ancestor_p is not None and _local_tag(ancestor_p) != "p":
                    ancestor_p = ancestor_p.getparent()
                if ancestor_p is not p_elem:
                    continue

            texts: List[str] = []
            t_elems = _find_elements(run_el, "t")
            for t_el in t_elems:
                if t_el.text:
                    texts.append(t_el.text)

            run_text = "".join(texts)
            if not run_text:
                continue

            bold = False
            italic = False
            char_prs = _find_elements(run_el, "charPr")
            for cp in char_prs:
                if cp.get("bold") == "1":
                    bold = True
                if cp.get("italic") == "1":
                    italic = True

            runs.append({"text": run_text, "bold": bold, "italic": italic})

        return runs

    def _extract_style(self, p_elem: etree._Element) -> Dict[str, Any]:
        """Extract style references from a paragraph element."""
        style: Dict[str, Any] = {}
        if p_elem.get("paraPrIDRef"):
            style["para_style_ref"] = p_elem.get("paraPrIDRef")
        if p_elem.get("styleIDRef"):
            style["style_ref"] = p_elem.get("styleIDRef")
        return style

    # ------------------------------------------------------------------
    # Table extraction
    # ------------------------------------------------------------------

    def _extract_tables(
        self, section_root: etree._Element
    ) -> List[Dict[str, Any]]:
        """Extract all tables from a section."""
        tables: List[Dict[str, Any]] = []

        tbl_elems = _find_elements(section_root, "tbl")
        for tbl_el in tbl_elems:
            table = self._parse_table(tbl_el)
            if table:
                tables.append(table)

        return tables

    def _parse_table(self, tbl_elem: etree._Element) -> Optional[Dict[str, Any]]:
        """Parse a single table element into structured data with cell span info."""
        try:
            rows: List[List[Dict[str, Any]]] = []

            tr_elems = _find_elements(tbl_elem, "tr")
            for tr_el in tr_elems:
                cells: List[Dict[str, Any]] = []

                tc_elems = _find_elements(tr_el, "tc")
                for tc_el in tc_elems:
                    cell_text = self._extract_cell_text(tc_el)
                    cell_text = _clean_text(cell_text)

                    # Extract span attributes from cellAddr or tc element itself
                    col_span = 1
                    row_span = 1

                    # cellAddr may carry colSpan/rowSpan
                    cell_addrs = _find_elements(tc_el, "cellAddr")
                    if cell_addrs:
                        addr = cell_addrs[0]
                        col_span = int(addr.get("colSpan", "1") or "1")
                        row_span = int(addr.get("rowSpan", "1") or "1")

                    # Some HWPX files store span on <tc> directly
                    if col_span == 1 and tc_el.get("colSpan"):
                        col_span = int(tc_el.get("colSpan", "1") or "1")
                    if row_span == 1 and tc_el.get("rowSpan"):
                        row_span = int(tc_el.get("rowSpan", "1") or "1")

                    cells.append(
                        {
                            "text": cell_text,
                            "colSpan": col_span,
                            "rowSpan": row_span,
                        }
                    )

                if cells:
                    rows.append(cells)

            if rows:
                max_cols = max(len(row) for row in rows)
                return {
                    "rows": rows,
                    "row_count": len(rows),
                    "col_count": max_cols,
                }

        except Exception as e:
            logger.warning("테이블 파싱 실패", error=str(e))

        return None

    def _extract_cell_text(self, tc_elem: etree._Element) -> str:
        """Extract all text from a table cell (via subList > p > run > t)."""
        texts: List[str] = []

        t_elems = _find_elements(tc_elem, "t")
        for t_el in t_elems:
            if t_el.text:
                texts.append(t_el.text)

        return " ".join(texts)

    # ------------------------------------------------------------------
    # Markdown generation
    # ------------------------------------------------------------------

    def _build_markdown(
        self,
        paragraphs: List[Dict[str, Any]],
        tables: List[Dict[str, Any]],
    ) -> str:
        """Build a markdown string from paragraphs and tables.

        Tables are inserted after the last paragraph that precedes them
        (best-effort ordering based on sequential index).
        """
        parts: List[str] = []

        # Simple strategy: paragraphs first, then tables at the end.
        # A more precise interleaving would require positional info from the XML,
        # which we don't track.  This gives a readable output.
        for p in paragraphs:
            text = p["text"]
            if p.get("has_emphasis"):
                parts.append(f"**{text}**")
            else:
                parts.append(text)

        for tbl in tables:
            md = _table_to_markdown(tbl)
            if md:
                parts.append("")  # blank line before table
                parts.append(md)
                parts.append("")  # blank line after table

        return "\n".join(parts)


# ------------------------------------------------------------------
# Module-level convenience function (backward compatibility)
# ------------------------------------------------------------------


def parse(file_path: str) -> Dict[str, Any]:
    """Parse an HWPX file and return structured content.

    This is the module-level entry point kept for backward compatibility.
    """
    parser = HWPXParser()
    return parser.parse(file_path)
