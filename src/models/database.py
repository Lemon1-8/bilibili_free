"""
数据库模型定义
使用 SQLAlchemy ORM
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    BigInteger,
    String,
    Text,
    Float,
    DateTime,
    ForeignKey,
    Index,
    Boolean,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from src.core import get_config


Base = declarative_base()


class Video(Base):
    """
    视频表
    存储视频基本信息
    """
    __tablename__ = "videos"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    bvid = Column(String(20), unique=True, nullable=False, index=True)
    aid = Column(BigInteger, unique=True, nullable=False)
    
    # 视频信息
    title = Column(String(500), nullable=False)
    description = Column(Text)
    duration = Column(Integer, default=0)
    tname = Column(String(100))
    owner = Column(String(100))
    
    # 平台信息
    platform = Column(String(20), default="bilibili")
    
    # 文件路径
    local_path = Column(String(500))
    thumbnail_path = Column(String(500))
    
    # 状态
    status = Column(String(20), default="pending")
    downloaded = Column(Boolean, default=False)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    evaluations = relationship("Evaluation", back_populates="video", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="video", cascade="all, delete-orphan")
    subtitles = relationship("Subtitle", back_populates="video", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_videos_platform", "platform"),
        Index("idx_videos_status", "status"),
        Index("idx_videos_created", "created_at"),
    )


class Evaluation(Base):
    """
    评分表
    存储AI搞笑评分结果
    """
    __tablename__ = "evaluations"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(Integer, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    
    # 各维度评分
    humor_score = Column(Float, default=0.0)
    visual_score = Column(Float, default=0.0)
    audio_score = Column(Float, default=0.0)
    text_score = Column(Float, default=0.0)
    
    # 搞笑等级
    humor_level = Column(String(50))
    
    # 分析总结
    summary = Column(Text)
    
    # 搞笑元素
    funny_elements = Column(Text)
    
    # 模型版本
    model_version = Column(String(50))
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    video = relationship("Video", back_populates="evaluations")
    
    __table_args__ = (
        Index("idx_evaluations_video", "video_id"),
        Index("idx_evaluations_score", "humor_score"),
    )


class Comment(Base):
    """
    评论表
    存储视频评论
    """
    __tablename__ = "comments"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(Integer, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    
    # 评论信息
    rpid = Column(BigInteger, unique=True)
    mid = Column(BigInteger)
    uname = Column(String(100))
    content = Column(Text)
    like = Column(Integer, default=0)
    ctime = Column(BigInteger)
    rcount = Column(Integer, default=0)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    video = relationship("Video", back_populates="comments")
    
    __table_args__ = (
        Index("idx_comments_video", "video_id"),
    )


class Subtitle(Base):
    """
    字幕表
    存储视频字幕/弹幕
    """
    __tablename__ = "subtitles"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(Integer, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    
    # 字幕类型：subtitle(字幕) / danmu(弹幕)
    subtitle_type = Column(String(20), default="subtitle")
    
    # 字幕内容
    text = Column(Text)
    start_time = Column(Float, default=0.0)
    end_time = Column(Float, default=0.0)
    
    # 弹幕特有
    dmid = Column(BigInteger)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    video = relationship("Video", back_populates="subtitles")
    
    __table_args__ = (
        Index("idx_subtitles_video", "video_id"),
        Index("idx_subtitles_type", "subtitle_type"),
    )


class Database:
    """
    数据库管理类
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self.config = get_config().database
        
        # 创建同步引擎（用于开发环境）
        self.engine = create_engine(
            self.config.url,
            echo=self.config.echo,
            pool_pre_ping=True,
        )
        
        # 创建会话工厂
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
        )
    
    def create_tables(self):
        """创建所有表"""
        Base.metadata.create_all(bind=self.engine)
    
    def get_session(self) -> Session:
        """获取数据库会话"""
        return self.SessionLocal()
    
    def close(self):
        """关闭数据库连接"""
        self.engine.dispose()


# 全局数据库实例
_db_instance = None


def get_database() -> Database:
    """获取数据库实例"""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance


def get_db_session() -> Session:
    """获取数据库会话（依赖注入用）"""
    db = get_database()
    session = db.get_session()
    try:
        yield session
    finally:
        session.close()
