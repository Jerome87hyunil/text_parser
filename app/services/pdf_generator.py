"""
PDF Generator for creating PDFs from parsed HWP content.
Optimized for Korean text handling.
"""
import structlog
from typing import Dict, Any, List
from pathlib import Path
import os

logger = structlog.get_logger()


class PDFGenerator:
    """
    Generate PDF files from parsed HWP content.
    Uses fpdf2 for better Unicode and Korean font support.
    """
    
    def __init__(self):
        self.default_font_path = None
        self._init_fonts()
    
    def _init_fonts(self):
        """Initialize font paths for Korean support."""
        # Common Korean font paths
        font_candidates = [
            # macOS
            "/System/Library/Fonts/AppleSDGothicNeo.ttc",
            "/Library/Fonts/NanumGothic.ttf",
            "/Library/Fonts/NanumMyeongjo.ttf",
            # Linux
            "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
            "/usr/share/fonts/truetype/nanum/NanumMyeongjo.ttf",
            "/usr/share/fonts/truetype/unfonts-core/UnBatang.ttf",
            # Windows
            "C:/Windows/Fonts/malgun.ttf",
            "C:/Windows/Fonts/batang.ttc",
        ]
        
        # Find first available font
        for font_path in font_candidates:
            if os.path.exists(font_path):
                self.default_font_path = font_path
                logger.info(f"Found Korean font: {font_path}")
                break
    
    async def generate_from_hwp_content(self, content: Dict[str, Any], output_path: str) -> bool:
        """
        Generate PDF from parsed HWP content.
        
        Args:
            content: Parsed HWP content dictionary
            output_path: Path for output PDF file
            
        Returns:
            bool: True if generation successful, False otherwise
        """
        try:
            # Use fpdf2 for better Korean support
            try:
                from fpdf import FPDF
                return await self._generate_with_fpdf2(content, output_path)
            except ImportError:
                logger.warning("fpdf2 not available, falling back to reportlab")
                return await self._generate_with_reportlab(content, output_path)
                
        except Exception as e:
            logger.error("PDF generation failed", error=str(e))
            return False
    
    async def _generate_with_fpdf2(self, content: Dict[str, Any], output_path: str) -> bool:
        """Generate PDF using fpdf2 library."""
        from fpdf import FPDF
        
        try:
            pdf = FPDF()
            pdf.set_auto_page_break(auto=True, margin=15)
            
            # Configure for better Unicode support
            pdf.set_doc_option('core_fonts_encoding', 'utf-8')
            
            # Add Korean font if available
            font_added = False
            if self.default_font_path:
                try:
                    # Add font with Unicode support
                    pdf.add_font(fname=self.default_font_path, uni=True)
                    font_family = Path(self.default_font_path).stem
                    pdf.set_font(font_family, size=12)
                    font_added = True
                    logger.info(f"Korean font added successfully: {font_family}")
                except Exception as e:
                    logger.warning(f"Failed to add Korean font: {e}")
            
            if not font_added:
                # Try DejaVu font as fallback (better Unicode support)
                try:
                    # Try to find DejaVu font
                    dejavu_paths = [
                        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                        "/System/Library/Fonts/Helvetica.ttc",
                        "C:/Windows/Fonts/arial.ttf"
                    ]
                    for dejavu_path in dejavu_paths:
                        if os.path.exists(dejavu_path):
                            pdf.add_font(fname=dejavu_path, uni=True)
                            pdf.set_font(Path(dejavu_path).stem, size=12)
                            font_added = True
                            logger.info(f"Fallback font added: {dejavu_path}")
                            break
                except Exception as e:
                    logger.warning(f"Failed to add fallback font: {e}")
            
            if not font_added:
                # Last resort: use built-in font
                pdf.set_font("helvetica", size=12)
                logger.warning("Using built-in font - Korean text may not display correctly")
            
            # Add metadata if available
            metadata = content.get("metadata", {})
            if metadata.get("title"):
                pdf.set_title(metadata["title"])
            if metadata.get("author"):
                pdf.set_author(metadata["author"])
            if metadata.get("subject"):
                pdf.set_subject(metadata["subject"])
            
            # Add content
            pdf.add_page()
            
            # Add title if available
            if metadata.get("title"):
                pdf.set_font_size(16)
                pdf.cell(0, 10, metadata["title"], new_x="LMARGIN", new_y="NEXT", align="C")
                pdf.ln(10)
                pdf.set_font_size(12)
            
            # Add paragraphs
            paragraphs = content.get("paragraphs", [])
            for para in paragraphs:
                if isinstance(para, dict):
                    text = para.get("text", "")
                else:
                    text = str(para)
                
                if text.strip():
                    # Use multi_cell for better text wrapping
                    pdf.multi_cell(0, 10, text, new_x="LMARGIN", new_y="NEXT")
                    pdf.ln(5)
            
            # If no paragraphs, try raw text
            if not paragraphs and content.get("text"):
                pdf.multi_cell(0, 10, content["text"], new_x="LMARGIN", new_y="NEXT")
            
            # Add tables if available
            tables = content.get("tables", [])
            for table_data in tables:
                self._add_table_fpdf2(pdf, table_data)
            
            # Save PDF
            pdf.output(output_path)
            logger.info("PDF generated successfully with fpdf2", path=output_path)
            return True
            
        except Exception as e:
            logger.error("fpdf2 PDF generation failed", error=str(e))
            return False
    
    async def _generate_with_reportlab(self, content: Dict[str, Any], output_path: str) -> bool:
        """Generate PDF using ReportLab library."""
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import inch
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        
        try:
            # Create PDF document
            doc = SimpleDocTemplate(output_path, pagesize=A4)
            story = []
            styles = getSampleStyleSheet()
            
            # Try to register Korean font
            korean_font_registered = False
            if self.default_font_path:
                try:
                    font_name = Path(self.default_font_path).stem
                    pdfmetrics.registerFont(TTFont(font_name, self.default_font_path))
                    korean_style = ParagraphStyle(
                        'Korean',
                        parent=styles['Normal'],
                        fontName=font_name,
                        fontSize=12,
                        leading=18
                    )
                    korean_font_registered = True
                except Exception as e:
                    logger.warning(f"Failed to register Korean font: {e}")
            
            # Use appropriate style
            para_style = korean_style if korean_font_registered else styles['Normal']
            
            # Add metadata as title if available
            metadata = content.get("metadata", {})
            if metadata.get("title"):
                title_style = ParagraphStyle(
                    'CustomTitle',
                    parent=styles['Title'],
                    fontName=para_style.fontName
                )
                story.append(Paragraph(metadata["title"], title_style))
                story.append(Spacer(1, 0.5*inch))
            
            # Add paragraphs
            paragraphs = content.get("paragraphs", [])
            for para in paragraphs:
                if isinstance(para, dict):
                    text = para.get("text", "")
                else:
                    text = str(para)
                
                if text.strip():
                    # Escape special characters for ReportLab
                    text = self._escape_text_for_reportlab(text)
                    story.append(Paragraph(text, para_style))
                    story.append(Spacer(1, 0.2*inch))
            
            # If no paragraphs, try raw text
            if not paragraphs and content.get("text"):
                text = self._escape_text_for_reportlab(content["text"])
                for line in text.split('\n'):
                    if line.strip():
                        story.append(Paragraph(line, para_style))
                        story.append(Spacer(1, 0.1*inch))
            
            # Add tables if available
            tables = content.get("tables", [])
            for table_data in tables:
                table_element = self._create_table_reportlab(table_data, para_style)
                if table_element:
                    story.append(table_element)
                    story.append(Spacer(1, 0.3*inch))
            
            # Build PDF
            doc.build(story)
            logger.info("PDF generated successfully with ReportLab", path=output_path)
            return True
            
        except Exception as e:
            logger.error("ReportLab PDF generation failed", error=str(e))
            return False
    
    def _escape_text_for_reportlab(self, text: str) -> str:
        """Escape special characters for ReportLab."""
        # ReportLab uses XML-like parsing for paragraphs
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        return text
    
    def _add_table_fpdf2(self, pdf, table_data: Dict[str, Any]):
        """Add table to fpdf2 PDF."""
        rows = table_data.get("rows", [])
        if not rows:
            return
        
        # Simple table rendering
        for row in rows:
            for cell in row:
                pdf.cell(40, 10, str(cell)[:20], 1)  # Limit cell content
            pdf.ln()
    
    def _create_table_reportlab(self, table_data: Dict[str, Any], style):
        """Create table for ReportLab."""
        from reportlab.platypus import Table, TableStyle
        from reportlab.lib import colors
        
        rows = table_data.get("rows", [])
        if not rows:
            return None
        
        # Create table
        table = Table(rows)
        
        # Apply basic style
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), style.fontName),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        return table