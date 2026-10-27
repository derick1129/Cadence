"""Tests for S3/MinIO presigned URL generator with AWS Signature Version 4."""

from urllib.parse import parse_qs, urlparse

from backend.app.core.storage import generate_presigned_s3_url


def test_generate_presigned_s3_url() -> None:
    """Verify presigned S3 URL contains required SigV4 query parameters and signature."""
    key = "recordings/org-123/sess-456.mp4"
    url = generate_presigned_s3_url(key=key, expires_in_seconds=600)

    parsed = urlparse(url)
    assert parsed.scheme in ("http", "https")
    assert key in parsed.path

    query_params = parse_qs(parsed.query)
    assert "X-Amz-Algorithm" in query_params
    assert query_params["X-Amz-Algorithm"][0] == "AWS4-HMAC-SHA256"
    assert "X-Amz-Credential" in query_params
    assert "X-Amz-Date" in query_params
    assert "X-Amz-Expires" in query_params
    assert query_params["X-Amz-Expires"][0] == "600"
    assert "X-Amz-Signature" in query_params
    assert len(query_params["X-Amz-Signature"][0]) == 64


def test_generate_presigned_s3_url_defaults() -> None:
    """Verify default expiration is 900 seconds and default bucket is used."""
    url = generate_presigned_s3_url(key="/calls/audio.mp4")
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)
    assert query_params["X-Amz-Expires"][0] == "900"
    assert "/cadence-recordings/calls/audio.mp4" in parsed.path
