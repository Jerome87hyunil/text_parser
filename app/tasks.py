"""
Celery tasks for background processing
"""
import os
import tempfile
import structlog
from typing import Dict, Any
from celery import Task
from app.core.celery_app import celery_app
from app.services.hwp_parser import get_parser  # v1.1: 싱글톤 사용
from app.services.text_extractor import TextExtractor
from app.core.cache import CacheManager

logger = structlog.get_logger()


class CallbackTask(Task):
    """Task with callbacks for better error handling"""
    
    def on_success(self, retval, task_id, args, kwargs):
        """Success callback"""
        logger.info("Task completed successfully", task_id=task_id)
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Failure callback"""
        logger.error("Task failed", task_id=task_id, error=str(exc))


@celery_app.task(bind=True, base=CallbackTask, name="extract_file_async")
def extract_file_async(
    self,
    file_content: bytes,
    file_name: str,
    extraction_type: str,
    options: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Extract content from file asynchronously
    
    Args:
        file_content: File content as bytes
        file_name: Original file name
        extraction_type: Type of extraction (json, text, markdown)
        options: Extraction options
        
    Returns:
        Extracted content
    """
    temp_file_path = None
    
    try:
        # Update task state
        self.update_state(state="PROCESSING", meta={"status": "Saving file"})
        
        # Determine file extension
        file_ext = os.path.splitext(file_name)[1].lower()
        if file_ext not in ['.hwp', '.hwpx', '.pdf']:
            raise ValueError(f"Unsupported file type: {file_ext}")
        
        # Save file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
            tmp.write(file_content)
            temp_file_path = tmp.name
        
        # Update task state
        self.update_state(state="PROCESSING", meta={"status": "Parsing file"})
        
        # Initialize parser and extractor (v1.1: 싱글톤 사용으로 메모리 최적화)
        parser = get_parser()
        extractor = TextExtractor()
        
        # Parse file
        parsed_content = parser.parse(temp_file_path)
        
        # Update task state
        self.update_state(state="PROCESSING", meta={"status": "Extracting content"})
        
        # Extract based on type
        if extraction_type == "json":
            result = extractor.extract_structured(
                parsed_content,
                include_metadata=options.get("include_metadata", True),
                include_structure=options.get("include_structure", True),
                include_statistics=options.get("include_statistics", True)
            )
        elif extraction_type == "text":
            text = parser.extract_text(temp_file_path)
            if not options.get("preserve_formatting", False):
                text = ' '.join(text.split())
            result = {"text": text}
        elif extraction_type == "markdown":
            result = {
                "markdown": extractor.to_markdown(
                    parsed_content,
                    include_metadata=options.get("include_metadata", True)
                )
            }
        else:
            raise ValueError(f"Unknown extraction type: {extraction_type}")
        
        logger.info(
            "File extracted successfully",
            task_id=self.request.id,
            file_name=file_name,
            extraction_type=extraction_type
        )
        
        return {
            "success": True,
            "filename": file_name,
            "extraction_type": extraction_type,
            "content": result
        }
        
    except Exception as e:
        logger.error(
            "Extraction failed",
            task_id=self.request.id,
            file_name=file_name,
            error=str(e)
        )
        raise
        
    finally:
        # Cleanup
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)


@celery_app.task(bind=True, base=CallbackTask, name="process_large_file")
def process_large_file(
    self,
    file_path: str,
    processing_options: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Process large files that require more resources
    
    Args:
        file_path: Path to the file
        processing_options: Processing options
        
    Returns:
        Processing result
    """
    try:
        # Update task state
        self.update_state(
            state="PROCESSING",
            meta={
                "status": "Processing large file",
                "file_path": file_path
            }
        )
        
        # TODO: Implement large file processing logic
        # This could include:
        # - Chunked processing
        # - Memory-efficient parsing
        # - Progress reporting
        
        return {
            "success": True,
            "file_path": file_path,
            "message": "Large file processed successfully"
        }
        
    except Exception as e:
        logger.error(
            "Large file processing failed",
            task_id=self.request.id,
            file_path=file_path,
            error=str(e)
        )
        raise


@celery_app.task(name="cleanup_old_files")
def cleanup_old_files(directory: str, max_age_hours: int = 24) -> Dict[str, Any]:
    """
    Clean up old temporary files
    
    Args:
        directory: Directory to clean
        max_age_hours: Maximum age of files in hours
        
    Returns:
        Cleanup result
    """
    import time
    
    cleaned_count = 0
    current_time = time.time()
    max_age_seconds = max_age_hours * 3600
    
    try:
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            
            # Skip if not a file
            if not os.path.isfile(file_path):
                continue
            
            # Check file age
            file_age = current_time - os.path.getmtime(file_path)
            if file_age > max_age_seconds:
                try:
                    os.unlink(file_path)
                    cleaned_count += 1
                    logger.info("Deleted old file", file_path=file_path)
                except Exception as e:
                    logger.error("Failed to delete file", file_path=file_path, error=str(e))
        
        return {
            "success": True,
            "cleaned_count": cleaned_count,
            "directory": directory
        }
        
    except Exception as e:
        logger.error("Cleanup failed", directory=directory, error=str(e))
        raise