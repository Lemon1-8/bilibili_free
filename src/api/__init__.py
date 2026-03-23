"""
API 路由定义
"""

from fastapi import APIRouter

from src.api.routes.health import health_router
from src.api.routes.video import video_router


router = APIRouter()


router.include_router(health_router, prefix="/health", tags=["健康检查"])
router.include_router(video_router, prefix="/api/v1", tags=["视频管理"])


__all__ = ["router"]
