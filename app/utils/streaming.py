"""
Streaming utilities for efficient file processing.
"""
import io
import asyncio
from typing import AsyncIterator, BinaryIO, Optional
import aiofiles
import structlog

logger = structlog.get_logger()


class StreamingFileProcessor:
    """Process files in streaming fashion to minimize memory usage."""
    
    def __init__(self, chunk_size: int = 8192):
        """
        Initialize streaming processor.
        
        Args:
            chunk_size: Size of chunks to read at a time
        """
        self.chunk_size = chunk_size
    
    async def read_file_chunks(self, file_path: str) -> AsyncIterator[bytes]:
        """
        Read file in chunks asynchronously.
        
        Args:
            file_path: Path to file
            
        Yields:
            Chunks of file content
        """
        try:
            async with aiofiles.open(file_path, 'rb') as file:
                while True:
                    chunk = await file.read(self.chunk_size)
                    if not chunk:
                        break
                    yield chunk
        except Exception as e:
            logger.error("Error reading file in chunks", error=str(e), file_path=file_path)
            raise
    
    async def process_upload_stream(
        self,
        file_stream: BinaryIO,
        output_path: str,
        max_size: Optional[int] = None
    ) -> int:
        """
        Process uploaded file stream and save to disk.
        
        Args:
            file_stream: Input file stream
            output_path: Path to save file
            max_size: Maximum allowed file size
            
        Returns:
            Total bytes written
            
        Raises:
            ValueError: If file exceeds max_size
        """
        total_size = 0
        
        try:
            async with aiofiles.open(output_path, 'wb') as output_file:
                while True:
                    chunk = file_stream.read(self.chunk_size)
                    if not chunk:
                        break
                    
                    total_size += len(chunk)
                    
                    if max_size and total_size > max_size:
                        # Clean up partial file
                        await output_file.close()
                        import os
                        os.unlink(output_path)
                        raise ValueError(f"File exceeds maximum size of {max_size} bytes")
                    
                    await output_file.write(chunk)
                    
                    # Yield control to prevent blocking
                    await asyncio.sleep(0)
            
            logger.info("File processed", path=output_path, size=total_size)
            return total_size
            
        except Exception as e:
            logger.error("Error processing upload stream", error=str(e))
            raise
    
    def estimate_memory_usage(self, file_size: int) -> dict:
        """
        Estimate memory usage for processing a file.
        
        Args:
            file_size: Size of file in bytes
            
        Returns:
            Dict with memory estimates
        """
        # Streaming uses fixed memory regardless of file size
        streaming_memory = self.chunk_size * 2  # Double buffer
        
        # Traditional approach loads entire file
        traditional_memory = file_size
        
        # Calculate savings
        savings = traditional_memory - streaming_memory
        savings_percent = (savings / traditional_memory * 100) if traditional_memory > 0 else 0
        
        return {
            "streaming_memory_bytes": streaming_memory,
            "traditional_memory_bytes": traditional_memory,
            "memory_savings_bytes": savings,
            "memory_savings_percent": round(savings_percent, 2)
        }


class ChunkedTextExtractor:
    """Extract text in chunks to minimize memory usage."""
    
    def __init__(self, chunk_size: int = 1024 * 1024):  # 1MB chunks
        self.chunk_size = chunk_size
        self.buffer = []
        self.buffer_size = 0
    
    async def extract_chunked(self, text: str) -> AsyncIterator[str]:
        """
        Extract text in chunks.
        
        Args:
            text: Input text
            
        Yields:
            Text chunks
        """
        # Process text in chunks
        for i in range(0, len(text), self.chunk_size):
            chunk = text[i:i + self.chunk_size]
            
            # Find last complete sentence or paragraph
            last_break = chunk.rfind('\n')
            if last_break == -1:
                last_break = chunk.rfind('. ')
            
            if last_break != -1 and i + self.chunk_size < len(text):
                # Yield up to the break point
                yield chunk[:last_break + 1]
                # Add remainder to next chunk
                text = chunk[last_break + 1:] + text[i + self.chunk_size:]
            else:
                yield chunk
            
            # Yield control
            await asyncio.sleep(0)
    
    def add_to_buffer(self, text: str) -> Optional[str]:
        """
        Add text to buffer and return when chunk is ready.
        
        Args:
            text: Text to add
            
        Returns:
            Chunk if buffer is full, None otherwise
        """
        self.buffer.append(text)
        self.buffer_size += len(text)
        
        if self.buffer_size >= self.chunk_size:
            result = ''.join(self.buffer)
            self.buffer = []
            self.buffer_size = 0
            return result
        
        return None
    
    def flush_buffer(self) -> Optional[str]:
        """
        Flush remaining buffer content.
        
        Returns:
            Remaining text if any
        """
        if self.buffer:
            result = ''.join(self.buffer)
            self.buffer = []
            self.buffer_size = 0
            return result
        return None