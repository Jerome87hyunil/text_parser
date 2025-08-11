from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
import structlog
import os
import uuid
from pathlib import Path

from app.core.config import settings
from app.services.hwp_converter import HWPConverter
from app.schemas.convert import ConvertResponse

router = APIRouter()
logger = structlog.get_logger()


@router.post("/hwp-to-pdf", response_model=ConvertResponse)
async def convert_hwp_to_pdf(
    file: UploadFile = File(..., description="HWP file to convert")
):
    """
    Convert HWP file to PDF format.
    
    - **file**: HWP file to be converted (max 10MB)
    
    Returns the converted PDF file.
    """
    # Validate file extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed types: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )
    
    # Validate file size
    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {settings.MAX_UPLOAD_SIZE / 1024 / 1024}MB"
        )
    
    # Generate unique filename
    file_id = str(uuid.uuid4())
    input_path = os.path.join(settings.UPLOAD_DIR, f"{file_id}{file_ext}")
    output_path = os.path.join(settings.OUTPUT_DIR, f"{file_id}.pdf")
    
    try:
        # Save uploaded file
        with open(input_path, "wb") as f:
            f.write(content)
        
        logger.info("File uploaded", file_id=file_id, filename=file.filename, size=len(content))
        
        # Convert HWP to PDF
        converter = HWPConverter()
        success = await converter.convert(input_path, output_path)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Conversion failed"
            )
        
        logger.info("Conversion completed", file_id=file_id)
        
        # Return the PDF file
        return FileResponse(
            path=output_path,
            filename=f"{Path(file.filename).stem}.pdf",
            media_type="application/pdf"
        )
        
    except Exception as e:
        logger.error("Conversion error", error=str(e), file_id=file_id)
        raise HTTPException(
            status_code=500,
            detail=f"Conversion error: {str(e)}"
        )
    
    finally:
        # Cleanup uploaded file
        if os.path.exists(input_path):
            os.remove(input_path)