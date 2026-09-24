"""
SeaweedFS S3 Storage Service
Handles all file operations: upload, download, presigned URLs, bucket management.
"""
import os
import io
import logging
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from typing import Optional

logger = logging.getLogger("smartlab.storage")

S3_ENDPOINT  = os.environ["S3_ENDPOINT"]
S3_ACCESS    = os.environ["S3_ACCESS_KEY"]
S3_SECRET    = os.environ["S3_SECRET_KEY"]

BUCKET_CONTENT = os.environ.get("S3_BUCKET_CONTENT", "smartlab-content")
BUCKET_SCORM   = os.environ.get("S3_BUCKET_SCORM",   "smartlab-scorm")
BUCKET_VIDEO   = os.environ.get("S3_BUCKET_VIDEO",   "smartlab-video")
BUCKET_EPUB    = os.environ.get("S3_BUCKET_EPUB",    "smartlab-epub")

_s3_client = None

def get_s3():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            endpoint_url=S3_ENDPOINT,
            aws_access_key_id=S3_ACCESS,
            aws_secret_access_key=S3_SECRET,
            config=Config(
                signature_version="s3v4",
                retries={"max_attempts": 3, "mode": "adaptive"},
            ),
            region_name="us-east-1",  # SeaweedFS ignores region but boto3 requires it
        )
    return _s3_client


def ensure_buckets():
    """Create all required S3 buckets if they don't exist."""
    s3 = get_s3()
    for bucket in [BUCKET_CONTENT, BUCKET_SCORM, BUCKET_VIDEO, BUCKET_EPUB]:
        try:
            s3.head_bucket(Bucket=bucket)
            logger.info(f"Bucket exists: {bucket}")
        except ClientError as e:
            if e.response["Error"]["Code"] in ("404", "NoSuchBucket"):
                s3.create_bucket(Bucket=bucket)
                logger.info(f"Created bucket: {bucket}")
            else:
                logger.error(f"Error checking bucket {bucket}: {e}")
                raise


def upload_bytes(bucket: str, key: str, data: bytes,
                 content_type: str = "application/octet-stream") -> str:
    """Upload bytes to SeaweedFS. Returns the S3 key."""
    s3 = get_s3()
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
    )
    logger.info(f"Uploaded s3://{bucket}/{key} ({len(data)} bytes)")
    return key


def upload_file(bucket: str, key: str, file_path: str,
                content_type: str = "application/octet-stream") -> str:
    """Upload a local file to SeaweedFS."""
    s3 = get_s3()
    with open(file_path, "rb") as f:
        s3.put_object(Bucket=bucket, Key=key, Body=f, ContentType=content_type)
    logger.info(f"Uploaded file s3://{bucket}/{key}")
    return key


def download_bytes(bucket: str, key: str) -> bytes:
    """Download an object from SeaweedFS as bytes."""
    s3 = get_s3()
    resp = s3.get_object(Bucket=bucket, Key=key)
    return resp["Body"].read()


def delete_object(bucket: str, key: str):
    s3 = get_s3()
    s3.delete_object(Bucket=bucket, Key=key)


def presigned_url(bucket: str, key: str, expires: int = 3600) -> str:
    """
    Generate a presigned download URL.
    For public CDN delivery via Nginx, caller should use CDN URL instead.
    """
    s3 = get_s3()
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires,
    )


def object_exists(bucket: str, key: str) -> bool:
    s3 = get_s3()
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError:
        return False


def upload_scorm_package(course_id: str, zip_bytes: bytes) -> str:
    """Upload SCORM ZIP. Returns S3 key."""
    key = f"courses/{course_id}/course.zip"
    return upload_bytes(BUCKET_SCORM, key, zip_bytes, "application/zip")


def upload_narration(lesson_id: str, slide_idx: int, audio_bytes: bytes) -> str:
    """Upload TTS narration audio for a slide. Returns S3 key."""
    key = f"audio/{lesson_id}/slide-{slide_idx}.mp3"
    return upload_bytes(BUCKET_CONTENT, key, audio_bytes, "audio/mpeg")


def upload_epub(book_id: str, epub_bytes: bytes) -> str:
    """Upload EPUB3 file. Returns S3 key."""
    key = f"books/{book_id}/book.epub"
    return upload_bytes(BUCKET_EPUB, key, epub_bytes, "application/epub+zip")


def upload_video(session_id: str, video_bytes: bytes,
                 filename: str = "video.mp4") -> str:
    """Upload raw video before transcoding. Returns S3 key."""
    key = f"video/{session_id}/{filename}"
    return upload_bytes(BUCKET_VIDEO, key, video_bytes, "video/mp4")


def upload_vtt(lesson_id: str, vtt_content: str) -> str:
    """Upload subtitle VTT file. Returns S3 key."""
    key = f"subtitles/{lesson_id}/subtitles.vtt"
    return upload_bytes(BUCKET_CONTENT, key, vtt_content.encode(), "text/vtt")
