"""
主入口文件 - 视频搞笑检测系统
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.core import get_config, init_storage_dirs
from src.api import router


def setup_logging():
    """配置日志"""
    config = get_config()
    logging.basicConfig(
        level=getattr(logging, config.logging.level),
        format=config.logging.format,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    config = get_config()

    # 启动时初始化
    setup_logging()
    init_storage_dirs(config)

    logger = logging.getLogger(__name__)
    logger.info("视频搞笑检测系统启动...")

    yield

    # 关闭时清理
    logger.info("视频搞笑检测系统关闭...")


def create_app() -> FastAPI:
    """创建 FastAPI 应用"""
    config = get_config()

    app = FastAPI(
        title="视频搞笑检测系统",
        description="支持B站等平台的视频抓取、搞笑程度AI分析",
        version="1.0.0",
        lifespan=lifespan,
    )

    # 配置 CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    app.include_router(router)

    # 挂载前端静态文件
    frontend_path = Path(__file__).parent / "frontend"
    if frontend_path.exists():
        app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    config = get_config()
    uvicorn.run(
        "main:app",
        host=config.api.host,
        port=config.api.port,
        reload=config.api.debug,
    )
