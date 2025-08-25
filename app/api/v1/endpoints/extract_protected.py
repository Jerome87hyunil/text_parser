"""
Protected extraction endpoints requiring API key authentication
"""
from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, Form
from typing import Optional, Dict, Any

from app.models.extract import ExtractionType, TextExtractionRequest, TextExtractionResponse
from app.services.text_extractor import TextExtractorService
from app.core.config import settings
from app.models.database import User
from app.middleware.api_key_auth import require_api_key
import structlog

logger = structlog.get_logger()

router = APIRouter()
text_extractor = TextExtractorService()


@router.post("/hwp-to-json",
    response_model=Dict[str, Any],
    summary="HWP to JSON 텍스트 추출 (API 키 필요)",
    description="API 키 인증이 필요한 HWP 파일 텍스트 추출",
    responses={
        200: {
            "description": "성공적으로 텍스트 추출",
            "content": {
                "application/json": {
                    "example": {
                        "filename": "document.hwp",
                        "file_type": "hwp",
                        "extraction_type": "json",
                        "pages": [
                            {
                                "page_number": 1,
                                "text": "문서 내용...",
                                "metadata": {}
                            }
                        ],
                        "metadata": {
                            "total_pages": 1,
                            "extracted_at": "2024-01-01T00:00:00Z"
                        }
                    }
                }
            }
        },
        401: {"description": "인증 실패"},
        413: {"description": "파일 크기 초과"},
        415: {"description": "지원하지 않는 파일 형식"},
        500: {"description": "추출 실패"}
    }
)
async def extract_hwp_to_json_protected(
    file: UploadFile = File(..., description="HWP 파일 (최대 100MB)"),
    extract_tables: bool = Form(True, description="테이블 추출 여부"),
    extract_images: bool = Form(False, description="이미지 추출 여부"),
    user: User = Depends(require_api_key)
):
    """
    API 키 인증이 필요한 HWP to JSON 추출 엔드포인트
    
    - **file**: HWP 파일 업로드
    - **extract_tables**: 테이블 추출 여부
    - **extract_images**: 이미지 추출 여부
    - **API Key**: Authorization 헤더 또는 X-API-Key 헤더에 API 키 필요
    """
    try:
        # Log API key usage
        logger.info(
            "Protected extraction requested",
            user_id=user.id,
            username=user.username,
            filename=file.filename,
            extraction_type="json"
        )
        
        # Validate file
        if not file.filename.lower().endswith(('.hwp', '.hwpx')):
            raise HTTPException(
                status_code=415,
                detail="Only HWP and HWPX files are supported"
            )
        
        # Check file size
        file_content = await file.read()
        if len(file_content) > settings.MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File size exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE} bytes"
            )
        
        # Extract text
        result = await text_extractor.extract_text(
            file_content=file_content,
            filename=file.filename,
            extraction_type=ExtractionType.JSON,
            options={
                "extract_tables": extract_tables,
                "extract_images": extract_images,
                "user_id": user.id  # Track usage by user
            }
        )
        
        logger.info(
            "Protected extraction completed",
            user_id=user.id,
            username=user.username,
            filename=file.filename,
            success=True
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Protected extraction failed",
            user_id=user.id,
            username=user.username,
            filename=file.filename,
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to extract text: {str(e)}"
        )


@router.post("/hwp-to-text",
    response_model=str,
    summary="HWP to Plain Text 추출 (API 키 필요)",
    description="API 키 인증이 필요한 HWP 파일 텍스트 추출",
    responses={
        200: {
            "description": "성공적으로 텍스트 추출",
            "content": {
                "text/plain": {
                    "example": "추출된 텍스트 내용..."
                }
            }
        },
        401: {"description": "인증 실패"},
        413: {"description": "파일 크기 초과"},
        415: {"description": "지원하지 않는 파일 형식"},
        500: {"description": "추출 실패"}
    }
)
async def extract_hwp_to_text_protected(
    file: UploadFile = File(..., description="HWP 파일 (최대 100MB)"),
    user: User = Depends(require_api_key)
):
    """
    API 키 인증이 필요한 HWP to Text 추출 엔드포인트
    
    - **file**: HWP 파일 업로드
    - **API Key**: Authorization 헤더 또는 X-API-Key 헤더에 API 키 필요
    """
    try:
        # Log API key usage
        logger.info(
            "Protected text extraction requested",
            user_id=user.id,
            username=user.username,
            filename=file.filename,
            extraction_type="text"
        )
        
        # Validate file
        if not file.filename.lower().endswith(('.hwp', '.hwpx')):
            raise HTTPException(
                status_code=415,
                detail="Only HWP and HWPX files are supported"
            )
        
        # Check file size
        file_content = await file.read()
        if len(file_content) > settings.MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File size exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE} bytes"
            )
        
        # Extract text
        result = await text_extractor.extract_text(
            file_content=file_content,
            filename=file.filename,
            extraction_type=ExtractionType.TEXT,
            options={
                "user_id": user.id  # Track usage by user
            }
        )
        
        logger.info(
            "Protected text extraction completed",
            user_id=user.id,
            username=user.username,
            filename=file.filename,
            success=True
        )
        
        # For text extraction, return only the text content
        if isinstance(result, dict) and "text" in result:
            return result["text"]
        elif isinstance(result, dict) and "pages" in result:
            # Combine text from all pages
            texts = []
            for page in result["pages"]:
                if isinstance(page, dict) and "text" in page:
                    texts.append(page["text"])
            return "\n\n".join(texts)
        else:
            return str(result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Protected text extraction failed",
            user_id=user.id,
            username=user.username,
            filename=file.filename,
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to extract text: {str(e)}"
        )


@router.post("/pdf-to-json",
    response_model=Dict[str, Any],
    summary="PDF to JSON 텍스트 추출 (API 키 필요)",
    description="API 키 인증이 필요한 PDF 파일 텍스트 추출",
    responses={
        200: {"description": "성공적으로 텍스트 추출"},
        401: {"description": "인증 실패"},
        413: {"description": "파일 크기 초과"},
        415: {"description": "지원하지 않는 파일 형식"},
        500: {"description": "추출 실패"}
    }
)
async def extract_pdf_to_json_protected(
    file: UploadFile = File(..., description="PDF 파일 (최대 100MB)"),
    extract_tables: bool = Form(True, description="테이블 추출 여부"),
    user: User = Depends(require_api_key)
):
    """
    API 키 인증이 필요한 PDF to JSON 추출 엔드포인트
    
    - **file**: PDF 파일 업로드
    - **extract_tables**: 테이블 추출 여부
    - **API Key**: Authorization 헤더 또는 X-API-Key 헤더에 API 키 필요
    """
    try:
        # Log API key usage
        logger.info(
            "Protected PDF extraction requested",
            user_id=user.id,
            username=user.username,
            filename=file.filename,
            extraction_type="json"
        )
        
        # Validate file
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(
                status_code=415,
                detail="Only PDF files are supported"
            )
        
        # Check file size
        file_content = await file.read()
        if len(file_content) > settings.MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File size exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE} bytes"
            )
        
        # Extract text
        result = await text_extractor.extract_text(
            file_content=file_content,
            filename=file.filename,
            extraction_type=ExtractionType.JSON,
            options={
                "extract_tables": extract_tables,
                "user_id": user.id  # Track usage by user
            }
        )
        
        logger.info(
            "Protected PDF extraction completed",
            user_id=user.id,
            username=user.username,
            filename=file.filename,
            success=True
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Protected PDF extraction failed",
            user_id=user.id,
            username=user.username,
            filename=file.filename,
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to extract text: {str(e)}"
        )