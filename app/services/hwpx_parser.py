"""
HWPX Parser implementation.
HWPX is the new XML-based format for HWP files.
"""
import structlog
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional
import os
import tempfile

logger = structlog.get_logger()


class HWPXParser:
    """Parser for HWPX (XML-based HWP) files."""
    
    def __init__(self):
        self.namespaces = {
            'pkg': 'http://schemas.microsoft.com/office/2006/xmlPackage',
            'hh': 'http://www.hancom.co.kr/hwpml/2011/head',
            'hp': 'http://www.hancom.co.kr/hwpml/2011/paragraph',
            'hs': 'http://www.hancom.co.kr/hwpml/2011/section',
            'ht': 'http://www.hancom.co.kr/hwpml/2011/table',
            'hc': 'http://www.hancom.co.kr/hwpml/2011/core',
            'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
        }
    
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
            # HWPX files are ZIP archives
            with zipfile.ZipFile(file_path, 'r') as zip_file:
                # Extract metadata
                result["metadata"] = self._extract_metadata(zip_file)
                
                # Extract content from sections
                sections_data = self._extract_sections(zip_file)
                
                # Process sections
                all_paragraphs = []
                all_tables = []
                
                for section_idx, section_data in enumerate(sections_data):
                    section_info = {
                        "section_id": f"section{section_idx}",
                        "paragraph_count": 0,
                        "table_count": 0
                    }
                    
                    # Extract paragraphs
                    paragraphs = self._extract_paragraphs_from_section(section_data)
                    section_info["paragraph_count"] = len(paragraphs)
                    all_paragraphs.extend(paragraphs)
                    
                    # Extract tables
                    tables = self._extract_tables_from_section(section_data)
                    section_info["table_count"] = len(tables)
                    all_tables.extend(tables)
                    
                    result["structure"]["sections"].append(section_info)
                
                result["structure"]["total_sections"] = len(sections_data)
                result["paragraphs"] = all_paragraphs
                result["tables"] = all_tables
                
                # Combine all text
                result["text"] = "\n\n".join([p.get("text", "") for p in all_paragraphs])
                
        except Exception as e:
            logger.error("Error parsing HWPX", error=str(e), file_path=file_path)
            raise
        
        return result
    
    def _extract_metadata(self, zip_file: zipfile.ZipFile) -> Dict[str, Any]:
        """Extract metadata from HWPX file."""
        metadata = {}
        
        try:
            # Try to read meta.xml
            if 'Contents/meta.xml' in zip_file.namelist():
                with zip_file.open('Contents/meta.xml') as meta_file:
                    tree = ET.parse(meta_file)
                    root = tree.getroot()
                    
                    # Extract common metadata fields
                    for elem in root.iter():
                        if elem.tag.endswith('title'):
                            metadata['title'] = elem.text or ""
                        elif elem.tag.endswith('subject'):
                            metadata['subject'] = elem.text or ""
                        elif elem.tag.endswith('creator'):
                            metadata['author'] = elem.text or ""
                        elif elem.tag.endswith('keywords'):
                            metadata['keywords'] = elem.text or ""
                        elif elem.tag.endswith('created'):
                            metadata['created_date'] = elem.text or ""
                        elif elem.tag.endswith('modified'):
                            metadata['modified_date'] = elem.text or ""
                            
        except Exception as e:
            logger.warning("Failed to extract metadata", error=str(e))
        
        return metadata
    
    def _extract_sections(self, zip_file: zipfile.ZipFile) -> List[ET.Element]:
        """Extract all section data from HWPX."""
        sections = []
        
        try:
            # List all files in Contents directory
            content_files = [f for f in zip_file.namelist() if f.startswith('Contents/') and f.endswith('.xml')]
            
            # Find section files (usually section0.xml, section1.xml, etc.)
            section_files = sorted([f for f in content_files if 'section' in f])
            
            for section_file in section_files:
                try:
                    with zip_file.open(section_file) as sf:
                        tree = ET.parse(sf)
                        sections.append(tree.getroot())
                except Exception as e:
                    logger.warning(f"Failed to parse section file: {section_file}", error=str(e))
                    
        except Exception as e:
            logger.error("Failed to extract sections", error=str(e))
        
        return sections
    
    def _extract_paragraphs_from_section(self, section_root: ET.Element) -> List[Dict[str, Any]]:
        """Extract paragraphs from a section element."""
        paragraphs = []
        
        try:
            # Find all paragraph elements
            for para_elem in section_root.iter():
                if para_elem.tag.endswith('p') or para_elem.tag.endswith('para'):
                    text = self._extract_text_from_element(para_elem)
                    if text.strip():
                        paragraphs.append({
                            "text": text,
                            "style": self._extract_style_from_element(para_elem)
                        })
                        
        except Exception as e:
            logger.warning("Failed to extract paragraphs", error=str(e))
        
        return paragraphs
    
    def _extract_tables_from_section(self, section_root: ET.Element) -> List[Dict[str, Any]]:
        """Extract tables from a section element."""
        tables = []
        
        try:
            # Find all table elements
            for table_elem in section_root.iter():
                if table_elem.tag.endswith('tbl') or table_elem.tag.endswith('table'):
                    table_data = self._parse_table_element(table_elem)
                    if table_data:
                        tables.append(table_data)
                        
        except Exception as e:
            logger.warning("Failed to extract tables", error=str(e))
        
        return tables
    
    def _extract_text_from_element(self, element: ET.Element) -> str:
        """Recursively extract text from an XML element."""
        texts = []
        
        # Get direct text
        if element.text:
            texts.append(element.text)
        
        # Process child elements
        for child in element:
            # Check for text run elements
            if child.tag.endswith('t') or child.tag.endswith('text'):
                if child.text:
                    texts.append(child.text)
            else:
                # Recursively extract from other elements
                child_text = self._extract_text_from_element(child)
                if child_text:
                    texts.append(child_text)
            
            # Get tail text
            if child.tail:
                texts.append(child.tail)
        
        return ''.join(texts)
    
    def _extract_style_from_element(self, element: ET.Element) -> Dict[str, Any]:
        """Extract style information from an element."""
        style = {}
        
        try:
            # Check for style attributes
            if 'style' in element.attrib:
                style['raw_style'] = element.attrib['style']
            
            # Check for specific style elements
            for child in element:
                if child.tag.endswith('pPr'):  # Paragraph properties
                    if child.find('.//sz') is not None:
                        style['font_size'] = child.find('.//sz').get('val', '')
                    if child.find('.//b') is not None:
                        style['bold'] = True
                    if child.find('.//i') is not None:
                        style['italic'] = True
                        
        except Exception as e:
            logger.debug("Failed to extract style", error=str(e))
        
        return style
    
    def _parse_table_element(self, table_elem: ET.Element) -> Optional[Dict[str, Any]]:
        """Parse a table element and extract its data."""
        try:
            rows = []
            
            # Find all row elements
            for row_elem in table_elem.iter():
                if row_elem.tag.endswith('tr') or row_elem.tag.endswith('row'):
                    cells = []
                    
                    # Find all cell elements
                    for cell_elem in row_elem.iter():
                        if cell_elem.tag.endswith('tc') or cell_elem.tag.endswith('cell'):
                            cell_text = self._extract_text_from_element(cell_elem)
                            cells.append(cell_text)
                    
                    if cells:
                        rows.append(cells)
            
            if rows:
                return {
                    "rows": rows,
                    "row_count": len(rows),
                    "col_count": max(len(row) for row in rows) if rows else 0
                }
                
        except Exception as e:
            logger.warning("Failed to parse table", error=str(e))
        
        return None


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