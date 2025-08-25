from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from contextlib import asynccontextmanager
import structlog
import os

from app.core.config import settings
from app.api.v1.api import api_router
from app.core.cache import cache_manager
from app.utils.memory_manager import memory_manager
from app.core.exceptions import HWPAPIException
from app.core.error_handlers import (
    hwpapi_exception_handler,
    validation_exception_handler,
    http_exception_handler,
    general_exception_handler
)
import asyncio


# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer() if settings.LOG_FORMAT == "json" else structlog.dev.ConsoleRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up", project=settings.PROJECT_NAME, version=settings.VERSION)
    
    # Create directories
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
    
    # Skip cache initialization if Redis is not available
    try:
        if settings.CACHE_ENABLED and settings.REDIS_URL:
            await cache_manager.connect()
            logger.info("Cache connected")
    except Exception as e:
        logger.warning(f"Cache connection failed: {e}, continuing without cache")
    
    # Skip memory monitoring for now to simplify startup
    # memory_task = asyncio.create_task(memory_manager.monitor_memory_async())
    
    yield
    
    # Shutdown
    # memory_task.cancel()
    try:
        await cache_manager.disconnect()
    except:
        pass
    logger.info("Shutting down")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="HWP/HWPX/PDF 파일에서 텍스트를 추출하여 AI 분석을 위한 구조화된 데이터로 변환하는 API",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name": "extract",
            "description": "문서에서 텍스트 및 구조화된 데이터를 추출하는 엔드포인트",
        },
        {
            "name": "health",
            "description": "서버 상태 확인 엔드포인트",
        }
    ]
)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add exception handlers
app.add_exception_handler(HWPAPIException, hwpapi_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Include routers
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/", tags=["health"], summary="API 정보 확인")
async def root():
    """
    API 기본 정보를 반환합니다.
    
    Returns:
        project: 프로젝트 이름
        version: API 버전
        status: 서버 상태
        docs: API 문서 URL
    """
    return {
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "healthy",
        "docs": "/docs"
    }


@app.get("/health", tags=["health"], summary="헬스 체크")
async def health_check():
    """
    서버 상태를 확인합니다.
    
    Returns:
        status: 서버 상태 (healthy/unhealthy)
    """
    return {"status": "healthy"}