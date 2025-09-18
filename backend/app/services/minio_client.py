# app/services/minio_client.py
import os
from minio import Minio#type: ignore

_MINIO_ENDPOINT   = os.getenv("MINIO_ENDPOINT", "minio:9000")
_MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
_MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
_MINIO_SECURE     = os.getenv("MINIO_SECURE", "false").lower() == "true"
_MINIO_BUCKET     = os.getenv("MINIO_BUCKET", "docs")

client = Minio(
    _MINIO_ENDPOINT,
    access_key=_MINIO_ACCESS_KEY,
    secret_key=_MINIO_SECRET_KEY,
    secure=_MINIO_SECURE,
)

def ensure_bucket():
    if not client.bucket_exists(_MINIO_BUCKET):
        client.make_bucket(_MINIO_BUCKET)

def bucket_name() -> str:
    return _MINIO_BUCKET
