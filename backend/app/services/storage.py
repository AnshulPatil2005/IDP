import os, io, json, boto3
from botocore.client import Config

_endpoint = os.getenv("MINIO_ENDPOINT")
_secure = os.getenv("MINIO_SECURE", "false").lower() == "true"
if _endpoint and not _endpoint.startswith("http"):
    _endpoint = f"{'https' if _secure else 'http'}://{_endpoint}"

_s3 = boto3.client(
    "s3",
    endpoint_url=_endpoint,
    aws_access_key_id=os.getenv("MINIO_ACCESS_KEY"),
    aws_secret_access_key=os.getenv("MINIO_SECRET_KEY"),
    config=Config(signature_version="s3v4"),
)
_BUCKET = os.getenv("MINIO_BUCKET", "docs")

def put_json(key: str, data: dict):
    _s3.put_object(Bucket=_BUCKET, Key=key, Body=json.dumps(data).encode("utf-8"), ContentType="application/json")

def get_json(key: str) -> dict | None:
    try:
        obj = _s3.get_object(Bucket=_BUCKET, Key=key)
        return json.loads(obj["Body"].read().decode("utf-8"))
    except _s3.exceptions.NoSuchKey:
        return None

def put_bytes(key: str, b: bytes, content_type: str = "application/octet-stream"):
    _s3.put_object(Bucket=_BUCKET, Key=key, Body=b, ContentType=content_type)

def get_bytes(key: str) -> bytes | None:
    """Fetch raw bytes from storage."""
    try:
        obj = _s3.get_object(Bucket=_BUCKET, Key=key)
        return obj["Body"].read()
    except _s3.exceptions.NoSuchKey:
        return None
