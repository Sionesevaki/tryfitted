"""
Storage Client - MinIO integration for uploading/downloading files

This module handles all interactions with MinIO for storing and retrieving
photos, GLB files, and other assets.
"""

from minio import Minio
from minio.error import S3Error
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class StorageClient:
    """MinIO storage client"""
    
    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str, secure: bool = False):
        """
        Initialize MinIO client
        
        Args:
            endpoint: MinIO endpoint (host:port)
            access_key: MinIO access key
            secret_key: MinIO secret key
            bucket: Bucket name
            secure: Use HTTPS (default: False)
        """
        self.endpoint = endpoint
        self.bucket = bucket
        self.secure = secure
        self.client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure
        )
        logger.info(f"Initialized MinIO client: {endpoint}/{bucket}")
        self._ensure_bucket()

    def _ensure_bucket(self):
        """Ensure bucket exists and has public read policy"""
        try:
            if not self.client.bucket_exists(self.bucket):
                logger.info(f"Creating bucket: {self.bucket}")
                self.client.make_bucket(self.bucket)
            
            # Set public read policy
            policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": ["*"]},
                        "Action": ["s3:GetObject"],
                        "Resource": [f"arn:aws:s3:::{self.bucket}/*"]
                    }
                ]
            }
            try:
               import json
               self.client.set_bucket_policy(self.bucket, json.dumps(policy))
               logger.info(f"Set public read policy for bucket: {self.bucket}")
            except Exception as e:
               # Policy might already be set or permission error
               logger.warning(f"Could not set bucket policy: {e}")

        except Exception as e:
            logger.error(f"Failed to ensure bucket exists: {e}")

    # ... (rest of methods)

    def get_public_url(self, object_name: str) -> str:
        """
        Get public URL for object
        
        Args:
            object_name: Object name in MinIO
            
        Returns:
            Public URL
        """
        protocol = "https" if self.secure else "http"
        return f"{protocol}://{self.endpoint}/{self.bucket}/{object_name}"
        
    def download_file(self, object_name: str, file_path: str) -> str:
        """
        Download file from MinIO
        
        Args:
            object_name: Object name in MinIO
            file_path: Local path to save file
            
        Returns:
            Path to downloaded file
        """
        try:
            logger.info(f"Downloading {object_name} from MinIO to {file_path}")
            self.client.fget_object(self.bucket, object_name, file_path)
            return file_path
        except S3Error as e:
            logger.error(f"Failed to download {object_name}: {e}")
            raise
    
    def upload_file(self, file_path: str, object_name: str, content_type: Optional[str] = None) -> str:
        """
        Upload file to MinIO
        
        Args:
            file_path: Local file path
            object_name: Object name in MinIO
            content_type: Content type (optional)
            
        Returns:
            Object name in MinIO
        """
        try:
            logger.info(f"Uploading {file_path} to MinIO as {object_name}")
            
            # Auto-detect content type if not provided
            if content_type is None:
                ext = os.path.splitext(file_path)[1].lower()
                content_type_map = {
                    ".glb": "model/gltf-binary",
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".png": "image/png",
                    ".json": "application/json",
                }
                content_type = content_type_map.get(ext, "application/octet-stream")
            
            self.client.fput_object(
                self.bucket,
                object_name,
                file_path,
                content_type=content_type
            )
            
            logger.info(f"Successfully uploaded {object_name}")
            return object_name
            
        except S3Error as e:
            logger.error(f"Failed to upload {file_path}: {e}")
            raise
    
    def get_public_url(self, object_name: str) -> str:
        """
        Get public URL for object
        
        Args:
            object_name: Object name in MinIO
            
        Returns:
            Public URL
        """
        protocol = "https" if self.secure else "http"
        return f"{protocol}://{self.endpoint}/{self.bucket}/{object_name}"
