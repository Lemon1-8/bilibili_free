"""
视频管理 API 路由
"""

import logging
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.core import get_config
from src.models import get_db_session, Video, Evaluation, Comment, Subtitle
from src.services import get_bilibili_crawler, BilibiliParseError, get_minio_storage
from src.services.ai_analyzer import get_humor_analyzer
from src.services.video import get_video_processor, VideoProcessError


logger = logging.getLogger(__name__)
video_router = APIRouter()


# ============== 请求/响应模型 ==============

class VideoParseRequest(BaseModel):
    """解析视频请求"""
    url: str = Field(..., description="B站视频URL")


class VideoParseResponse(BaseModel):
    """解析视频响应"""
    bvid: str
    aid: int
    title: str
    description: str
    duration: int
    owner: str
    tname: str
    pic: str


class CommentResponse(BaseModel):
    """评论响应"""
    rpid: int
    uname: str
    content: str
    like: int
    ctime: int


class EvaluationResponse(BaseModel):
    """评分响应"""
    humor_score: float
    visual_score: float
    audio_score: float
    text_score: float
    humor_level: str
    summary: str
    funny_elements: List[str]


class VideoResponse(BaseModel):
    """视频响应"""
    id: int
    bvid: str
    title: str
    description: Optional[str]
    duration: int
    owner: str
    tname: str
    platform: str
    status: str
    downloaded: bool
    local_path: Optional[str]
    thumbnail_path: Optional[str]
    humor_score: Optional[float]
    humor_level: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class VideoDetailResponse(VideoResponse):
    """视频详情响应"""
    evaluations: List[EvaluationResponse] = []
    comments: List[CommentResponse] = []
    danmu_count: int = 0
    comment_count: int = 0

    class Config:
        from_attributes = True


# ============== API 路由 ==============

@video_router.post("/parse", response_model=VideoParseResponse)
async def parse_video(
    request: VideoParseRequest,
    db: Session = Depends(get_db_session),
):
    """
    解析B站视频URL，获取视频信息
    
    Args:
        request: 包含视频URL的请求
        db: 数据库会话
        
    Returns:
        VideoParseResponse: 视频基本信息
    """
    try:
        crawler = get_bilibili_crawler()
        video_info = crawler.parse_url(request.url)
        crawler.close()
        
        return VideoParseResponse(**video_info)
        
    except BilibiliParseError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"解析视频失败: {e}")
        raise HTTPException(status_code=500, detail="解析视频失败")


@video_router.post("/download/{bvid}")
async def download_video(
    bvid: str,
    db: Session = Depends(get_db_session),
    background_tasks: BackgroundTasks = None,
):
    """
    下载视频（同步版本，直接下载）
    
    Args:
        bvid: BV号
        db: 数据库会话
        
    Returns:
        dict: 下载结果
    """
    try:
        config = get_config()
        crawler = get_bilibili_crawler()
        
        # 获取视频信息
        video_info = crawler._get_video_info(bvid)
        
        # 检查是否已存在
        existing = db.query(Video).filter(Video.bvid == bvid).first()
        
        if existing:
            if existing.downloaded and existing.local_path:
                return {
                    "message": "视频已存在",
                    "video_id": existing.id,
                    "local_path": existing.local_path,
                }
        
        # 保存到数据库
        if not existing:
            video = Video(
                bvid=video_info["bvid"],
                aid=video_info["aid"],
                title=video_info["title"],
                description=video_info["description"],
                duration=video_info["duration"],
                owner=video_info["owner"],
                tname=video_info["tname"],
                platform="bilibili",
                status="downloading",
            )
            db.add(video)
            db.commit()
            db.refresh(video)
        else:
            video = existing
            video.status = "downloading"
            db.commit()
        
        # 下载视频
        video_dir = Path(config.storage.video_dir)
        video_dir.mkdir(parents=True, exist_ok=True)
        
        video_path = video_dir / f"{bvid}.mp4"
        
        try:
            crawler.download_video(bvid, str(video_path))
        except Exception as e:
            logger.warning(f"直接下载失败，尝试其他方式: {e}")
            raise HTTPException(status_code=501, detail="视频下载暂不可用，请稍后重试")
        
        # 下载缩略图
        thumbnail_dir = Path(config.storage.thumbnail_dir)
        thumbnail_dir.mkdir(parents=True, exist_ok=True)
        thumbnail_path = thumbnail_dir / f"{bvid}.jpg"
        
        crawler.get_thumbnail(video_info["pic"], str(thumbnail_path))
        crawler.close()
        
        # 更新视频状态
        video.local_path = str(video_path)
        video.thumbnail_path = str(thumbnail_path)
        video.downloaded = True
        video.status = "downloaded"
        db.commit()
        
        return {
            "message": "下载成功",
            "video_id": video.id,
            "local_path": str(video_path),
            "thumbnail_path": str(thumbnail_path),
        }
        
    except BilibiliParseError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"下载视频失败: {e}")
        raise HTTPException(status_code=500, detail=f"下载失败: {str(e)}")


@video_router.get("/{video_id}", response_model=VideoDetailResponse)
async def get_video(
    video_id: int,
    db: Session = Depends(get_db_session),
):
    """
    获取视频详情
    
    Args:
        video_id: 视频ID
        db: 数据库会话
        
    Returns:
        VideoDetailResponse: 视频详情
    """
    video = db.query(Video).filter(Video.id == video_id).first()

    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    # 获取评分
    evaluations = db.query(Evaluation).filter(Evaluation.video_id == video_id).all()

    # 获取评论
    comments = db.query(Comment).filter(Comment.video_id == video_id).order_by(Comment.like.desc()).limit(1000).all()

    # 获取弹幕数量
    danmu_count = db.query(Subtitle).filter(
        Subtitle.video_id == video_id,
        Subtitle.subtitle_type == "danmu"
    ).count()

    evaluation_responses = [
        EvaluationResponse(
            humor_score=ev.humor_score,
            visual_score=ev.visual_score,
            audio_score=ev.audio_score,
            text_score=ev.text_score,
            humor_level=ev.humor_level or "unknown",
            summary=ev.summary or "",
            funny_elements=ev.funny_elements.split(",") if ev.funny_elements else [],
        )
        for ev in evaluations
    ]

    comment_responses = [
        CommentResponse(
            rpid=c.rpid,
            uname=c.uname,
            content=c.content,
            like=c.like,
            ctime=c.ctime,
        )
        for c in comments
    ]

    humor_score = evaluations[0].humor_score if evaluations else None
    humor_level = evaluations[0].humor_level if evaluations else None

    return VideoDetailResponse(
        id=video.id,
        bvid=video.bvid,
        title=video.title,
        description=video.description,
        duration=video.duration,
        owner=video.owner,
        tname=video.tname,
        platform=video.platform,
        status=video.status,
        downloaded=video.downloaded,
        local_path=video.local_path,
        thumbnail_path=video.thumbnail_path,
        humor_score=humor_score,
        humor_level=humor_level,
        created_at=video.created_at,
        evaluations=evaluation_responses,
        comments=comment_responses,
        danmu_count=danmu_count,
        comment_count=len(comments),
    )


@video_router.get("/")
async def list_videos(
    page: int = 1,
    page_size: int = 20,
    platform: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db_session),
):
    """
    获取视频列表
    
    Args:
        page: 页码
        page_size: 每页数量
        platform: 平台筛选
        status: 状态筛选
        db: 数据库会话
        
    Returns:
        dict: 视频列表和分页信息
    """
    query = db.query(Video)
    
    if platform:
        query = query.filter(Video.platform == platform)
    
    if status:
        query = query.filter(Video.status == status)
    
    total = query.count()
    
    videos = (
        query
        .order_by(Video.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    
    # 获取每个视频的最新评分
    result = []
    for video in videos:
        evaluation = (
            db.query(Evaluation)
            .filter(Evaluation.video_id == video.id)
            .order_by(Evaluation.created_at.desc())
            .first()
        )
        
        result.append(
            VideoResponse(
                id=video.id,
                bvid=video.bvid,
                title=video.title,
                description=video.description,
                duration=video.duration,
                owner=video.owner,
                tname=video.tname,
                platform=video.platform,
                status=video.status,
                downloaded=video.downloaded,
                local_path=video.local_path,
                thumbnail_path=video.thumbnail_path,
                humor_score=evaluation.humor_score if evaluation else None,
                humor_level=evaluation.humor_level if evaluation else None,
                created_at=video.created_at,
            )
        )
    
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "videos": result,
    }


@video_router.post("/analyze/{video_id}")
async def analyze_video(
    video_id: int,
    db: Session = Depends(get_db_session),
):
    """
    分析视频搞笑程度
    
    Args:
        video_id: 视频ID
        db: 数据库会话
        
    Returns:
        dict: 分析结果
    """
    video = db.query(Video).filter(Video.id == video_id).first()
    
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    
    try:
        analyzer = get_humor_analyzer()
        
        # 获取字幕和弹幕
        subtitles = (
            db.query(Subtitle)
            .filter(Subtitle.video_id == video_id, Subtitle.subtitle_type == "subtitle")
            .all()
        )
        danmus = (
            db.query(Subtitle)
            .filter(Subtitle.video_id == video_id, Subtitle.subtitle_type == "danmu")
            .all()
        )
        comments = db.query(Comment).filter(Comment.video_id == video_id).all()
        
        subtitle_texts = [s.text for s in subtitles if s.text]
        danmu_texts = [d.text for d in danmus if d.text]
        comment_texts = [c.content for c in comments if c.content]
        
        # AI 分析
        result = analyzer.analyze_video_humor(
            title=video.title,
            description=video.description or "",
            subtitles=subtitle_texts,
            comments=comment_texts,
            danmu=danmu_texts,
        )
        
        # 保存评分结果
        evaluation = Evaluation(
            video_id=video_id,
            humor_score=result.humor_score,
            visual_score=result.visual_score,
            audio_score=result.audio_score,
            text_score=result.text_score,
            humor_level=result.humor_level,
            summary=result.summary,
            funny_elements=",".join(result.funny_elements),
            model_version="deepseek-chat-v1",
        )
        db.add(evaluation)
        db.commit()
        
        return {
            "message": "分析完成",
            "evaluation": EvaluationResponse(
                humor_score=result.humor_score,
                visual_score=result.visual_score,
                audio_score=result.audio_score,
                text_score=result.text_score,
                humor_level=result.humor_level,
                summary=result.summary,
                funny_elements=result.funny_elements,
            ),
        }
        
    except Exception as e:
        logger.error(f"分析视频失败: {e}")
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


@video_router.post("/collect/{bvid}")
async def collect_video_data(
    bvid: str,
    db: Session = Depends(get_db_session),
):
    """
    采集视频完整数据（信息+评论+弹幕+评分）
    
    Args:
        bvid: BV号
        db: 数据库会话
        
    Returns:
        dict: 采集结果
    """
    try:
        crawler = get_bilibili_crawler()
        
        # 1. 获取视频信息
        video_info = crawler._get_video_info(bvid)
        
        # 2. 检查/创建视频记录
        video = db.query(Video).filter(Video.bvid == bvid).first()
        
        if not video:
            video = Video(
                bvid=video_info["bvid"],
                aid=video_info["aid"],
                title=video_info["title"],
                description=video_info["description"],
                duration=video_info["duration"],
                owner=video_info["owner"],
                tname=video_info["tname"],
                platform="bilibili",
                status="collected",
            )
            db.add(video)
            db.commit()
            db.refresh(video)
        
        # 3. 获取弹幕
        existing_danmu = db.query(Subtitle).filter(
            Subtitle.video_id == video.id,
            Subtitle.subtitle_type == "danmu"
        ).count()
        
        if existing_danmu == 0:
            danmu_list = crawler.get_danmu(video_info["cid"])
            
            for dm in danmu_list:
                subtitle = Subtitle(
                    video_id=video.id,
                    subtitle_type="danmu",
                    text=dm["text"],
                    start_time=dm["time"],
                    dmid=dm.get("dmid"),
                )
                db.add(subtitle)
            
            db.commit()
            logger.info(f"采集弹幕 {len(danmu_list)} 条")

        # 获取认证配置（用于评论和视频下载）
        auth_config = get_config().bilibili_auth

        # 4. 获取评论
        existing_rpids = set(
            row[0] for row in db.query(Comment.rpid).filter(
                Comment.video_id == video.id
            ).all()
        )

        if len(existing_rpids) < 100:
            comments_data = crawler.get_all_comments(
                video_info["aid"],
                max_pages=10,
                cookies=auth_config.to_cookies() if auth_config.has_auth() else None,
            )

            new_comments = []
            for cm in comments_data:
                if cm["rpid"] not in existing_rpids:
                    new_comments.append(Comment(
                        video_id=video.id,
                        rpid=cm["rpid"],
                        mid=cm["mid"],
                        uname=cm["uname"],
                        content=cm["content"],
                        like=cm["like"],
                        ctime=cm["ctime"],
                        rcount=cm["rcount"],
                    ))
                    existing_rpids.add(cm["rpid"])

            if new_comments:
                db.add_all(new_comments)
                db.commit()
                logger.info(f"采集评论 {len(new_comments)} 条")

        # 5. 下载视频并上传到 MinIO
        minio_storage = get_minio_storage()
        video_local_path = None

        if not video.downloaded:
            try:
                # 尝试下载视频
                config = get_config()
                video_dir = Path(config.storage.video_dir)
                video_dir.mkdir(parents=True, exist_ok=True)

                video_path = video_dir / f"{bvid}.mp4"

                # 下载视频到本地临时目录（传入CID和Cookie）
                crawler.download_video(
                    bvid=bvid,
                    save_path=str(video_path),
                    cid=video_info["cid"],
                    cookies=auth_config.to_cookies() if auth_config.has_auth() else None,
                )
                video_local_path = str(video_path)

                # 上传到 MinIO
                minio_url = minio_storage.upload_video(
                    file_path=str(video_path),
                    object_name=f"videos/{bvid}.mp4",
                )

                if minio_url:
                    video.local_path = minio_url
                    logger.info(f"视频已上传到 MinIO: {minio_url}")
                else:
                    # MinIO 上传失败，保留本地路径
                    video.local_path = str(video_path)
                    logger.warning("MinIO 上传失败，保留本地路径")

                # 下载缩略图
                thumbnail_dir = Path(config.storage.thumbnail_dir)
                thumbnail_dir.mkdir(parents=True, exist_ok=True)
                thumbnail_path = thumbnail_dir / f"{bvid}.jpg"

                crawler.get_thumbnail(video_info["pic"], str(thumbnail_path))

                # 上传缩略图到 MinIO
                thumbnail_minio_url = minio_storage.upload_file(
                    file_path=str(thumbnail_path),
                    object_name=f"thumbnails/{bvid}.jpg",
                    content_type="image/jpeg",
                )

                if thumbnail_minio_url:
                    video.thumbnail_path = thumbnail_minio_url
                else:
                    video.thumbnail_path = str(thumbnail_path)

                video.downloaded = True
                video.status = "downloaded"

            except Exception as e:
                logger.warning(f"视频下载失败: {e}")
                video.status = "download_failed"

        db.commit()

        crawler.close()

        return {
            "message": "采集完成",
            "video_id": video.id,
            "bvid": bvid,
            "title": video.title,
            "local_path": video.local_path,
            "thumbnail_path": video.thumbnail_path,
            "downloaded": video.downloaded,
        }
        
    except BilibiliParseError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"采集视频数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"采集失败: {str(e)}")


@video_router.delete("/{video_id}")
async def delete_video(
    video_id: int,
    db: Session = Depends(get_db_session),
):
    """
    删除视频
    
    Args:
        video_id: 视频ID
        db: 数据库会话
        
    Returns:
        dict: 删除结果
    """
    video = db.query(Video).filter(Video.id == video_id).first()
    
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    
    # 删除本地文件
    if video.local_path:
        try:
            Path(video.local_path).unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"删除视频文件失败: {e}")
    
    if video.thumbnail_path:
        try:
            Path(video.thumbnail_path).unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"删除缩略图失败: {e}")
    
    # 删除数据库记录
    db.delete(video)
    db.commit()
    
    return {"message": "删除成功", "video_id": video_id}
