"""
视频搞笑检测系统 - 核心配置模块
负责加载和验证配置文件
"""

import os
from pathlib import Path
from typing import Optional
from functools import lru_cache

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class APIConfig(BaseModel):
    """API 服务器配置"""
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False


class DatabaseConfig(BaseModel):
    """数据库配置"""
    url: str = "sqlite:///./data/humor_detect.db"
    echo: bool = False


class DeepSeekConfig(BaseModel):
    """Deep Seek API 配置"""
    api_key: str
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"
    temperature: float = 0.7
    max_tokens: int = 2000


class BilibiliConfig(BaseModel):
    """B站爬虫配置"""
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    timeout: int = 30
    retry_times: int = 3
    headers: dict = Field(default_factory=lambda: {"referer": "https://www.bilibili.com"})


class BilibiliAuthConfig(BaseModel):
    """B站登录认证配置"""
    sessdata: str = ""
    bili_jct: str = ""
    buvid3: str = ""

    def to_cookies(self) -> dict:
        """转换为 Cookie 字典"""
        cookies = {}
        if self.sessdata:
            cookies["SESSDATA"] = self.sessdata
        if self.bili_jct:
            cookies["bili_jct"] = self.bili_jct
        if self.buvid3:
            cookies["buvid3"] = self.buvid3
        return cookies

    def has_auth(self) -> bool:
        """是否配置了认证信息"""
        return bool(self.sessdata)


class FFmpegConfig(BaseModel):
    """FFmpeg 配置"""
    path: str = ""
    frame_interval: int = 1
    max_frames: int = 30
    thumbnail_size: str = "320x180"


class StorageConfig(BaseModel):
    """存储路径配置"""
    video_dir: str = "./data/videos"
    thumbnail_dir: str = "./data/thumbnails"
    audio_dir: str = "./data/audio"
    subtitle_dir: str = "./data/subtitles"


class MinioConfig(BaseModel):
    """MinIO 配置"""
    endpoint: str = "localhost:9000"
    access_key: str = "admin"
    secret_key: str = "123456789"
    bucket: str = "humor-videos"
    secure: bool = False


class AIAnalysisConfig(BaseModel):
    """AI 分析配置"""
    humor_threshold: float = 60.0
    weights: dict = Field(default_factory=lambda: {
        "visual": 0.3,
        "audio": 0.3,
        "text": 0.4
    })


class LoggingConfig(BaseModel):
    """日志配置"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: str = "./logs/app.log"


class AppConfig(BaseModel):
    """应用配置"""
    api: APIConfig
    database: DatabaseConfig
    deepseek: DeepSeekConfig
    bilibili: BilibiliConfig
    bilibili_auth: BilibiliAuthConfig
    ffmpeg: FFmpegConfig
    minio: MinioConfig
    storage: StorageConfig
    ai_analysis: AIAnalysisConfig
    logging: LoggingConfig


_ENV_SECRETS = {
    "DEEPSEEK_API_KEY": ("deepseek", "api_key"),
    "BILIBILI_SESSDATA": ("bilibili_auth", "sessdata"),
    "BILIBILI_JCT": ("bilibili_auth", "bili_jct"),
    "BILIBILI_BUVID3": ("bilibili_auth", "buvid3"),
}


def _apply_env_overrides(config_dict: dict) -> dict:
    """环境变量优先于配置文件，避免密钥写入仓库"""
    for env_name, (section, key) in _ENV_SECRETS.items():
        value = os.environ.get(env_name)
        if value:
            config_dict.setdefault(section, {})[key] = value
    return config_dict


def load_config(config_path: Optional[str] = None) -> AppConfig:
    """
    加载配置文件

    Args:
        config_path: 配置文件路径，默认为 config/config.yaml

    Returns:
        AppConfig: 应用配置对象
    """
    if config_path is None:
        config_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"

    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config_dict = yaml.safe_load(f) or {}

    config_dict = _apply_env_overrides(config_dict)

    return AppConfig(**config_dict)


@lru_cache()
def get_config() -> AppConfig:
    """
    获取应用配置（单例模式）
    
    Returns:
        AppConfig: 应用配置对象
    """
    return load_config()


def init_storage_dirs(config: AppConfig) -> None:
    """
    初始化存储目录
    
    Args:
        config: 应用配置对象
    """
    dirs = [
        config.storage.video_dir,
        config.storage.thumbnail_dir,
        config.storage.audio_dir,
        config.storage.subtitle_dir,
    ]
    
    for dir_path in dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
