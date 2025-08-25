"""
Streaming parser for large files with optimized memory management
"""
import os
import asyncio
import structlog
from typing import AsyncIterator, Dict, Any, Optional, BinaryIO
import aiofiles
import tempfile
from contextlib import asynccontextmanager
import mmap
from app.services.text_extractor import TextExtractor
from app.core.exceptions import FileTooLargeError, ProcessingError

logger = structlog.get_logger()


class StreamParser:
    """
    Parse large files using streaming and memory-mapped I/O to minimize memory usage
    """
    
    def __init__(self, chunk_size: int = 8192, max_file_size: int = 500 * 1024 * 1024):  # 500MB default
        self.chunk_size = chunk_size
        self.max_file_size = max_file_size
        self.text_extractor = TextExtractor()
        
    @asynccontextmanager
    async def save_uploaded_file_stream(self, file_stream, suffix: str):
        """
        Save uploaded file using streaming with size validation
        """
        temp_file_path = None
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                temp_file_path = tmp.name
            
            # Stream file content to disk with size check
            bytes_written = 0
            async with aiofiles.open(temp_file_path, 'wb') as f:
                async for chunk in file_stream:
                    if bytes_written + len(chunk) > self.max_file_size:
                        raise FileTooLargeError(f"File exceeds maximum size of {self.max_file_size / 1024 / 1024:.0f}MB")
                    
                    await f.write(chunk)
                    bytes_written += len(chunk)
                    
                    # Log progress for large files
                    if bytes_written % (10 * 1024 * 1024) == 0:  # Every 10MB
                        logger.info(f"Streaming file: {bytes_written / 1024 / 1024:.1f} MB written")
            
            logger.info(f"File saved: {bytes_written / 1024 / 1024:.2f} MB total")
            yield temp_file_path
            
        finally:
            # Cleanup
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except Exception as e:
                    logger.warning(f"Failed to delete temp file: {e}")
    
    async def parse_file_chunks(self, file_path: str, file_type: str) -> AsyncIterator[Dict[str, Any]]:
        """
        Parse file in chunks using memory-mapped I/O for efficient large file handling
        
        Yields:
            Parsed content chunks
        """
        file_size = os.path.getsize(file_path)
        logger.info(f"Starting chunked parsing: {file_size / 1024 / 1024:.2f} MB, type: {file_type}")
        
        # File info chunk
        yield {
            "type": "file_info",
            "size": file_size,
            "path": file_path,
            "file_type": file_type
        }
        
        # Choose parsing strategy based on file size
        if file_size < 10 * 1024 * 1024:  # < 10MB - parse in memory
            yield await self._parse_small_file(file_path, file_type)
        elif file_size < 100 * 1024 * 1024:  # < 100MB - use memory mapping
            async for chunk in self._parse_medium_file_mmap(file_path, file_type):
                yield chunk
        else:  # >= 100MB - stream processing
            async for chunk in self._parse_large_file_stream(file_path, file_type):
                yield chunk
    
    async def _parse_small_file(self, file_path: str, file_type: str) -> Dict[str, Any]:
        """Parse small files entirely in memory"""
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            
            # Use existing text extractor
            result = await asyncio.to_thread(
                self.text_extractor.extract_text,
                content,
                file_type,
                output_format='json'
            )
            
            return {
                "type": "content",
                "data": result
            }
        except Exception as e:
            logger.error(f"Failed to parse small file: {e}")
            raise ProcessingError(f"Failed to parse file: {str(e)}")
    
    async def _parse_medium_file_mmap(self, file_path: str, file_type: str) -> AsyncIterator[Dict[str, Any]]:
        """Parse medium files using memory-mapped I/O"""
        try:
            with open(file_path, 'rb') as f:
                # Use memory mapping for efficient access
                with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mmapped_file:
                    # Process in chunks
                    total_size = len(mmapped_file)
                    chunk_size = 5 * 1024 * 1024  # 5MB chunks
                    
                    for offset in range(0, total_size, chunk_size):
                        end = min(offset + chunk_size, total_size)
                        chunk_data = mmapped_file[offset:end]
                        
                        # Process chunk (simplified - actual implementation would parse properly)
                        yield {
                            "type": "content_chunk",
                            "offset": offset,
                            "size": end - offset,
                            "total_size": total_size,
                            "progress": (end / total_size) * 100
                        }
                        
                        # Allow other tasks to run
                        await asyncio.sleep(0)
                    
                    # Final processing
                    mmapped_file.seek(0)
                    result = await asyncio.to_thread(
                        self.text_extractor.extract_text,
                        bytes(mmapped_file),
                        file_type,
                        output_format='json'
                    )
                    
                    yield {
                        "type": "final_content",
                        "data": result
                    }
                    
        except Exception as e:
            logger.error(f"Failed to parse medium file with mmap: {e}")
            raise ProcessingError(f"Failed to parse file: {str(e)}")
    
    async def _parse_large_file_stream(self, file_path: str, file_type: str) -> AsyncIterator[Dict[str, Any]]:
        """Parse very large files using streaming"""
        try:
            # For very large files, we need specialized streaming parsers
            # This is a simplified implementation
            
            if file_type == 'pdf':
                async for chunk in self._stream_pdf(file_path):
                    yield chunk
            elif file_type in ['hwp', 'hwpx']:
                async for chunk in self._stream_hwp(file_path):
                    yield chunk
            else:
                # Fallback to chunked text extraction
                async for chunk in self._stream_text(file_path):
                    yield chunk
                    
        except Exception as e:
            logger.error(f"Failed to parse large file stream: {e}")
            raise ProcessingError(f"Failed to parse file: {str(e)}")
    
    async def _stream_pdf(self, file_path: str) -> AsyncIterator[Dict[str, Any]]:
        """Stream PDF content page by page"""
        import fitz  # PyMuPDF
        
        try:
            doc = fitz.open(file_path)
            total_pages = len(doc)
            
            for page_num in range(total_pages):
                page = doc[page_num]
                text = page.get_text()
                
                yield {
                    "type": "page",
                    "page_number": page_num + 1,
                    "total_pages": total_pages,
                    "content": text,
                    "progress": ((page_num + 1) / total_pages) * 100
                }
                
                # Allow other tasks to run
                await asyncio.sleep(0)
            
            doc.close()
            
        except Exception as e:
            logger.error(f"Failed to stream PDF: {e}")
            raise
    
    async def _stream_hwp(self, file_path: str) -> AsyncIterator[Dict[str, Any]]:
        """Stream HWP content in chunks"""
        # This would require a streaming HWP parser
        # For now, we'll use the regular parser with chunking
        
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            
            # Extract in chunks (simplified)
            result = await asyncio.to_thread(
                self.text_extractor.extract_text,
                content,
                'hwp',
                output_format='json'
            )
            
            # Yield as chunks
            if isinstance(result, dict) and 'content' in result:
                content_str = str(result['content'])
                chunk_size = 10000  # characters
                
                for i in range(0, len(content_str), chunk_size):
                    yield {
                        "type": "text_chunk",
                        "offset": i,
                        "content": content_str[i:i+chunk_size],
                        "progress": (min(i + chunk_size, len(content_str)) / len(content_str)) * 100
                    }
                    await asyncio.sleep(0)
                    
        except Exception as e:
            logger.error(f"Failed to stream HWP: {e}")
            raise
    
    async def _stream_text(self, file_path: str) -> AsyncIterator[Dict[str, Any]]:
        """Stream plain text content"""
        try:
            file_size = os.path.getsize(file_path)
            bytes_read = 0
            
            async with aiofiles.open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                while True:
                    chunk = await f.read(self.chunk_size)
                    if not chunk:
                        break
                    
                    bytes_read += len(chunk.encode('utf-8'))
                    
                    yield {
                        "type": "text_chunk",
                        "content": chunk,
                        "progress": (bytes_read / file_size) * 100
                    }
                    
                    await asyncio.sleep(0)
                    
        except Exception as e:
            logger.error(f"Failed to stream text: {e}")
            raise
    
    async def extract_text_stream(self, file_path: str, file_type: str) -> AsyncIterator[str]:
        """
        Extract text from file using streaming
        
        Yields:
            Text chunks
        """
        async for chunk in self.parse_file_chunks(file_path, file_type):
            if chunk['type'] == 'text_chunk':
                yield chunk['content']
            elif chunk['type'] == 'page':
                yield chunk['content']
            elif chunk['type'] == 'final_content':
                if isinstance(chunk['data'], dict) and 'text' in chunk['data']:
                    yield chunk['data']['text']