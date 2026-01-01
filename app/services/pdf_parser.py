"""
PDF Parser implementation for text extraction.
"""
import structlog
import fitz  # PyMuPDF
import pdfplumber
from typing import Dict, Any, List, Optional
import os
import re

logger = structlog.get_logger()


class PDFParser:
    """Parser for PDF files using multiple strategies."""
    
    def parse(self, file_path: str) -> Dict[str, Any]:
        """
        Parse PDF file and extract content.
        
        Args:
            file_path: Path to PDF file
            
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
                "total_pages": 0
            }
        }
        
        # Try PyMuPDF first (faster and more reliable for text)
        try:
            result = self._parse_with_pymupdf(file_path)
            
            # Try to extract tables with pdfplumber
            tables = self._extract_tables_with_pdfplumber(file_path)
            if tables:
                result["tables"] = tables
                
        except Exception as e:
            logger.warning("PyMuPDF parsing failed, trying pdfplumber", error=str(e))
            # Fallback to pdfplumber
            try:
                result = self._parse_with_pdfplumber(file_path)
            except Exception as e2:
                logger.error("All PDF parsers failed", error=str(e2))
                raise
        
        return result
    
    def _parse_with_pymupdf(self, file_path: str) -> Dict[str, Any]:
        """Parse PDF using PyMuPDF (fitz).

        v1.1: 메모리 누수 방지를 위해 try/finally 추가
        """
        result = {
            "paragraphs": [],
            "tables": [],
            "images": [],
            "metadata": {},
            "text": "",
            "structure": {
                "sections": [],
                "total_pages": 0
            }
        }

        doc = None
        try:
            # Open PDF
            doc = fitz.open(file_path)
            result["structure"]["total_pages"] = len(doc)

            # Extract metadata
            metadata = doc.metadata
            if metadata:
                result["metadata"] = {
                    "title": metadata.get("title", ""),
                    "author": metadata.get("author", ""),
                    "subject": metadata.get("subject", ""),
                    "keywords": metadata.get("keywords", ""),
                    "creator": metadata.get("creator", ""),
                    "producer": metadata.get("producer", ""),
                    "created_date": str(metadata.get("creationDate", "")),
                    "modified_date": str(metadata.get("modDate", "")),
                }

            # Extract text from each page
            all_text = []
            paragraphs = []

            for page_num, page in enumerate(doc):
                # Extract text
                text = page.get_text()
                if text.strip():
                    all_text.append(text)

                    # Split into paragraphs
                    page_paragraphs = self._split_into_paragraphs(text)
                    for para in page_paragraphs:
                        if para.strip():
                            paragraphs.append({
                                "text": para.strip(),
                                "page": page_num + 1,
                                "style": {}
                            })

                # Add page info to structure
                result["structure"]["sections"].append({
                    "page": page_num + 1,
                    "text_length": len(text),
                    "paragraph_count": len(page_paragraphs)
                })

            result["text"] = "\n\n".join(all_text)
            result["paragraphs"] = paragraphs

        except Exception as e:
            logger.error("Error parsing PDF with PyMuPDF", error=str(e))
            raise
        finally:
            # 메모리 누수 방지: 항상 문서 닫기
            if doc is not None:
                try:
                    doc.close()
                except:
                    pass

        return result
    
    def _parse_with_pdfplumber(self, file_path: str) -> Dict[str, Any]:
        """Parse PDF using pdfplumber (better for tables)."""
        result = {
            "paragraphs": [],
            "tables": [],
            "images": [],
            "metadata": {},
            "text": "",
            "structure": {
                "sections": [],
                "total_pages": 0
            }
        }
        
        try:
            with pdfplumber.open(file_path) as pdf:
                result["structure"]["total_pages"] = len(pdf.pages)
                
                # Extract metadata
                if pdf.metadata:
                    result["metadata"] = {
                        "title": pdf.metadata.get("Title", ""),
                        "author": pdf.metadata.get("Author", ""),
                        "subject": pdf.metadata.get("Subject", ""),
                        "keywords": pdf.metadata.get("Keywords", ""),
                        "creator": pdf.metadata.get("Creator", ""),
                        "producer": pdf.metadata.get("Producer", ""),
                        "created_date": str(pdf.metadata.get("CreationDate", "")),
                        "modified_date": str(pdf.metadata.get("ModDate", "")),
                    }
                
                # Extract content from each page
                all_text = []
                paragraphs = []
                tables = []
                
                for page_num, page in enumerate(pdf.pages):
                    # Extract text
                    text = page.extract_text()
                    if text:
                        all_text.append(text)
                        
                        # Split into paragraphs
                        page_paragraphs = self._split_into_paragraphs(text)
                        for para in page_paragraphs:
                            if para.strip():
                                paragraphs.append({
                                    "text": para.strip(),
                                    "page": page_num + 1,
                                    "style": {}
                                })
                    
                    # Extract tables
                    page_tables = page.extract_tables()
                    for table_idx, table in enumerate(page_tables):
                        if table and len(table) > 0:
                            tables.append({
                                "page": page_num + 1,
                                "index": len(tables),
                                "rows": table,
                                "row_count": len(table),
                                "col_count": len(table[0]) if table else 0
                            })
                    
                    # Add page info to structure
                    result["structure"]["sections"].append({
                        "page": page_num + 1,
                        "text_length": len(text) if text else 0,
                        "paragraph_count": len(page_paragraphs),
                        "table_count": len(page_tables)
                    })
                
                result["text"] = "\n\n".join(all_text)
                result["paragraphs"] = paragraphs
                result["tables"] = tables
                
        except Exception as e:
            logger.error("Error parsing PDF with pdfplumber", error=str(e))
            raise
        
        return result
    
    def _extract_tables_with_pdfplumber(self, file_path: str) -> List[Dict[str, Any]]:
        """Extract tables specifically using pdfplumber."""
        tables = []
        
        try:
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    page_tables = page.extract_tables()
                    for table_idx, table in enumerate(page_tables):
                        if table and len(table) > 0:
                            # Process table to create structured data
                            processed_table = self._process_table(table)
                            processed_table["page"] = page_num + 1
                            processed_table["index"] = len(tables)
                            tables.append(processed_table)
        except Exception as e:
            logger.warning("Failed to extract tables with pdfplumber", error=str(e))
        
        return tables
    
    def _process_table(self, raw_table: List[List[str]]) -> Dict[str, Any]:
        """Process raw table data into structured format."""
        if not raw_table or len(raw_table) == 0:
            return {"rows": [], "row_count": 0, "col_count": 0}
        
        # Clean table data
        cleaned_rows = []
        for row in raw_table:
            cleaned_row = []
            for cell in row:
                # Clean cell content
                if cell is None:
                    cleaned_row.append("")
                else:
                    cleaned_row.append(str(cell).strip())
            cleaned_rows.append(cleaned_row)
        
        # Create structured table
        table = {
            "rows": cleaned_rows,
            "row_count": len(cleaned_rows),
            "col_count": len(cleaned_rows[0]) if cleaned_rows else 0,
            "headers": [],
            "structured_data": []
        }
        
        # Assume first row is headers
        if len(cleaned_rows) > 0:
            table["headers"] = cleaned_rows[0]
            
            # Create structured data
            for row_idx, row in enumerate(cleaned_rows[1:], 1):
                row_data = {}
                for col_idx, cell in enumerate(row):
                    if col_idx < len(table["headers"]):
                        header = table["headers"][col_idx]
                        if header:  # Only add if header is not empty
                            row_data[header] = cell
                
                if row_data:
                    table["structured_data"].append(row_data)
        
        return table
    
    def _split_into_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs based on multiple newlines or patterns."""
        if not text:
            return []
        
        # First, normalize line endings
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # Split by multiple newlines
        paragraphs = re.split(r'\n\s*\n', text)
        
        # Further split by common paragraph patterns
        result = []
        for para in paragraphs:
            # Check for numbered lists or bullet points
            if re.search(r'^\s*[\d\-•·▪▫◦‣⁃]\s', para, re.MULTILINE):
                # Split by line for lists
                lines = para.split('\n')
                current_item = []
                for line in lines:
                    if re.match(r'^\s*[\d\-•·▪▫◦‣⁃]\s', line):
                        if current_item:
                            result.append('\n'.join(current_item))
                        current_item = [line]
                    else:
                        current_item.append(line)
                if current_item:
                    result.append('\n'.join(current_item))
            else:
                # Regular paragraph
                result.append(para)
        
        return [p.strip() for p in result if p.strip()]


def parse(file_path: str) -> Dict[str, Any]:
    """
    Parse PDF file using PDFParser.
    
    Args:
        file_path: Path to PDF file
        
    Returns:
        Dict containing extracted content
    """
    parser = PDFParser()
    return parser.parse(file_path)