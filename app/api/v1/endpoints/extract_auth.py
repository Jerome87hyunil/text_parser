"""
Authenticated extraction endpoints with higher rate limits
"""
import structlog
from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, Query
from typing import Dict, Any, Optional
import os
import tempfile
import aiofiles

from app.core.config import get_settings
from app.services.hwp_parser import HWPParser
from app.services.text_extractor import TextExtractor
from app.models.extract import ExtractRequest, ExtractResponse, ExtractFormat, ExtractedContent
from app.api.v1.endpoints.auth import get_current_active_user
from app.models.auth import User
from app.middleware.rate_limit_fixed import auth_rate_limit_dependency
import time

logger = structlog.get_logger()
router = APIRouter()
settings = get_settings()


@router.post("/hwp-to-json", 
    response_model=ExtractResponse,
    tags=["extract", "authenticated"],
    summary="문서를 JSON으로 변환 (인증됨)",
    dependencies=[Depends(auth_rate_limit_dependency)],
    responses={
        200: {"description": "성공적으로 변환됨"},
        400: {"description": "잘못된 파일 형식"},
        401: {"description": "인증 필요"},
        413: {"description": "파일 크기 초과"},
        429: {"description": "요청 한도 초과"},
        500: {"description": "추출 실패"}
    }
)
async def extract_hwp_to_json_auth(
    file: UploadFile = File(..., description="HWP, HWPX, 또는 PDF 파일"),
    include_metadata: bool = Query(True, description="문서 메타데이터 포함 여부"),
    include_structure: bool = Query(True, description="문서 구조 정보 포함 여부"),
    include_statistics: bool = Query(True, description="텍스트 통계 정보 포함 여부"),
    current_user: User = Depends(get_current_active_user)
) -> ExtractResponse:
    """
    인증된 사용자를 위한 JSON 추출 엔드포인트.
    더 높은 rate limit (100/분)이 적용됩니다.
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
        logger.info("Extracting content from file (authenticated)", 
                   filename=file.filename, 
                   user=current_user.username)
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
            "Successfully extracted content (authenticated)",
            filename=file.filename,
            user=current_user.username,
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
            message=f"Content extracted successfully for user: {current_user.username}"
        )
        
    except Exception as e:
        logger.error("Failed to extract HWP content", 
                    error=str(e), 
                    filename=file.filename,
                    user=current_user.username)
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")
    
    finally:
        # Cleanup
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)