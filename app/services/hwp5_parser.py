"""
HWP5 parser implementation.
Uses hwp5 library if available.
"""
import structlog
from typing import Dict, Any, List
import json

logger = structlog.get_logger()


def parse(file_path: str) -> Dict[str, Any]:
    """
    Parse HWP file using hwp5 library.
    
    Args:
        file_path: Path to HWP file
        
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
        # Try to import hwp5
        import hwp5
        from hwp5.dataio import ParseError
        
        # Open HWP file
        hwp = hwp5.HWP5File(file_path)
        
        # Extract metadata
        try:
            docinfo = hwp.docinfo
            if docinfo:
                result["metadata"] = extract_metadata(docinfo)
        except Exception as e:
            logger.warning("Failed to extract metadata", error=str(e))
        
        # Extract text content
        text_parts = []
        paragraph_list = []
        table_list = []
        
        # Iterate through bodytext sections
        for section in hwp.bodytext.sections:
            section_text_parts = []
            section_para_count = 0
            
            for paragraph in section:
                try:
                    # Extract paragraph text
                    para_text = extract_paragraph_text(paragraph)
                    if para_text:
                        section_text_parts.append(para_text)
                        section_para_count += 1
                        
                        # Create paragraph entry
                        paragraph_list.append({
                            "text": para_text,
                            "style": extract_paragraph_style(paragraph)
                        })
                    
                    # Check for tables
                    for ctrl in paragraph.controls:
                        if hasattr(ctrl, 'table') or ctrl.__class__.__name__ == 'Table':
                            table_data = extract_table(ctrl)
                            if table_data:
                                table_list.append(table_data)
                                
                except Exception as e:
                    logger.warning("Failed to process paragraph", error=str(e))
                    continue
            
            if section_text_parts:
                section_text = "\n\n".join(section_text_parts)
                text_parts.append(section_text)
                
                result["structure"]["sections"].append({
                    "section_id": f"section_{len(result['structure']['sections'])}",
                    "text_length": len(section_text),
                    "paragraph_count": section_para_count
                })
        
        result["structure"]["total_sections"] = len(result["structure"]["sections"])
        result["text"] = "\n\n".join(text_parts)
        result["paragraphs"] = paragraph_list
        result["tables"] = table_list
        
        hwp.close()
        
    except ImportError:
        logger.error("hwp5 library not available")
        raise Exception("hwp5 library is not installed")
    except Exception as e:
        logger.error("Error parsing HWP with hwp5", error=str(e))
        raise
    
    return result


def extract_metadata(docinfo) -> Dict[str, str]:
    """Extract metadata from docinfo."""
    metadata = {}
    
    try:
        # Extract document properties
        if hasattr(docinfo, 'title'):
            metadata["title"] = str(docinfo.title)
        if hasattr(docinfo, 'author'):
            metadata["author"] = str(docinfo.author)
        if hasattr(docinfo, 'subject'):
            metadata["subject"] = str(docinfo.subject)
        if hasattr(docinfo, 'keywords'):
            metadata["keywords"] = str(docinfo.keywords)
        if hasattr(docinfo, 'created_date'):
            metadata["created_date"] = str(docinfo.created_date)
        if hasattr(docinfo, 'modified_date'):
            metadata["modified_date"] = str(docinfo.modified_date)
            
        # Try to get document statistics
        if hasattr(docinfo, 'document_properties'):
            props = docinfo.document_properties
            if hasattr(props, 'page_count'):
                metadata["page_count"] = props.page_count
                
    except Exception as e:
        logger.warning("Error extracting metadata", error=str(e))
    
    return metadata


def extract_paragraph_text(paragraph) -> str:
    """Extract text from a paragraph object."""
    text_parts = []
    
    try:
        # Method 1: Direct text attribute
        if hasattr(paragraph, 'text'):
            text = str(paragraph.text).strip()
            if text:
                return text
        
        # Method 2: Iterate through runs
        if hasattr(paragraph, 'runs'):
            for run in paragraph.runs:
                if hasattr(run, 'text'):
                    text_parts.append(str(run.text))
        
        # Method 3: Get text through string conversion
        if not text_parts:
            para_str = str(paragraph).strip()
            if para_str and not para_str.startswith('<'):
                text_parts.append(para_str)
                
    except Exception as e:
        logger.debug("Error extracting paragraph text", error=str(e))
    
    return " ".join(text_parts).strip()


def extract_paragraph_style(paragraph) -> Dict[str, Any]:
    """Extract style information from paragraph."""
    style = {}
    
    try:
        if hasattr(paragraph, 'shape'):
            shape = paragraph.shape
            if hasattr(shape, 'level'):
                style["level"] = shape.level
            if hasattr(shape, 'align'):
                style["align"] = str(shape.align)
                
        if hasattr(paragraph, 'style_id'):
            style["style_id"] = paragraph.style_id
            
        # Check if it's a heading
        if hasattr(paragraph, 'outline_level'):
            level = paragraph.outline_level
            if level > 0:
                style["is_heading"] = True
                style["level"] = level
                
    except Exception as e:
        logger.debug("Error extracting paragraph style", error=str(e))
    
    return style


def extract_table(table_ctrl) -> Dict[str, Any]:
    """Extract table data from table control."""
    table_data = {
        "rows": [],
        "row_count": 0,
        "col_count": 0
    }
    
    try:
        # Get table object
        table = table_ctrl.table if hasattr(table_ctrl, 'table') else table_ctrl
        
        # Extract rows
        if hasattr(table, 'rows'):
            for row in table.rows:
                row_data = []
                if hasattr(row, 'cells'):
                    for cell in row.cells:
                        cell_text = extract_cell_text(cell)
                        row_data.append(cell_text)
                table_data["rows"].append(row_data)
        
        # Update counts
        table_data["row_count"] = len(table_data["rows"])
        if table_data["rows"]:
            table_data["col_count"] = max(len(row) for row in table_data["rows"])
            
    except Exception as e:
        logger.warning("Error extracting table", error=str(e))
    
    return table_data if table_data["rows"] else None


def extract_cell_text(cell) -> str:
    """Extract text from table cell."""
    text_parts = []
    
    try:
        # Method 1: Direct text
        if hasattr(cell, 'text'):
            return str(cell.text).strip()
        
        # Method 2: Paragraphs in cell
        if hasattr(cell, 'paragraphs'):
            for para in cell.paragraphs:
                para_text = extract_paragraph_text(para)
                if para_text:
                    text_parts.append(para_text)
                    
        # Method 3: String conversion
        if not text_parts:
            cell_str = str(cell).strip()
            if cell_str and not cell_str.startswith('<'):
                text_parts.append(cell_str)
                
    except Exception as e:
        logger.debug("Error extracting cell text", error=str(e))
    
    return " ".join(text_parts).strip()