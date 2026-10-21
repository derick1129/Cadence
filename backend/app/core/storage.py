"""S3/MinIO object storage presigned URL generation via AWS Signature Version 4."""

import hashlib
import hmac
from datetime import UTC, datetime
from urllib.parse import quote, urlparse

from backend.app.core.settings import settings


def _hmac_sha256(key: bytes, msg: str) -> bytes:
    """Compute HMAC-SHA256 digest."""
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _get_signature_key(key: str, date_stamp: str, region_name: str, service_name: str) -> bytes:
    """Derive AWS SigV4 signing key."""
    k_date = _hmac_sha256(f"AWS4{key}".encode(), date_stamp)
    k_region = _hmac_sha256(k_date, region_name)
    k_service = _hmac_sha256(k_region, service_name)
    return _hmac_sha256(k_service, "aws4_request")


def generate_presigned_s3_url(
    key: str,
    bucket: str | None = None,
    expires_in_seconds: int = 900,
    method: str = "GET",
) -> str:
    """Generate an AWS SigV4 presigned URL for S3/MinIO object retrieval or upload."""
    bucket_name = bucket or settings.S3_RECORDINGS_BUCKET
    endpoint = settings.S3_ENDPOINT.rstrip("/")
    access_key = settings.S3_ACCESS_KEY
    secret_key = settings.S3_SECRET_KEY
    region = getattr(settings, "S3_REGION", "us-east-1")
    service = "s3"

    parsed_endpoint = urlparse(endpoint)
    host = parsed_endpoint.netloc

    now = datetime.now(UTC)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")

    clean_key = quote(key.lstrip("/"), safe="/")
    canonical_uri = f"/{bucket_name}/{clean_key}"

    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
    credential_param = f"{access_key}/{credential_scope}"

    query_params = {
        "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
        "X-Amz-Credential": credential_param,
        "X-Amz-Date": amz_date,
        "X-Amz-Expires": str(expires_in_seconds),
        "X-Amz-SignedHeaders": "host",
    }

    sorted_params = sorted(query_params.items())
    canonical_query = "&".join(f"{quote(k, safe='')}={quote(v, safe='')}" for k, v in sorted_params)
    canonical_headers = f"host:{host}\n"
    signed_headers = "host"
    payload_hash = "UNSIGNED-PAYLOAD"

    canonical_request = (
        f"{method}\n{canonical_uri}\n{canonical_query}\n"
        f"{canonical_headers}\n{signed_headers}\n{payload_hash}"
    )

    string_to_sign = (
        f"AWS4-HMAC-SHA256\n{amz_date}\n{credential_scope}\n"
        f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
    )

    signing_key = _get_signature_key(secret_key, date_stamp, region, service)
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    return f"{endpoint}{canonical_uri}?{canonical_query}&X-Amz-Signature={signature}"
