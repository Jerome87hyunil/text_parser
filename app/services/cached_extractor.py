"""
Cached extraction service
"""
import structlog
from typing import Dict, Any, Optional
from app.services.hwp_parser import HWPParser
from app.services.text_extractor import TextExtractor
from app.core.cache import cache_manager

logger = structlog.get_logger()


class CachedExtractor:
    """
    Extraction service with caching support
    """
    
    def __init__(self):
        self.parser = HWPParser()
        self.extractor = TextExtractor()
    
    async def extract_with_cache(
        self,
        file_path: str,
        file_content: bytes,
        extraction_type: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Extract content with caching support
        
        Args:
            file_path: Path to the file
            file_content: File content for cache key generation
            extraction_type: Type of extraction (json, text, markdown)
            **kwargs: Additional parameters for extraction
            
        Returns:
            Extracted content
        """
        # Build cache key
        cache_key_parts = [extraction_type]
        for key, value in kwargs.items():
            cache_key_parts.append(f"{key}:{value}")
        cache_key = "_".join(cache_key_parts)
        
        # Check cache
        cached_result = await cache_manager.get(file_content, cache_key)
        if cached_result:
            logger.info("Cache hit", cache_key=cache_key)
            return cached_result
        
        # Parse file
        parsed_content = self.parser.parse(file_path)
        
        # Extract based on type
        if extraction_type == "json":
            result = self.extractor.extract_structured(
                parsed_content,
                include_metadata=kwargs.get("include_metadata", True),
                include_structure=kwargs.get("include_structure", True),
                include_statistics=kwargs.get("include_statistics", True)
            )
        elif extraction_type == "text":
            text = self.parser.extract_text(file_path)
            if not kwargs.get("preserve_formatting", False):
                text = ' '.join(text.split())
            result = {"text": text}
        elif extraction_type == "markdown":
            result = {
                "markdown": self.extractor.to_markdown(
                    parsed_content,
                    include_metadata=kwargs.get("include_metadata", True)
                )
            }
        else:
            raise ValueError(f"Unknown extraction type: {extraction_type}")
        
        # Cache the result
        await cache_manager.set(file_content, cache_key, result)
        logger.info("Cached result", cache_key=cache_key)
        
        return result