from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import boto3
from botocore.client import Config

_BUCKET = os.getenv("MINIO_BUCKET", "docs")
_BACKEND = os.getenv("STORAGE_BACKEND", "auto").lower()  # auto | s3 | local
_LOCAL_ROOT = Path(os.getenv("STORAGE_LOCAL_ROOT", "./app_storage")).resolve()
_S3_CLIENT: Any = None
_S3_INIT_FAILED = False
_BUCKET_READY = False


def _endpoint_url() -> str:
    url = os.getenv("MINIO_ENDPOINT", "minio:9000")
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "http://" + url
    return url


def _local_path(key: str) -> Path:
    clean = key.replace("\\", "/").lstrip("/")
    return _LOCAL_ROOT / clean


def _ensure_local_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _get_s3():
    global _S3_CLIENT, _S3_INIT_FAILED
    if _BACKEND == "local":
        return None
    if _S3_INIT_FAILED:
        return None
    if _S3_CLIENT is None:
        try:
            _S3_CLIENT = boto3.client(
                "s3",
                endpoint_url=_endpoint_url(),
                aws_access_key_id=os.getenv("MINIO_ACCESS_KEY"),
                aws_secret_access_key=os.getenv("MINIO_SECRET_KEY"),
                config=Config(signature_version="s3v4"),
            )
        except Exception:
            _S3_INIT_FAILED = True
            return None
    return _S3_CLIENT


def _ensure_bucket(client: Any) -> bool:
    global _BUCKET_READY
    if _BUCKET_READY:
        return True
    try:
        client.head_bucket(Bucket=_BUCKET)
    except Exception:
        try:
            client.create_bucket(Bucket=_BUCKET)
        except Exception:
            return False
    _BUCKET_READY = True
    return True


def put_json(key: str, data: dict) -> None:
    payload = json.dumps(data).encode("utf-8")
    client = _get_s3()
    if client and _ensure_bucket(client):
        try:
            client.put_object(Bucket=_BUCKET, Key=key, Body=payload, ContentType="application/json")
            return
        except Exception:
            if _BACKEND == "s3":
                raise
    path = _local_path(key)
    _ensure_local_parent(path)
    path.write_bytes(payload)


def get_json(key: str) -> dict | None:
    client = _get_s3()
    if client:
        try:
            obj = client.get_object(Bucket=_BUCKET, Key=key)
            return json.loads(obj["Body"].read().decode("utf-8"))
        except Exception:
            if _BACKEND == "s3":
                raise
    path = _local_path(key)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def put_bytes(key: str, b: bytes, content_type: str = "application/octet-stream") -> None:
    client = _get_s3()
    if client and _ensure_bucket(client):
        try:
            client.put_object(Bucket=_BUCKET, Key=key, Body=b, ContentType=content_type)
            return
        except Exception:
            if _BACKEND == "s3":
                raise
    path = _local_path(key)
    _ensure_local_parent(path)
    path.write_bytes(b)


def get_bytes(key: str) -> bytes | None:
    client = _get_s3()
    if client:
        try:
            obj = client.get_object(Bucket=_BUCKET, Key=key)
            return obj["Body"].read()
        except Exception:
            if _BACKEND == "s3":
                raise
    path = _local_path(key)
    if not path.exists():
        return None
    return path.read_bytes()
