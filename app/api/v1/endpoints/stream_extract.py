"""
Streaming extraction endpoints for large files
"""
import structlog
from fastapi import APIRouter, File, UploadFile, HTTPException, Query
from fastapi.responses import StreamingResponse
from typing import AsyncIterator
import json

from app.core.config import get_settings
from app.services.stream_parser import StreamParser

logger = structlog.get_logger()
router = APIRouter()
settings = get_settings()


async def generate_json_stream(chunks: AsyncIterator[dict]) -> AsyncIterator[bytes]:
    """Generate JSON streaming response"""
    yield b'{"chunks": ['
    first = True
    
    async for chunk in chunks:
        if not first:
            yield b','
        first = False
        yield json.dumps(chunk, ensure_ascii=False).encode('utf-8')
    
    yield b']}'


@router.post("/stream/extract",
    tags=["stream"],
    summary="대용량 파일 스트리밍 추출",
    responses={
        200: {
            "description": "스트리밍 응답",
            "content": {
                "application/json": {
                    "example": {
                        "chunks": [
                            {"type": "metadata", "data": {}},
                            {"type": "text", "data": "content..."},
                            {"type": "complete", "stats": {}}
                        ]
                    }
                }
            }
        }
    }
)
async def stream_extract(
    file: UploadFile = File(..., description="대용량 파일"),
    chunk_size: int = Query(8192, description="청크 크기 (bytes)")
):
    """
    대용량 파일을 스트리밍 방식으로 처리합니다.
    
    메모리 사용을 최소화하면서 파일을 처리합니다.
    """
    # Validate file extension
    file_ext = file.filename.lower().split('.')[-1]
    if file_ext not in ['hwp', 'hwpx', 'pdf', 'txt']:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file_ext}"
        )
    
    parser = StreamParser(chunk_size=chunk_size)
    
    async def file_stream():
        """Read file in chunks"""
        while chunk := await file.read(chunk_size):
            yield chunk
    
    # Save and process file using streaming
    async with parser.save_uploaded_file_stream(file_stream(), f".{file_ext}") as temp_path:
        chunks = parser.parse_file_chunks(temp_path)
        
        return StreamingResponse(
            generate_json_stream(chunks),
            media_type="application/json",
            headers={
                "X-Content-Type-Options": "nosniff",
                "X-Filename": file.filename
            }
        )