"""
PyHWP parser implementation.
Uses pyhwp library for parsing HWP files.
"""
import structlog
from typing import Dict, Any, List
import subprocess
import tempfile
import json
import os

logger = structlog.get_logger()


def parse(file_path: str) -> Dict[str, Any]:
    """
    Parse HWP file using pyhwp library.
    
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
        # Method 1: Use pyhwp command-line tools if available
        text = extract_with_cli(file_path)
        if text:
            result["text"] = text
            # Split into paragraphs
            paragraphs = text.split('\n\n')
            for i, para in enumerate(paragraphs):
                if para.strip():
                    result["paragraphs"].append({
                        "text": para.strip(),
                        "index": i
                    })
            return result
        
        # Method 2: Direct Python API
        try:
            import pyhwp
            # Try to use pyhwp API directly
            result = parse_with_api(file_path)
        except ImportError:
            logger.warning("pyhwp Python API not available, falling back")
            
    except Exception as e:
        logger.error("Error parsing HWP with pyhwp", error=str(e))
        raise
    
    return result


def extract_with_cli(file_path: str) -> str:
    """
    Extract text using pyhwp command-line tools.
    
    Args:
        file_path: Path to HWP file
        
    Returns:
        Extracted text or None if failed
    """
    try:
        # Try hwp5proc command
        cmd = ["hwp5proc", "cat", "--vstreams", file_path, "PrvText.utf8"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0 and result.stdout:
            logger.info("Successfully extracted text with hwp5proc")
            return result.stdout
        
        # Try alternative: extract PrvText and convert encoding
        cmd = ["hwp5proc", "cat", file_path, "PrvText"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=30
        )
        
        if result.returncode == 0 and result.stdout:
            # Convert from UTF-16LE to UTF-8
            try:
                text = result.stdout.decode('utf-16le', errors='ignore')
                logger.info("Successfully extracted text with encoding conversion")
                return text
            except Exception as e:
                logger.warning("Failed to decode text", error=str(e))
                
    except subprocess.TimeoutExpired:
        logger.warning("Command timed out")
    except FileNotFoundError:
        logger.warning("hwp5proc command not found")
    except Exception as e:
        logger.warning("CLI extraction failed", error=str(e))
    
    return None


def parse_with_api(file_path: str) -> Dict[str, Any]:
    """
    Parse HWP file using pyhwp Python API.
    
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
        import pyhwp
        from pyhwp.hwp5 import filestructure
        
        # Open HWP file
        hwp = filestructure.Hwp5File(file_path)
        
        # Extract metadata
        if hasattr(hwp, 'header'):
            header = hwp.header
            result["metadata"] = {
                "version": getattr(header, 'version', '5.0'),
                "flags": getattr(header, 'flags', {})
            }
        
        # Extract document info
        if 'DocInfo' in hwp:
            docinfo = hwp['DocInfo']
            # Parse document information stream
            result["metadata"].update(parse_docinfo(docinfo))
        
        # Extract body text
        text_parts = []
        section_count = 0
        
        # Iterate through BodyText sections
        for name in hwp.list_streams():
            if name.startswith('BodyText/Section'):
                section_count += 1
                try:
                    section_data = hwp[name].read()
                    # Extract text from section
                    section_text = extract_section_text(section_data)
                    if section_text:
                        text_parts.append(section_text)
                        result["structure"]["sections"].append({
                            "section_id": name,
                            "text_length": len(section_text),
                            "paragraph_count": len(section_text.split('\n\n'))
                        })
                except Exception as e:
                    logger.warning(f"Failed to process {name}", error=str(e))
        
        result["structure"]["total_sections"] = section_count
        result["text"] = "\n\n".join(text_parts)
        
        # Create paragraphs
        if result["text"]:
            paragraphs = result["text"].split('\n\n')
            for i, para in enumerate(paragraphs):
                if para.strip():
                    result["paragraphs"].append({
                        "text": para.strip(),
                        "index": i
                    })
        
        hwp.close()
        
    except Exception as e:
        logger.error("Failed to parse with pyhwp API", error=str(e))
        raise
    
    return result


def parse_docinfo(docinfo_stream) -> Dict[str, Any]:
    """Parse DocInfo stream for metadata."""
    metadata = {}
    
    try:
        # DocInfo contains document properties
        # This is a simplified extraction - actual format is complex
        data = docinfo_stream.read()
        
        # Try to find title, author, etc. in the binary data
        # This is a heuristic approach
        text_parts = []
        for i in range(0, len(data) - 1, 2):
            # Try UTF-16LE decoding
            try:
                char = data[i:i+2].decode('utf-16le', errors='ignore')
                if char.isprintable():
                    text_parts.append(char)
            except:
                pass
        
        # Join and split by null characters
        text = ''.join(text_parts)
        fields = text.split('\x00')
        
        # Common patterns in DocInfo
        for i, field in enumerate(fields):
            field = field.strip()
            if field:
                # Try to identify metadata fields
                if i == 0 and len(field) < 100:
                    metadata["title"] = field
                elif '@' in field and len(field) < 50:
                    metadata["author"] = field.split('@')[0]
                elif field.startswith('20') and len(field) == 8:
                    # Possible date in YYYYMMDD format
                    metadata["date"] = field
                    
    except Exception as e:
        logger.debug("Failed to parse DocInfo", error=str(e))
    
    return metadata


def extract_section_text(section_data: bytes) -> str:
    """Extract text from section data."""
    text_parts = []
    
    # HWP sections can be compressed
    try:
        import zlib
        # Try to decompress
        decompressed = zlib.decompress(section_data, -zlib.MAX_WBITS)
        section_data = decompressed
    except:
        # Not compressed or decompression failed
        pass
    
    # Extract text with multiple encoding attempts
    encodings = ['utf-16le', 'utf-8', 'cp949', 'euc-kr']
    
    for encoding in encodings:
        try:
            # Remove null bytes
            cleaned = section_data.replace(b'\x00\x00', b'\n')
            text = cleaned.decode(encoding, errors='ignore')
            
            # Clean up
            lines = []
            for line in text.split('\n'):
                line = line.strip()
                # Filter printable content
                if line and sum(c.isprintable() for c in line) > len(line) * 0.5:
                    lines.append(line)
            
            if lines:
                return '\n'.join(lines)
                
        except Exception:
            continue
    
    return ""