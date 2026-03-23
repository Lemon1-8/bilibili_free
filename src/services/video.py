"""
视频处理服务
使用 FFmpeg 进行视频处理，包括提取帧、音频、缩略图等
"""

import logging
import subprocess
from pathlib import Path
from typing import Optional, List, Tuple

from src.core import get_config


logger = logging.getLogger(__name__)


class VideoProcessError(Exception):
    """视频处理错误"""
    pass


class VideoProcessor:
    """
    视频处理器
    使用 FFmpeg 进行视频处理
    """
    
    def __init__(self):
        self.config = get_config().ffmpeg
        self._verify_ffmpeg()
    
    def _verify_ffmpeg(self) -> None:
        """验证 FFmpeg 是否可用"""
        try:
            subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            raise VideoProcessError(
                "FFmpeg 未安装或不可用，请先安装 FFmpeg: https://ffmpeg.org/download.html"
            )
    
    def _get_ffmpeg_cmd(self) -> List[str]:
        """获取 FFmpeg 命令"""
        if self.config.path and Path(self.config.path).exists():
            return [str(Path(self.config.path))]
        return ["ffmpeg"]
    
    def _get_ffprobe_cmd(self) -> List[str]:
        """获取 FFprobe 命令"""
        if self.config.path:
            ffprobe_path = Path(self.config.path).parent / "ffprobe"
            if ffprobe_path.exists():
                return [str(ffprobe_path)]
        return ["ffprobe"]
    
    def extract_frames(
        self,
        video_path: str,
        output_dir: str,
        interval: Optional[int] = None,
        max_frames: Optional[int] = None,
    ) -> List[str]:
        """
        从视频中提取帧图片
        
        Args:
            video_path: 视频文件路径
            output_dir: 输出目录
            interval: 提取间隔（秒），默认使用配置
            max_frames: 最大提取帧数，默认使用配置
            
        Returns:
            List[str]: 提取的帧图片路径列表
        """
        video_path = Path(video_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        if interval is None:
            interval = self.config.frame_interval
        if max_frames is None:
            max_frames = self.config.max_frames
        
        # 获取视频时长
        duration = self.get_duration(str(video_path))
        
        # 计算需要提取的时间点
        times = []
        current_time = 0.0
        frame_count = 0
        
        while current_time < duration and frame_count < max_frames:
            times.append(current_time)
            current_time += interval
            frame_count += 1
        
        # 提取帧
        frame_paths = []
        
        for i, timestamp in enumerate(times):
            output_path = output_dir / f"frame_{i:04d}.jpg"
            
            cmd = [
                *self._get_ffmpeg_cmd(),
                "-ss", str(timestamp),
                "-i", str(video_path),
                "-vframes", "1",
                "-q:v", "2",
                "-y",
                str(output_path),
            ]
            
            try:
                subprocess.run(
                    cmd,
                    capture_output=True,
                    check=True,
                )
                frame_paths.append(str(output_path))
            except subprocess.CalledProcessError as e:
                logger.warning(f"提取帧失败 {output_path}: {e.stderr.decode() if e.stderr else e}")
                continue
        
        return frame_paths
    
    def extract_audio(
        self,
        video_path: str,
        output_path: str,
        format: str = "wav",
    ) -> str:
        """
        从视频中提取音频
        
        Args:
            video_path: 视频文件路径
            output_path: 输出路径
            format: 音频格式，默认 wav
            
        Returns:
            str: 输出的音频文件路径
        """
        video_path = Path(video_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        cmd = [
            *self._get_ffmpeg_cmd(),
            "-i", str(video_path),
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            "-y",
            str(output_path),
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            return str(output_path)
        except subprocess.CalledProcessError as e:
            raise VideoProcessError(f"音频提取失败: {e.stderr.decode() if e.stderr else str(e)}")
    
    def generate_thumbnail(
        self,
        video_path: str,
        output_path: str,
        timestamp: float = 0,
        size: Optional[str] = None,
    ) -> str:
        """
        生成视频缩略图
        
        Args:
            video_path: 视频文件路径
            output_path: 输出路径
            timestamp: 截取时间点（秒）
            size: 缩略图大小，默认使用配置
            
        Returns:
            str: 缩略图路径
        """
        video_path = Path(video_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if size is None:
            size = self.config.thumbnail_size
        
        cmd = [
            *self._get_ffmpeg_cmd(),
            "-ss", str(timestamp),
            "-i", str(video_path),
            "-vframes", "1",
            "-s", size,
            "-q:v", "2",
            "-y",
            str(output_path),
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            return str(output_path)
        except subprocess.CalledProcessError as e:
            raise VideoProcessError(f"缩略图生成失败: {e.stderr.decode() if e.stderr else str(e)}")
    
    def get_duration(self, video_path: str) -> float:
        """
        获取视频时长
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            float: 视频时长（秒）
        """
        cmd = [
            *self._get_ffprobe_cmd(),
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, check=True, text=True)
            return float(result.stdout.strip())
        except subprocess.CalledProcessError as e:
            raise VideoProcessError(f"获取视频时长失败: {e}")
    
    def get_video_info(self, video_path: str) -> dict:
        """
        获取视频详细信息
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            dict: 视频信息
        """
        cmd = [
            *self._get_ffprobe_cmd(),
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(video_path),
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, check=True, text=True)
            import json
            return json.loads(result.stdout)
        except subprocess.CalledProcessError as e:
            raise VideoProcessError(f"获取视频信息失败: {e}")
        except json.JSONDecodeError as e:
            raise VideoProcessError(f"解析视频信息失败: {e}")
    
    def compress_video(
        self,
        video_path: str,
        output_path: str,
        crf: int = 28,
    ) -> str:
        """
        压缩视频
        
        Args:
            video_path: 输入视频路径
            output_path: 输出视频路径
            crf: 质量参数，值越小质量越高（18-28之间）默认28
            
        Returns:
            str: 压缩后的视频路径
        """
        video_path = Path(video_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        cmd = [
            *self._get_ffmpeg_cmd(),
            "-i", str(video_path),
            "-vcodec", "libx264",
            "-crf", str(crf),
            "-preset", "medium",
            "-acodec", "aac",
            "-y",
            str(output_path),
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            return str(output_path)
        except subprocess.CalledProcessError as e:
            raise VideoProcessError(f"视频压缩失败: {e.stderr.decode() if e.stderr else str(e)}")


def get_video_processor() -> VideoProcessor:
    """
    获取视频处理器实例
    
    Returns:
        VideoProcessor: 视频处理器实例
    """
    return VideoProcessor()
