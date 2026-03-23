"""
核心模块
"""

from .config import AppConfig, get_config, load_config, init_storage_dirs

__all__ = ["AppConfig", "get_config", "load_config", "init_storage_dirs"]
