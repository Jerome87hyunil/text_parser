"""
API endpoints for extracting structured data from HWP files.
Optimized for AI analysis and processing.
"""
import structlog
from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
import os
import tempfile
import aiofiles
import json

from app.core.config import get_settings
from app.services.hwp_parser import HWPParser
from app.services.text_extractor import TextExtractor
from app.models.extract import ExtractRequest, ExtractResponse, ExtractFormat

logger = structlog.get_logger()
router = APIRouter()
settings = get_settings()


@router.post("/hwp-to-json", response_model=ExtractResponse)
async def extract_hwp_to_json(
    file: UploadFile = File(...),
    include_metadata: bool = True,
    include_structure: bool = True,
    include_statistics: bool = True,
) -> ExtractResponse:
    """
    Extract structured data from HWP file in JSON format.
    
    This endpoint is optimized for AI analysis:
    - Preserves document structure (headings, paragraphs, lists, tables)
    - Extracts metadata (title, author, creation date, etc.)
    - Provides text statistics for analysis
    - Returns clean, structured JSON suitable for LLM processing
    
    Args:
        file: HWP file to extract
        include_metadata: Include document metadata
        include_structure: Preserve document structure
        include_statistics: Include text statistics
        
    Returns:
        Structured JSON with extracted content
    """
    # Validate file
    allowed_extensions = ('.hwp', '.hwpx', '.pdf')
    if not file.filename.lower().endswith(allowed_extensions):
        raise HTTPException(status_code=400, detail="File must be HWP, HWPX, or PDF format")
    
    if file.size > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {settings.MAX_FILE_SIZE} bytes"
        )
    
    temp_file_path = None
    try:
        # Save uploaded file temporarily
        if file.filename.lower().endswith('.hwpx'):
            suffix = '.hwpx'
        elif file.filename.lower().endswith('.pdf'):
            suffix = '.pdf'
        else:
            suffix = '.hwp'
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file_path = temp_file.name
            content = await file.read()
            async with aiofiles.open(temp_file_path, 'wb') as f:
                await f.write(content)
        
        # Initialize parser and extractor
        parser = HWPParser()
        extractor = TextExtractor()
        
        # Parse file
        logger.info("Extracting content from file", filename=file.filename)
        parsed_content = parser.parse(temp_file_path)
        
        # Extract structured content
        structured_content = extractor.extract_structured(
            parsed_content,
            include_metadata=include_metadata,
            include_structure=include_structure,
            include_statistics=include_statistics
        )
        
        # Log success
        logger.info(
            "Successfully extracted content",
            filename=file.filename,
            text_length=len(structured_content.get("text", "")),
            paragraphs=len(structured_content.get("paragraphs", [])),
            tables=len(structured_content.get("tables", []))
        )
        
        return ExtractResponse(
            success=True,
            filename=file.filename,
            format=ExtractFormat.JSON,
            content=structured_content,
            message="Content extracted successfully"
        )
        
    except Exception as e:
        logger.error("Failed to extract HWP content", error=str(e), filename=file.filename)
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")
    
    finally:
        # Cleanup
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)


@router.post("/hwp-to-text", response_model=ExtractResponse)
async def extract_hwp_to_text(
    file: UploadFile = File(...),
    preserve_formatting: bool = False,
) -> ExtractResponse:
    """
    Extract plain text from HWP file.
    
    Simple text extraction for basic AI analysis:
    - Clean plain text output
    - Optional formatting preservation
    - Suitable for simple text analysis tasks
    
    Args:
        file: HWP file to extract
        preserve_formatting: Preserve line breaks and spacing
        
    Returns:
        Plain text content
    """
    # Validate file
    allowed_extensions = ('.hwp', '.hwpx', '.pdf')
    if not file.filename.lower().endswith(allowed_extensions):
        raise HTTPException(status_code=400, detail="File must be HWP, HWPX, or PDF format")
    
    if file.size > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {settings.MAX_FILE_SIZE} bytes"
        )
    
    temp_file_path = None
    try:
        # Save uploaded file temporarily
        if file.filename.lower().endswith('.hwpx'):
            suffix = '.hwpx'
        elif file.filename.lower().endswith('.pdf'):
            suffix = '.pdf'
        else:
            suffix = '.hwp'
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file_path = temp_file.name
            content = await file.read()
            async with aiofiles.open(temp_file_path, 'wb') as f:
                await f.write(content)
        
        # Initialize parser
        parser = HWPParser()
        
        # Extract text
        logger.info("Extracting text from HWP", filename=file.filename)
        text_content = parser.extract_text(temp_file_path)
        
        # Process formatting if requested
        if not preserve_formatting:
            # Remove extra whitespace and normalize
            text_content = ' '.join(text_content.split())
        
        logger.info(
            "Successfully extracted text",
            filename=file.filename,
            text_length=len(text_content)
        )
        
        return ExtractResponse(
            success=True,
            filename=file.filename,
            format=ExtractFormat.TEXT,
            content={"text": text_content},
            message="Text extracted successfully"
        )
        
    except Exception as e:
        logger.error("Failed to extract text", error=str(e), filename=file.filename)
        raise HTTPException(status_code=500, detail=f"Text extraction failed: {str(e)}")
    
    finally:
        # Cleanup
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)


@router.post("/hwp-to-markdown", response_model=ExtractResponse)
async def extract_hwp_to_markdown(
    file: UploadFile = File(...),
    include_metadata: bool = True,
) -> ExtractResponse:
    """
    Extract content from HWP file in Markdown format.
    
    Markdown output for AI analysis with structure:
    - Headers, paragraphs, lists preserved
    - Tables in markdown format
    - Metadata as YAML front matter
    - Human-readable and AI-parseable
    
    Args:
        file: HWP file to extract
        include_metadata: Include metadata as YAML front matter
        
    Returns:
        Markdown formatted content
    """
    # Validate file
    allowed_extensions = ('.hwp', '.hwpx', '.pdf')
    if not file.filename.lower().endswith(allowed_extensions):
        raise HTTPException(status_code=400, detail="File must be HWP, HWPX, or PDF format")
    
    if file.size > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {settings.MAX_FILE_SIZE} bytes"
        )
    
    temp_file_path = None
    try:
        # Save uploaded file temporarily
        if file.filename.lower().endswith('.hwpx'):
            suffix = '.hwpx'
        elif file.filename.lower().endswith('.pdf'):
            suffix = '.pdf'
        else:
            suffix = '.hwp'
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file_path = temp_file.name
            content = await file.read()
            async with aiofiles.open(temp_file_path, 'wb') as f:
                await f.write(content)
        
        # Initialize parser and extractor
        parser = HWPParser()
        extractor = TextExtractor()
        
        # Parse HWP file
        logger.info("Extracting content for markdown", filename=file.filename)
        parsed_content = parser.parse(temp_file_path)
        
        # Convert to markdown
        markdown_content = extractor.to_markdown(
            parsed_content,
            include_metadata=include_metadata
        )
        
        logger.info(
            "Successfully created markdown",
            filename=file.filename,
            markdown_length=len(markdown_content)
        )
        
        return ExtractResponse(
            success=True,
            filename=file.filename,
            format=ExtractFormat.MARKDOWN,
            content={"markdown": markdown_content},
            message="Markdown created successfully"
        )
        
    except Exception as e:
        logger.error("Failed to create markdown", error=str(e), filename=file.filename)
        raise HTTPException(status_code=500, detail=f"Markdown creation failed: {str(e)}")
    
    finally:
        # Cleanup
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)