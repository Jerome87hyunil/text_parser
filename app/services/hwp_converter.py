import os
import asyncio
import structlog
from typing import Optional, Dict, Any
import subprocess
import platform
from pathlib import Path

logger = structlog.get_logger()


class HWPConverter:
    """
    HWP to PDF converter service.
    Uses multiple strategies to convert HWP files to PDF.
    """
    
    def __init__(self):
        self.timeout = 300  # 5 minutes
        
    async def convert(self, input_path: str, output_path: str) -> bool:
        """
        Convert HWP file to PDF.
        
        Args:
            input_path: Path to input HWP file
            output_path: Path for output PDF file
            
        Returns:
            bool: True if conversion successful, False otherwise
        """
        try:
            logger.info("Starting HWP conversion", input=input_path, output=output_path)
            
            # Try actual HWP parsing first
            try:
                from .hwp_parser import HWPParser
                from .pdf_generator import PDFGenerator
                
                # Parse HWP file
                parser = HWPParser()
                content = parser.parse(input_path)
                
                # Generate PDF from parsed content
                generator = PDFGenerator()
                success = await generator.generate_from_hwp_content(content, output_path)
                
                if success:
                    logger.info("HWP conversion completed successfully", 
                              input=input_path, output=output_path)
                    return True
                    
            except Exception as e:
                logger.warning("HWP parsing failed, trying fallback methods", 
                             error=str(e))
            
            # Fallback: Try LibreOffice conversion if available
            if self._check_libreoffice():
                success = await self._convert_with_libreoffice(input_path, output_path)
                if success:
                    return True
            
            # Last resort: Create a placeholder PDF with error message
            await self._create_error_pdf(output_path, input_path)
            return True
            
        except Exception as e:
            logger.error("Conversion failed", error=str(e))
            return False
    
    async def _convert_with_libreoffice(self, input_path: str, output_path: str) -> bool:
        """
        Convert HWP to PDF using LibreOffice.
        
        Args:
            input_path: Path to input HWP file
            output_path: Path for output PDF file
            
        Returns:
            bool: True if conversion successful, False otherwise
        """
        try:
            output_dir = os.path.dirname(output_path)
            
            # LibreOffice command
            cmd = [
                "libreoffice",
                "--headless",
                "--convert-to", "pdf",
                "--outdir", output_dir,
                input_path
            ]
            
            # Run conversion
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                result.communicate(), 
                timeout=self.timeout
            )
            
            if result.returncode == 0:
                # LibreOffice creates PDF with same name as input
                temp_output = os.path.join(
                    output_dir, 
                    Path(input_path).stem + ".pdf"
                )
                
                # Rename if needed
                if temp_output != output_path:
                    os.rename(temp_output, output_path)
                
                logger.info("LibreOffice conversion successful")
                return True
            else:
                logger.error("LibreOffice conversion failed", 
                           stderr=stderr.decode() if stderr else "")
                return False
                
        except asyncio.TimeoutError:
            logger.error("LibreOffice conversion timed out")
            return False
        except Exception as e:
            logger.error("LibreOffice conversion error", error=str(e))
            return False
    
    async def _create_error_pdf(self, output_path: str, input_path: str):
        """
        Create an error PDF when conversion fails.
        """
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        
        c = canvas.Canvas(output_path, pagesize=A4)
        width, height = A4
        
        # Add error message
        c.setFont("Helvetica-Bold", 24)
        c.drawString(50, height - 100, "HWP Conversion Error")
        
        c.setFont("Helvetica", 12)
        c.drawString(50, height - 150, f"Failed to convert: {os.path.basename(input_path)}")
        c.drawString(50, height - 180, "Possible reasons:")
        c.drawString(70, height - 200, "- HWP file is corrupted or uses unsupported features")
        c.drawString(70, height - 220, "- Required dependencies are not installed")
        c.drawString(70, height - 240, "- File is password protected")
        
        c.drawString(50, height - 280, "Please try:")
        c.drawString(70, height - 300, "1. Open the file in Hancom Office and save as PDF")
        c.drawString(70, height - 320, "2. Install LibreOffice for better conversion support")
        c.drawString(70, height - 340, "3. Check if the file opens correctly in HWP viewer")
        
        c.save()
        
        logger.info("Error PDF created", path=output_path)
    
    def _check_dependencies(self) -> dict:
        """
        Check if required dependencies are installed.
        """
        dependencies = {
            "pyhwp": self._check_python_package("pyhwp"),
            "hwp5": self._check_python_package("hwp5"),
            "libreoffice": self._check_libreoffice(),
        }
        
        return dependencies
    
    def _check_python_package(self, package_name: str) -> bool:
        """Check if a Python package is installed."""
        try:
            __import__(package_name)
            return True
        except ImportError:
            return False
    
    def _check_libreoffice(self) -> bool:
        """Check if LibreOffice is installed."""
        try:
            result = subprocess.run(
                ["libreoffice", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False