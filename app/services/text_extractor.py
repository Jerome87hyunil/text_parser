"""
Text Extractor Service for structured content extraction.
Optimized for AI analysis and processing.
"""
import structlog
from typing import Dict, Any, List, Optional
import re
from datetime import datetime, timezone
import json

logger = structlog.get_logger()


class TextExtractor:
    """
    Extract and structure text content for AI analysis.
    """
    
    def extract_structured(
        self,
        parsed_content: Dict[str, Any],
        include_metadata: bool = True,
        include_structure: bool = True,
        include_statistics: bool = True
    ) -> Dict[str, Any]:
        """
        Extract structured content from parsed HWP data.
        
        Args:
            parsed_content: Parsed HWP content
            include_metadata: Include document metadata
            include_structure: Preserve document structure
            include_statistics: Include text statistics
            
        Returns:
            Structured content dictionary
        """
        result = {
            "version": "1.0",
            "extracted_at": datetime.now(timezone.utc).isoformat(),
        }
        
        # Extract metadata
        if include_metadata:
            result["metadata"] = self._extract_metadata(parsed_content)
        
        # Extract main content
        if include_structure:
            result["structure"] = self._extract_structure(parsed_content)
            result["paragraphs"] = self._extract_paragraphs(parsed_content)
            result["tables"] = self._extract_tables(parsed_content)
            result["lists"] = self._extract_lists(parsed_content)
            result["headings"] = self._extract_headings(parsed_content)
        
        # Extract plain text
        result["text"] = self._extract_plain_text(parsed_content)
        
        # Calculate statistics
        if include_statistics:
            result["statistics"] = self._calculate_statistics(result)
        
        return result
    
    def _extract_metadata(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Extract document metadata."""
        metadata = content.get("metadata", {})
        
        # Standardize metadata fields
        return {
            "title": metadata.get("title", ""),
            "author": metadata.get("author", ""),
            "subject": metadata.get("subject", ""),
            "keywords": metadata.get("keywords", ""),
            "created_date": metadata.get("created_date", ""),
            "modified_date": metadata.get("modified_date", ""),
            "creator": metadata.get("creator", "HWP"),
            "language": metadata.get("language", "ko"),
            "page_count": metadata.get("page_count", 0),
        }
    
    def _extract_structure(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Extract document structure information."""
        structure = {
            "type": "document",
            "sections": [],
            "hierarchy": []
        }
        
        # Analyze document structure
        paragraphs = content.get("paragraphs", [])
        current_section = None
        section_stack = []
        
        for i, para in enumerate(paragraphs):
            if isinstance(para, dict):
                para_text = para.get("text", "")
                para_style = para.get("style", {})
                
                # Detect headings based on style or pattern
                if self._is_heading(para_text, para_style):
                    level = self._get_heading_level(para_text, para_style)
                    section = {
                        "type": "heading",
                        "level": level,
                        "text": para_text,
                        "index": i
                    }
                    
                    # Update hierarchy
                    while section_stack and section_stack[-1]["level"] >= level:
                        section_stack.pop()
                    
                    if section_stack:
                        section["parent"] = section_stack[-1]["index"]
                    
                    section_stack.append(section)
                    structure["sections"].append(section)
        
        # Build hierarchy tree
        structure["hierarchy"] = self._build_hierarchy(structure["sections"])
        
        return structure
    
    def _extract_paragraphs(self, content: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract paragraphs with context."""
        paragraphs = []
        raw_paragraphs = content.get("paragraphs", [])
        
        for i, para in enumerate(raw_paragraphs):
            if isinstance(para, dict):
                para_dict = {
                    "index": i,
                    "text": para.get("text", ""),
                    "type": self._classify_paragraph(para),
                    "style": para.get("style", {}),
                    "char_count": len(para.get("text", "")),
                    "word_count": len(para.get("text", "").split()),
                }
                
                # Add semantic tags
                para_dict["tags"] = self._tag_paragraph(para_dict["text"])
                
                paragraphs.append(para_dict)
            elif isinstance(para, str):
                paragraphs.append({
                    "index": i,
                    "text": para,
                    "type": "normal",
                    "char_count": len(para),
                    "word_count": len(para.split()),
                    "tags": self._tag_paragraph(para)
                })
        
        return paragraphs
    
    def _extract_tables(self, content: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract tables with structure preserved."""
        tables = []
        raw_tables = content.get("tables", [])
        
        # Also check for tables in paragraphs (HWP format with <> delimiters)
        paragraphs = content.get("paragraphs", [])
        for para in paragraphs:
            text = para.get("text", "") if isinstance(para, dict) else para
            if self._is_table_text(text):
                parsed_table = self._parse_table_from_text(text)
                if parsed_table:
                    tables.append(parsed_table)
        
        # Process existing tables
        for i, table in enumerate(raw_tables):
            table_dict = {
                "index": i,
                "rows": [],
                "row_count": 0,
                "col_count": 0,
                "cells": []
            }
            
            if isinstance(table, dict):
                rows = table.get("rows", [])
                table_dict["row_count"] = len(rows)
                
                # Process rows
                for row_idx, row in enumerate(rows):
                    if row:
                        table_dict["col_count"] = max(table_dict["col_count"], len(row))
                        processed_row = []
                        
                        for col_idx, cell in enumerate(row):
                            cell_data = {
                                "row": row_idx,
                                "col": col_idx,
                                "text": str(cell),
                                "type": self._classify_cell(cell, row_idx, col_idx)
                            }
                            processed_row.append(cell_data["text"])
                            table_dict["cells"].append(cell_data)
                        
                        table_dict["rows"].append(processed_row)
                
                # Extract table summary
                table_dict["summary"] = self._summarize_table(table_dict)
            
            tables.append(table_dict)
        
        return tables
    
    def _extract_lists(self, content: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract lists from content."""
        lists = []
        paragraphs = content.get("paragraphs", [])
        
        current_list = None
        list_pattern = re.compile(r'^[\s]*[•·▪▫◦‣⁃\-\*]\s*|^[\s]*\d+[\.\)]\s*|^[\s]*[가-힣][\.\)]\s*')
        
        for i, para in enumerate(paragraphs):
            text = para.get("text", "") if isinstance(para, dict) else para
            
            if list_pattern.match(text):
                # This is a list item
                if not current_list:
                    current_list = {
                        "type": self._detect_list_type(text),
                        "items": [],
                        "start_index": i
                    }
                
                current_list["items"].append({
                    "text": list_pattern.sub('', text).strip(),
                    "level": self._detect_list_level(text),
                    "index": len(current_list["items"]),
                    "original": text
                })
            else:
                # Not a list item
                if current_list:
                    current_list["end_index"] = i - 1
                    lists.append(current_list)
                    current_list = None
        
        # Handle list at end of document
        if current_list:
            current_list["end_index"] = len(paragraphs) - 1
            lists.append(current_list)
        
        return lists
    
    def _extract_headings(self, content: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract headings with hierarchy."""
        headings = []
        paragraphs = content.get("paragraphs", [])
        
        for i, para in enumerate(paragraphs):
            text = para.get("text", "") if isinstance(para, dict) else para
            style = para.get("style", {}) if isinstance(para, dict) else {}
            
            if self._is_heading(text, style):
                headings.append({
                    "text": text,
                    "level": self._get_heading_level(text, style),
                    "index": i,
                    "type": self._classify_heading(text)
                })
        
        return headings
    
    def _extract_plain_text(self, content: Dict[str, Any]) -> str:
        """Extract plain text for simple analysis."""
        text_parts = []
        
        # From paragraphs
        paragraphs = content.get("paragraphs", [])
        for para in paragraphs:
            if isinstance(para, dict):
                text_parts.append(para.get("text", ""))
            else:
                text_parts.append(str(para))
        
        # From tables (simplified)
        tables = content.get("tables", [])
        for table in tables:
            if isinstance(table, dict):
                rows = table.get("rows", [])
                for row in rows:
                    text_parts.append(" | ".join(str(cell) for cell in row))
        
        # From raw text if available
        if "text" in content:
            text_parts.append(content["text"])
        
        return "\n\n".join(filter(None, text_parts))
    
    def _calculate_statistics(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate text statistics for analysis."""
        text = extracted_data.get("text", "")
        paragraphs = extracted_data.get("paragraphs", [])
        tables = extracted_data.get("tables", [])
        
        # Basic statistics
        stats = {
            "char_count": len(text),
            "char_count_no_spaces": len(text.replace(" ", "").replace("\n", "")),
            "word_count": len(text.split()),
            "line_count": text.count("\n") + 1,
            "paragraph_count": len(paragraphs),
            "table_count": len(tables),
            "list_count": len(extracted_data.get("lists", [])),
            "heading_count": len(extracted_data.get("headings", [])),
        }
        
        # Language detection (simple heuristic for Korean)
        korean_chars = len(re.findall(r'[가-힣]', text))
        english_chars = len(re.findall(r'[a-zA-Z]', text))
        stats["korean_ratio"] = korean_chars / max(len(text), 1)
        stats["english_ratio"] = english_chars / max(len(text), 1)
        
        # Sentence statistics
        sentences = re.split(r'[.!?]+', text)
        stats["sentence_count"] = len([s for s in sentences if s.strip()])
        stats["avg_sentence_length"] = (
            sum(len(s.split()) for s in sentences if s.strip()) / 
            max(stats["sentence_count"], 1)
        )
        
        # Paragraph statistics
        if paragraphs:
            para_lengths = [p.get("word_count", 0) for p in paragraphs]
            stats["avg_paragraph_length"] = sum(para_lengths) / len(para_lengths)
            stats["max_paragraph_length"] = max(para_lengths)
            stats["min_paragraph_length"] = min(para_lengths)
        
        return stats
    
    def to_markdown(self, parsed_content: Dict[str, Any], include_metadata: bool = True) -> str:
        """
        Convert parsed content to Markdown format.
        
        Args:
            parsed_content: Parsed HWP content
            include_metadata: Include metadata as YAML front matter
            
        Returns:
            Markdown formatted string
        """
        parts = []
        
        # Add metadata as YAML front matter
        if include_metadata:
            metadata = self._extract_metadata(parsed_content)
            if any(metadata.values()):
                parts.append("---")
                for key, value in metadata.items():
                    if value:
                        parts.append(f"{key}: {value}")
                parts.append("---")
                parts.append("")
        
        # Process content
        paragraphs = parsed_content.get("paragraphs", [])
        tables = parsed_content.get("tables", [])
        
        # Track table positions
        table_positions = {}
        for i, table in enumerate(tables):
            if isinstance(table, dict) and "position" in table:
                table_positions[table["position"]] = i
        
        # Process paragraphs and insert tables at appropriate positions
        for i, para in enumerate(paragraphs):
            text = para.get("text", "") if isinstance(para, dict) else para
            style = para.get("style", {}) if isinstance(para, dict) else {}
            
            # Check if this is a heading
            if self._is_heading(text, style):
                level = self._get_heading_level(text, style)
                parts.append(f"{'#' * level} {text}")
            else:
                # Regular paragraph
                parts.append(text)
            
            # Check if there's a table after this paragraph
            if i in table_positions:
                table_md = self._table_to_markdown(tables[table_positions[i]])
                parts.append("")
                parts.append(table_md)
            
            parts.append("")
        
        # Add any remaining tables
        for i, table in enumerate(tables):
            if i not in table_positions.values():
                parts.append(self._table_to_markdown(table))
                parts.append("")
        
        return "\n".join(parts).strip()
    
    def _table_to_markdown(self, table: Dict[str, Any]) -> str:
        """Convert table to markdown format."""
        if not isinstance(table, dict):
            return ""
        
        rows = table.get("rows", [])
        if not rows:
            return ""
        
        md_lines = []
        
        # Add header row
        if rows:
            md_lines.append("| " + " | ".join(str(cell) for cell in rows[0]) + " |")
            md_lines.append("|" + "---|" * len(rows[0]))
            
            # Add data rows
            for row in rows[1:]:
                md_lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
        
        return "\n".join(md_lines)
    
    # Helper methods
    def _is_heading(self, text: str, style: Dict[str, Any]) -> bool:
        """Detect if text is a heading."""
        # Check style hints
        if style.get("is_heading"):
            return True
        
        # Check patterns
        heading_patterns = [
            r'^제\s*\d+\s*[장절조항]',  # 제1장, 제2절 등
            r'^\d+\.\s+',  # 1. 2. 3.
            r'^[가-힣]\.\s+',  # 가. 나. 다.
            r'^Chapter\s+\d+',  # Chapter 1
            r'^Section\s+\d+',  # Section 1
            r'^<[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫⅰⅱⅲⅳⅴⅵⅶⅷⅸⅹ]+>',  # <Ⅰ>, <Ⅱ> 등 로마 숫자
            r'^[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫⅰⅱⅲⅳⅴⅵⅶⅷⅸⅹ]+\.',  # Ⅰ. Ⅱ. 등
            r'^[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫⅰⅱⅲⅳⅴⅵⅶⅷⅸⅹ]+\s+',  # Ⅰ Ⅱ 등
        ]
        
        return any(re.match(pattern, text.strip()) for pattern in heading_patterns)
    
    def _get_heading_level(self, text: str, style: Dict[str, Any]) -> int:
        """Determine heading level (1-6)."""
        # From style
        if "level" in style:
            return min(max(style["level"], 1), 6)
        
        # From patterns
        if re.match(r'^제\s*\d+\s*장', text):
            return 1
        elif re.match(r'^제\s*\d+\s*절', text):
            return 2
        elif re.match(r'^<[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ]+>', text):  # 대문자 로마 숫자
            return 1
        elif re.match(r'^[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ]+\.', text):  # 대문자 로마 숫자 with period
            return 1
        elif re.match(r'^<[ⅰⅱⅲⅳⅴⅵⅶⅷⅸⅹ]+>', text):  # 소문자 로마 숫자
            return 2
        elif re.match(r'^\d+\.\s+', text):
            return 2
        elif re.match(r'^[가-힣]\.\s+', text):
            return 3
        
        return 2  # Default
    
    def _classify_paragraph(self, para: Dict[str, Any]) -> str:
        """Classify paragraph type."""
        text = para.get("text", "")
        
        if self._is_heading(text, para.get("style", {})):
            return "heading"
        elif re.match(r'^[\s]*[•·▪▫◦‣⁃\-\*]\s+', text):
            return "list_item"
        elif re.match(r'^[\s]*\d+[\.\)]\s+', text):
            return "numbered_list"
        elif len(text) < 50 and text.isupper():
            return "title"
        else:
            return "normal"
    
    def _tag_paragraph(self, text: str) -> List[str]:
        """Generate semantic tags for paragraph."""
        tags = []
        
        # Content type tags
        if re.search(r'\d{4}[-/년]\s*\d{1,2}[-/월]\s*\d{1,2}', text):
            tags.append("date")
        if re.search(r'[\w\.-]+@[\w\.-]+', text):
            tags.append("email")
        if re.search(r'https?://\S+', text):
            tags.append("url")
        if re.search(r'\d{2,3}-\d{3,4}-\d{4}', text):
            tags.append("phone")
        if re.search(r'[₩$¥€£]\s*[\d,]+', text):
            tags.append("currency")
        
        # Length tags
        word_count = len(text.split())
        if word_count < 10:
            tags.append("short")
        elif word_count > 100:
            tags.append("long")
        
        return tags
    
    def _classify_cell(self, cell: Any, row: int, col: int) -> str:
        """Classify table cell type."""
        if row == 0:
            return "header"
        elif col == 0:
            return "row_header"
        else:
            return "data"
    
    def _summarize_table(self, table: Dict[str, Any]) -> str:
        """Generate table summary."""
        rows = table.get("row_count", 0)
        cols = table.get("col_count", 0)
        
        return f"Table with {rows} rows and {cols} columns"
    
    def _detect_list_type(self, text: str) -> str:
        """Detect list type from text."""
        if re.match(r'^[\s]*\d+[\.\)]\s+', text):
            return "ordered"
        elif re.match(r'^[\s]*[가-힣][\.\)]\s+', text):
            return "korean_ordered"
        else:
            return "unordered"
    
    def _detect_list_level(self, text: str) -> int:
        """Detect list indentation level."""
        leading_spaces = len(text) - len(text.lstrip())
        return (leading_spaces // 2) + 1
    
    def _classify_heading(self, text: str) -> str:
        """Classify heading type."""
        if re.match(r'^제\s*\d+\s*[장절조항]', text):
            return "legal"
        elif re.match(r'^Chapter|Section', text, re.I):
            return "academic"
        else:
            return "general"
    
    def _build_hierarchy(self, sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build hierarchical structure from flat sections."""
        if not sections:
            return []
        
        # Create a tree structure
        hierarchy = []
        stack = []
        
        for section in sections:
            node = {
                "text": section["text"],
                "level": section["level"],
                "index": section["index"],
                "children": []
            }
            
            # Find parent
            while stack and stack[-1]["level"] >= node["level"]:
                stack.pop()
            
            if stack:
                stack[-1]["children"].append(node)
            else:
                hierarchy.append(node)
            
            stack.append(node)
        
        return hierarchy
    
    def _is_table_text(self, text: str) -> bool:
        """Check if text contains table data with <> delimiters."""
        # Count occurrences of <> patterns
        delimiter_count = text.count('><')
        # If we have multiple cells (at least 2 delimiters in a line)
        lines = text.strip().split('\n')
        for line in lines:
            if line.count('><') >= 2:
                return True
        return False
    
    def _parse_table_from_text(self, text: str) -> Optional[Dict[str, Any]]:
        """Parse table from text with <> delimiters."""
        lines = text.strip().split('\n')
        table_lines = []
        
        # Find lines that contain table data
        for line in lines:
            if '<' in line and '>' in line:
                # Extract cells from the line
                cells = []
                current_cell = ""
                in_cell = False
                
                for char in line:
                    if char == '<':
                        in_cell = True
                        current_cell = ""
                    elif char == '>':
                        in_cell = False
                        cells.append(current_cell.strip())
                    elif in_cell:
                        current_cell += char
                
                if cells:
                    table_lines.append(cells)
        
        if not table_lines:
            return None
        
        # Create table structure
        table = {
            "index": 0,
            "row_count": len(table_lines),
            "col_count": max(len(row) for row in table_lines) if table_lines else 0,
            "headers": [],
            "rows": [],
            "cells": [],
            "structured_data": []
        }
        
        # First row is usually headers
        if table_lines:
            table["headers"] = table_lines[0]
            
            # Process data rows
            for row_idx, row in enumerate(table_lines[1:], 1):
                # Create structured row data
                row_data = {}
                for col_idx, cell in enumerate(row):
                    if col_idx < len(table["headers"]):
                        header = table["headers"][col_idx]
                        row_data[header] = cell
                    
                    # Add to cells list
                    table["cells"].append({
                        "row": row_idx,
                        "col": col_idx,
                        "text": cell,
                        "type": "header" if row_idx == 0 else "data"
                    })
                
                table["rows"].append(row)
                if row_data:
                    table["structured_data"].append(row_data)
        
        # Add summary
        table["summary"] = f"Table with {table['row_count']} rows and {table['col_count']} columns"
        
        return table