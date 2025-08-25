"""
Security-related endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict

from app.api.v1.endpoints.auth import get_current_active_user
from app.models.auth import User
from app.utils.virus_scanner import virus_scanner
from app.middleware.rate_limit_fixed import rate_limit_dependency
from app.models.status import VirusScanStats, SecurityStatus

router = APIRouter()


@router.get("/virus-scan/stats",
    tags=["security"],
    summary="바이러스 스캔 통계",
    dependencies=[Depends(rate_limit_dependency)],
)
async def get_virus_scan_stats() -> VirusScanStats:
    """
    Get virus scanning statistics
    """
    stats = await virus_scanner.get_scan_stats()
    return VirusScanStats(
        total_scans=stats.get('total_scans', 0),
        threats_detected=stats.get('threats_detected', 0),
        files_cleaned=stats.get('files_cleaned', 0),
        files_quarantined=stats.get('files_quarantined', 0),
        last_scan=stats.get('last_scan'),
        scan_engine=stats.get('scan_engine', 'custom'),
        engine_version=stats.get('engine_version')
    )


@router.get("/security/status",
    tags=["security"],
    summary="보안 상태 확인",
    dependencies=[Depends(get_current_active_user)],
)
async def get_security_status(current_user: User = Depends(get_current_active_user)) -> SecurityStatus:
    """
    Get overall security status (authenticated users only)
    """
    scan_stats = await virus_scanner.get_scan_stats()
    
    return SecurityStatus(
        virus_scanning_enabled=True,
        rate_limiting_enabled=True,
        authentication_enabled=True,
        encryption_enabled=True,
        security_level="high",
        last_security_check=scan_stats.get('last_scan'),
        threats_detected=scan_stats.get('threats_detected', 0)
    )