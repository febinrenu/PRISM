"""
Phase 3, Module F — Cloudflare R2 (S3-compatible) object storage.

If R2 credentials are configured, uploads go to the bucket; otherwise files stay
on local disk (data/uploads) exactly as in Phase 1/2. The rest of the app calls
`put_object` / `presigned_url` without caring which backend is active, so the
deployment story is a pure config change.
"""
from pathlib import Path
from typing import Optional

from config import (
    R2_ACCESS_KEY,
    R2_BUCKET,
    R2_ENDPOINT,
    R2_SECRET_KEY,
    UPLOAD_DIR,
)

R2_ENABLED = bool(R2_ENDPOINT and R2_ACCESS_KEY and R2_SECRET_KEY)

_client = None


def _get_client():
    global _client
    if _client is None:
        import boto3

        _client = boto3.client(
            "s3",
            endpoint_url=R2_ENDPOINT,
            aws_access_key_id=R2_ACCESS_KEY,
            aws_secret_access_key=R2_SECRET_KEY,
            region_name="auto",
        )
    return _client


def put_object(key: str, data: bytes, content_type: str = "application/pdf") -> str:
    """Store bytes and return the storage key (R2) or local path."""
    if R2_ENABLED:
        _get_client().put_object(Bucket=R2_BUCKET, Key=key, Body=data, ContentType=content_type)
        return key
    dest = UPLOAD_DIR / key
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return str(dest)


def get_object(key: str) -> Optional[bytes]:
    if R2_ENABLED:
        obj = _get_client().get_object(Bucket=R2_BUCKET, Key=key)
        return obj["Body"].read()
    p = Path(key) if Path(key).is_absolute() else UPLOAD_DIR / key
    return p.read_bytes() if p.exists() else None


def presigned_url(key: str, expires: int = 3600) -> Optional[str]:
    if R2_ENABLED:
        return _get_client().generate_presigned_url(
            "get_object", Params={"Bucket": R2_BUCKET, "Key": key}, ExpiresIn=expires
        )
    return None  # local: served via /api/pdf/{doc_id}


def status() -> dict:
    return {"backend": "r2" if R2_ENABLED else "local", "bucket": R2_BUCKET if R2_ENABLED else None}
