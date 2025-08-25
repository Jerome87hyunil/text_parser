"""
Asynchronous extraction endpoints using Celery
"""
import structlog
from fastapi import APIRouter, File, UploadFile, HTTPException, Query
from typing import Dict
from celery.result import AsyncResult

from app.core.config import get_settings
from app.tasks import extract_file_async
from app.models.extract import ExtractFormat
from app.models.status import TaskStatus, TaskResult

logger = structlog.get_logger()
router = APIRouter()
settings = get_settings()


@router.post("/submit",
    tags=["async"],
    summary="비동기 파일 추출 작업 제출",
    responses={
        202: {
            "description": "작업이 성공적으로 제출됨",
            "content": {
                "application/json": {
                    "example": {
                        "task_id": "550e8400-e29b-41d4-a716-446655440000",
                        "status": "PENDING",
                        "message": "Task submitted successfully"
                    }
                }
            }
        },
        400: {"description": "잘못된 파일 형식"},
        413: {"description": "파일 크기 초과"}
    }
)
async def submit_extraction(
    file: UploadFile = File(..., description="HWP, HWPX, 또는 PDF 파일"),
    extraction_type: str = Query("json", description="추출 형식 (json, text, markdown)"),
    include_metadata: bool = Query(True, description="메타데이터 포함 여부"),
    include_structure: bool = Query(True, description="구조 정보 포함 여부"),
    include_statistics: bool = Query(True, description="통계 정보 포함 여부"),
) -> Dict[str, str]:
    """
    파일 추출 작업을 비동기로 제출합니다.
    
    대용량 파일이나 여러 파일을 처리할 때 유용합니다.
    작업 ID를 반환하며, 이를 사용하여 작업 상태를 확인할 수 있습니다.
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
    
    # Validate extraction type
    if extraction_type not in ["json", "text", "markdown"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid extraction type. Must be 'json', 'text', or 'markdown'"
        )
    
    # Read file content
    content = await file.read()
    
    # Prepare options
    options = {
        "include_metadata": include_metadata,
        "include_structure": include_structure,
        "include_statistics": include_statistics
    }
    
    # Submit task
    task = extract_file_async.delay(
        content,
        file.filename,
        extraction_type,
        options
    )
    
    logger.info(
        "Extraction task submitted",
        task_id=task.id,
        filename=file.filename,
        extraction_type=extraction_type
    )
    
    return {
        "task_id": task.id,
        "status": "PENDING",
        "message": "Task submitted successfully"
    }


@router.get("/status/{task_id}",
    tags=["async"],
    summary="비동기 작업 상태 확인",
    responses={
        200: {
            "description": "작업 상태",
            "content": {
                "application/json": {
                    "examples": {
                        "pending": {
                            "value": {
                                "task_id": "550e8400-e29b-41d4-a716-446655440000",
                                "status": "PENDING",
                                "progress": None
                            }
                        },
                        "processing": {
                            "value": {
                                "task_id": "550e8400-e29b-41d4-a716-446655440000",
                                "status": "PROCESSING",
                                "progress": {"status": "Parsing file"}
                            }
                        },
                        "success": {
                            "value": {
                                "task_id": "550e8400-e29b-41d4-a716-446655440000",
                                "status": "SUCCESS",
                                "result": {"success": True, "content": {}}
                            }
                        }
                    }
                }
            }
        },
        404: {"description": "작업을 찾을 수 없음"}
    }
)
async def get_task_status(task_id: str) -> TaskStatus:
    """
    비동기 작업의 상태를 확인합니다.
    
    상태 값:
    - PENDING: 작업이 대기 중
    - PROCESSING: 작업이 진행 중
    - SUCCESS: 작업이 성공적으로 완료됨
    - FAILURE: 작업이 실패함
    """
    task = AsyncResult(task_id)
    
    if task.state == "PENDING":
        return TaskStatus(
            task_id=task_id,
            status=task.state,
            progress=None,
            message="Task is pending"
        )
    elif task.state == "PROCESSING":
        progress_info = task.info if isinstance(task.info, dict) else {}
        return TaskStatus(
            task_id=task_id,
            status=task.state,
            progress=progress_info.get('progress'),
            message=progress_info.get('status', 'Processing')
        )
    elif task.state == "SUCCESS":
        return TaskStatus(
            task_id=task_id,
            status=task.state,
            progress=100,
            message="Task completed successfully"
        )
    else:  # FAILURE
        return TaskStatus(
            task_id=task_id,
            status=task.state,
            progress=None,
            message=f"Task failed: {str(task.info)}"
        )


@router.get("/result/{task_id}",
    tags=["async"],
    summary="비동기 작업 결과 가져오기",
    responses={
        200: {"description": "작업 결과"},
        202: {"description": "작업이 아직 진행 중"},
        404: {"description": "작업을 찾을 수 없음"},
        500: {"description": "작업 실패"}
    }
)
async def get_task_result(task_id: str) -> TaskResult:
    """
    완료된 비동기 작업의 결과를 가져옵니다.
    
    작업이 아직 진행 중인 경우 202 상태 코드를 반환합니다.
    """
    task = AsyncResult(task_id)
    
    if task.state == "PENDING":
        raise HTTPException(
            status_code=202,
            detail="Task is still pending"
        )
    elif task.state == "PROCESSING":
        raise HTTPException(
            status_code=202,
            detail=f"Task is processing: {task.info.get('status', 'Unknown')}"
        )
    elif task.state == "SUCCESS":
        return TaskResult(
            task_id=task_id,
            status=task.state,
            result=task.result,
            error=None
        )
    else:  # FAILURE
        raise HTTPException(
            status_code=500,
            detail=f"Task failed: {str(task.info)}"
        )