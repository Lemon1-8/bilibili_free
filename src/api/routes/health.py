"""
健康检查路由
"""

from fastapi import APIRouter


health_router = APIRouter()


@health_router.get("")
async def health_check():
    """
    健康检查接口
    """
    return {"status": "ok", "service": "视频搞笑检测系统"}


@health_router.get("/ping")
async def ping():
    """
    Ping 接口
    """
    return {"message": "pong"}
