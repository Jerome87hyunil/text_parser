"""
OleFile-based HWP parser implementation.
Fallback parser when pyhwp/hwp5 are not available.
"""
import structlog
import olefile
from typing import Dict, Any
import zlib

logger = structlog.get_logger()


def parse(file_path: str) -> Dict[str, Any]:
    """
    Parse HWP file using olefile library.
    
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
        ole = olefile.OleFileIO(file_path)
        
        # Extract summary information
        if ole.exists("\\005HwpSummaryInformation"):
            try:
                summary = ole.getproperties("\\005HwpSummaryInformation")
                result["metadata"] = {
                    "title": summary.get(2, ""),
                    "subject": summary.get(3, ""),
                    "author": summary.get(4, ""),
                    "keywords": summary.get(5, ""),
                    "created": str(summary.get(12, "")),
                    "modified": str(summary.get(13, ""))
                }
            except Exception as e:
                logger.warning("Failed to extract metadata", error=str(e))
        
        # Try to extract text from BodyText sections
        text_parts = []
        seen_texts = set()  # Track unique texts to avoid duplicates
        
        # HWP stores text in BodyText/Section0, Section1, etc.
        section_count = 0
        for entry in ole.listdir():
            if len(entry) >= 2 and entry[0] == "BodyText" and entry[1].startswith("Section"):
                section_count += 1
                try:
                    stream_path = "/".join(entry)
                    data = ole.openstream(stream_path).read()
                    
                    # Try to decompress if compressed
                    section_text = None
                    try:
                        decompressed = zlib.decompress(data, -zlib.MAX_WBITS)
                        section_text = extract_text_from_data(decompressed)
                    except zlib.error:
                        # Data might not be compressed
                        section_text = extract_text_from_data(data)
                    
                    if section_text:
                        # Check for duplicate content
                        text_hash = hash(section_text.strip())
                        if text_hash not in seen_texts:
                            seen_texts.add(text_hash)
                            text_parts.append(section_text)
                            result["structure"]["sections"].append({
                                "section_id": entry[1],
                                "text_length": len(section_text),
                                "paragraph_count": len(section_text.split("\n\n"))
                            })
                        else:
                            logger.debug(f"Skipping duplicate content in {entry[1]}")
                            
                except Exception as e:
                    logger.warning(f"Failed to extract from {entry}", error=str(e))
        
        result["structure"]["total_sections"] = section_count
        
        result["text"] = "\n\n".join(text_parts)
        
        # Create paragraphs from extracted text
        if result["text"]:
            paragraphs = result["text"].split("\n\n")
            for para in paragraphs:
                if para.strip():
                    result["paragraphs"].append({
                        "text": para.strip()
                    })
        
        ole.close()
        
    except Exception as e:
        logger.error("Error parsing HWP with olefile", error=str(e))
        raise
    
    return result


def extract_text_from_data(data: bytes) -> str:
    """
    Extract text from binary data.
    Attempts multiple encoding strategies.
    
    Args:
        data: Binary data containing text
        
    Returns:
        Extracted text string
    """
    text_parts = []
    
    # Try different decoding strategies
    encodings = ['utf-16-le', 'utf-8', 'cp949', 'euc-kr']
    
    for encoding in encodings:
        try:
            # Skip null bytes and control characters
            cleaned_data = data.replace(b'\x00\x00', b'\n').replace(b'\x00', b'')
            text = cleaned_data.decode(encoding, errors='ignore')
            
            # Clean up the text
            lines = []
            for line in text.split('\n'):
                line = line.strip()
                # Filter out lines with too many special characters
                if line and len([c for c in line if c.isprintable()]) > len(line) * 0.5:
                    lines.append(line)
            
            if lines:
                return '\n'.join(lines)
                
        except Exception:
            continue
    
    # Fallback: extract any ASCII text
    ascii_text = []
    for byte in data:
        if 32 <= byte <= 126:  # Printable ASCII range
            ascii_text.append(chr(byte))
        elif byte in (10, 13):  # Newline characters
            ascii_text.append('\n')
            
    return ''.join(ascii_text)