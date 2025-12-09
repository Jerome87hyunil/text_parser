"""
API endpoints for extracting structured data from HWP files.
Optimized for AI analysis and processing.
"""
import structlog
from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
import os
import tempfile
import aiofiles
import json

from app.core.config import get_settings
from app.services.hwp_parser import get_parser  # v1.1: 싱글톤 사용
from app.services.text_extractor import TextExtractor
import gc  # v3.3: 메모리 관리
from app.models.extract import ExtractRequest, ExtractResponse, ExtractFormat, ExtractedContent
from app.core.cache import cache_manager
from app.api.v1.endpoints.metrics import track_extraction, track_extraction_duration
from app.api.v1.endpoints.auth import get_current_active_user
from app.models.auth import User
from app.middleware.rate_limit_fixed import rate_limit_dependency
from app.utils.file_validator import file_validator
import time

logger = structlog.get_logger()
router = APIRouter()
settings = get_settings()


@router.post("/hwp-to-json", 
    response_model=ExtractResponse,
    tags=["extract"],
    summary="문서를 JSON으로 변환",
    dependencies=[Depends(rate_limit_dependency)],
    responses={
        200: {
            "description": "성공적으로 변환됨",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "filename": "document.hwp",
                        "format": "json",
                        "content": {
                            "text": "추출된 전체 텍스트...",
                            "metadata": {
                                "title": "문서 제목",
                                "author": "작성자",
                                "created_date": "2024-01-01"
                            },
                            "paragraphs": [
                                {
                                    "text": "단락 내용",
                                    "type": "normal",
                                    "level": 0
                                }
                            ],
                            "tables": [
                                {
                                    "rows": 2,
                                    "cols": 3,
                                    "data": [["셀1", "셀2", "셀3"]]
                                }
                            ]
                        },
                        "message": "Content extracted successfully"
                    }
                }
            }
        },
        400: {"description": "잘못된 파일 형식"},
        413: {"description": "파일 크기 초과"},
        500: {"description": "추출 실패"}
    }
)
async def extract_hwp_to_json(
    file: UploadFile = File(..., description="HWP, HWPX, 또는 PDF 파일"),
    include_metadata: bool = Query(True, description="문서 메타데이터 포함 여부"),
    include_structure: bool = Query(True, description="문서 구조 정보 포함 여부"),
    include_statistics: bool = Query(True, description="텍스트 통계 정보 포함 여부"),
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
    # Basic validation
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
        
        # Enhanced file validation
        validation_result = file_validator.validate_file(temp_file_path, file.filename)
        if not validation_result["valid"]:
            raise HTTPException(
                status_code=400,
                detail=f"File validation failed: {'; '.join(validation_result['errors'])}"
            )
        
        # Log warnings if any
        if validation_result["warnings"]:
            logger.warning("File validation warnings", 
                         warnings=validation_result["warnings"],
                         filename=file.filename)
        
        # Initialize parser and extractor (v1.1: 싱글톤 사용)
        parser = get_parser()
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
        
        # Create ExtractedContent object from structured_content
        from datetime import datetime, timezone
        extracted_content = ExtractedContent(
            version="1.0",
            extracted_at=datetime.now(timezone.utc).isoformat() + "Z",
            metadata=structured_content.get("metadata"),
            text=structured_content.get("text", ""),
            paragraphs=structured_content.get("paragraphs"),
            tables=structured_content.get("tables"),
            lists=structured_content.get("lists"),
            headings=structured_content.get("headings"),
            statistics=structured_content.get("statistics"),
            # raw_data removed to avoid JSON schema issues
        )
        
        return ExtractResponse(
            success=True,
            filename=file.filename,
            format=ExtractFormat.JSON,
            content=extracted_content,
            message="Content extracted successfully"
        )
        
    except Exception as e:
        logger.error("Failed to extract HWP content", error=str(e), filename=file.filename)
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")
    
    finally:
        # Cleanup
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
        # v3.3: 요청 후 GC 호출
        gc.collect()


@router.post("/hwp-to-text",
    response_model=ExtractResponse,
    tags=["extract"],
    summary="문서를 텍스트로 변환",
    dependencies=[Depends(rate_limit_dependency)],
    responses={
        200: {"description": "성공적으로 변환됨"},
        400: {"description": "잘못된 파일 형식"},
        413: {"description": "파일 크기 초과"},
        500: {"description": "추출 실패"}
    }
)
async def extract_hwp_to_text(
    file: UploadFile = File(..., description="HWP, HWPX, 또는 PDF 파일"),
    preserve_formatting: bool = Query(False, description="줄바꿈 및 공백 유지 여부"),
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
    # Basic validation
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
        
        # Enhanced file validation
        validation_result = file_validator.validate_file(temp_file_path, file.filename)
        if not validation_result["valid"]:
            raise HTTPException(
                status_code=400,
                detail=f"File validation failed: {'; '.join(validation_result['errors'])}"
            )
        
        # Log warnings if any
        if validation_result["warnings"]:
            logger.warning("File validation warnings", 
                         warnings=validation_result["warnings"],
                         filename=file.filename)
        
        # Initialize parser (v1.1: 싱글톤 사용)
        parser = get_parser()

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
            content=text_content,  # Return string directly for TEXT format
            message="Text extracted successfully"
        )
        
    except Exception as e:
        logger.error("Failed to extract text", error=str(e), filename=file.filename)
        raise HTTPException(status_code=500, detail=f"Text extraction failed: {str(e)}")
    
    finally:
        # Cleanup
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
        # v3.3: 요청 후 GC 호출
        gc.collect()


@router.post("/hwp-to-markdown",
    response_model=ExtractResponse,
    tags=["extract"],
    summary="문서를 Markdown으로 변환",
    dependencies=[Depends(rate_limit_dependency)],
    responses={
        200: {"description": "성공적으로 변환됨"},
        400: {"description": "잘못된 파일 형식"},
        413: {"description": "파일 크기 초과"},
        500: {"description": "추출 실패"}
    }
)
async def extract_hwp_to_markdown(
    file: UploadFile = File(..., description="HWP, HWPX, 또는 PDF 파일"),
    include_metadata: bool = Query(True, description="YAML 프론트매터로 메타데이터 포함 여부"),
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
    # Basic validation
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
        
        # Enhanced file validation
        validation_result = file_validator.validate_file(temp_file_path, file.filename)
        if not validation_result["valid"]:
            raise HTTPException(
                status_code=400,
                detail=f"File validation failed: {'; '.join(validation_result['errors'])}"
            )
        
        # Log warnings if any
        if validation_result["warnings"]:
            logger.warning("File validation warnings", 
                         warnings=validation_result["warnings"],
                         filename=file.filename)
        
        # Initialize parser and extractor (v1.1: 싱글톤 사용)
        parser = get_parser()
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
            content=markdown_content,  # Return string directly for MARKDOWN format
            message="Markdown created successfully"
        )
        
    except Exception as e:
        logger.error("Failed to create markdown", error=str(e), filename=file.filename)
        raise HTTPException(status_code=500, detail=f"Markdown creation failed: {str(e)}")

    finally:
        # Cleanup
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
        # v3.3: 요청 후 GC 호출
        gc.collect()