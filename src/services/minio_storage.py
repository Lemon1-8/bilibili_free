"""
MinIO 存储服务
负责视频文件上传到 MinIO 对象存储
"""

import logging
import io
from typing import Optional
from pathlib import Path

from minio import Minio
from minio.error import S3Error

from src.core import get_config


logger = logging.getLogger(__name__)


class MinioStorageError(Exception):
    """MinIO 存储错误"""
    pass


class MinioStorage:
    """
    MinIO 存储客户端

    提供视频文件上传、下载、删除等操作
    """

    def __init__(self):
        self.config = get_config().minio
        self._client: Optional[Minio] = None
        self._bucket_initialized = False

    @property
    def client(self) -> Minio:
        """
        获取 MinIO 客户端（懒加载）

        Returns:
            Minio: MinIO 客户端实例
        """
        if self._client is None:
            self._client = Minio(
                endpoint=self.config.endpoint,
                access_key=self.config.access_key,
                secret_key=self.config.secret_key,
                secure=self.config.secure,
            )
        return self._client

    def ensure_bucket(self) -> bool:
        """
        确保 bucket 存在，不存在则创建

        Returns:
            bool: 是否成功
        """
        if self._bucket_initialized:
            return True

        try:
            if not self.client.bucket_exists(self.config.bucket):
                self.client.make_bucket(self.config.bucket)
                logger.info(f"创建 MinIO bucket: {self.config.bucket}")
            self._bucket_initialized = True
            return True
        except S3Error as e:
            logger.error(f"检查/创建 bucket 失败: {e}")
            return False
        except Exception as e:
            logger.error(f"MinIO 连接失败: {e}")
            return False

    def upload_video(
        self,
        file_path: str,
        object_name: Optional[str] = None,
    ) -> Optional[str]:
        """
        上传视频文件到 MinIO

        Args:
            file_path: 本地文件路径
            object_name: MinIO 中的对象名称（默认使用文件名）

        Returns:
            str: MinIO 中的对象访问URL，失败返回 None
        """
        if not self.ensure_bucket():
            return None

        local_path = Path(file_path)
        if not local_path.exists():
            logger.error(f"文件不存在: {file_path}")
            return None

        if object_name is None:
            object_name = local_path.name

        try:
            self.client.fput_object(
                bucket_name=self.config.bucket,
                object_name=object_name,
                file_path=str(local_path),
                content_type="video/mp4",
            )
            logger.info(f"视频上传成功: {object_name}")

            # 返回访问 URL
            protocol = "https" if self.config.secure else "http"
            url = f"{protocol}://{self.config.endpoint}/{self.config.bucket}/{object_name}"
            return url

        except S3Error as e:
            logger.error(f"上传视频到 MinIO 失败: {e}")
            return None

    def upload_file(
        self,
        file_path: str,
        object_name: str,
        content_type: str = "application/octet-stream",
    ) -> Optional[str]:
        """
        上传任意文件到 MinIO

        Args:
            file_path: 本地文件路径
            object_name: MinIO 中的对象名称
            content_type: 文件 MIME 类型

        Returns:
            str: MinIO 中的对象访问URL，失败返回 None
        """
        if not self.ensure_bucket():
            return None

        local_path = Path(file_path)
        if not local_path.exists():
            logger.error(f"文件不存在: {file_path}")
            return None

        try:
            self.client.fput_object(
                bucket_name=self.config.bucket,
                object_name=object_name,
                file_path=str(local_path),
                content_type=content_type,
            )
            logger.info(f"文件上传成功: {object_name}")

            protocol = "https" if self.config.secure else "http"
            url = f"{protocol}://{self.config.endpoint}/{self.config.bucket}/{object_name}"
            return url

        except S3Error as e:
            logger.error(f"上传文件到 MinIO 失败: {e}")
            return None

    def upload_bytes(
        self,
        data: bytes,
        object_name: str,
        content_type: str = "application/octet-stream",
    ) -> Optional[str]:
        """
        上传字节数据到 MinIO

        Args:
            data: 字节数据
            object_name: MinIO 中的对象名称
            content_type: 文件 MIME 类型

        Returns:
            str: MinIO 中的对象访问URL，失败返回 None
        """
        if not self.ensure_bucket():
            return None

        try:
            self.client.put_object(
                bucket_name=self.config.bucket,
                object_name=object_name,
                data=io.BytesIO(data),
                length=len(data),
                content_type=content_type,
            )
            logger.info(f"数据上传成功: {object_name}")

            protocol = "https" if self.config.secure else "http"
            url = f"{protocol}://{self.config.endpoint}/{self.config.bucket}/{object_name}"
            return url

        except S3Error as e:
            logger.error(f"上传数据到 MinIO 失败: {e}")
            return None

    def delete_object(self, object_name: str) -> bool:
        """
        删除 MinIO 中的对象

        Args:
            object_name: 对象名称

        Returns:
            bool: 是否删除成功
        """
        if not self.ensure_bucket():
            return False

        try:
            self.client.remove_object(
                bucket_name=self.config.bucket,
                object_name=object_name,
            )
            logger.info(f"删除对象成功: {object_name}")
            return True
        except S3Error as e:
            logger.error(f"删除对象失败: {e}")
            return False

    def get_presigned_url(self, object_name: str, expires_seconds: int = 3600) -> Optional[str]:
        """
        获取对象的预签名访问URL（用于临时访问）

        Args:
            object_name: 对象名称
            expires_seconds: URL 过期时间（秒）

        Returns:
            str: 预签名访问URL
        """
        if not self.ensure_bucket():
            return None

        try:
            url = self.client.presigned_get_object(
                bucket_name=self.config.bucket,
                object_name=object_name,
                expires=expires_seconds,
            )
            return url
        except S3Error as e:
            logger.error(f"获取预签名URL失败: {e}")
            return None

    def test_connection(self) -> bool:
        """
        测试 MinIO 连接

        Returns:
            bool: 连接是否成功
        """
        try:
            if self.client.bucket_exists(self.config.bucket):
                logger.info("MinIO 连接测试成功")
                return True
            else:
                # 尝试创建 bucket
                self.client.make_bucket(self.config.bucket)
                logger.info("MinIO 连接成功，bucket 已自动创建")
                self._bucket_initialized = True
                return True
        except S3Error as e:
            logger.error(f"MinIO 连接测试失败: {e}")
            return False
        except Exception as e:
            logger.error(f"MinIO 连接异常: {e}")
            return False


_minio_storage: Optional[MinioStorage] = None


def get_minio_storage() -> MinioStorage:
    """
    获取 MinIO 存储实例（单例）

    Returns:
        MinioStorage: MinIO 存储客户端
    """
    global _minio_storage
    if _minio_storage is None:
        _minio_storage = MinioStorage()
    return _minio_storage