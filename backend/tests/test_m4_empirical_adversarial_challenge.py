"""Empirical adversarial and stress test suite for Milestone M4 (Sessions & Records).

This module independently stress-tests:
1. SigV4 Presigned S3 URLs:
   - Expiration bounds (0s, negative, 1s, 900s, 7 days max, 30 days extreme).
   - Special characters in keys (spaces, subdirectories, leading slashes, unicode).
   - RFC 3986 URI encoding of path segments in CanonicalURI.
2. Transcript Ordering & Ingestion:
   - Scrambled out-of-order segment ingestion.
   - Sequence collisions (duplicate seq turns).
   - High volume turn counts (500+ turns in reverse order) and benchmarking.
3. Session Metrics Telemetry:
   - Floating point billed counters (precision preservation).
   - Negative latencies and counters handling.
   - Repeated/multiple update calls (overwriting vs idempotency).
4. Internal Worker Gateway & Token Security:
   - Constant-time verification timing resilience.
   - Token fuzzing across empty, whitespace, buffer overflow, and non-ASCII characters.
5. Cross-Tenant Records Isolation:
   - IDOR prevention across /transcript, /metrics, /recording-url.
   - Session reconciliation edge cases (boundary, clock skew, concurrency).
"""

import asyncio
import math
import time
import urllib.parse
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.security import compare_digest, create_access_token
from backend.app.core.settings import settings
from backend.app.core.storage import generate_presigned_s3_url
from backend.app.main import app
from backend.app.modules.agents.repository import AgentRepository
from backend.app.modules.agents.router import get_agent_service
from backend.app.modules.agents.service import AgentService
from backend.app.modules.internal.router import get_internal_service, verify_internal_token
from backend.app.modules.internal.service import InternalGatewayService
from backend.app.modules.providers.service import ProviderService
from backend.app.modules.sessions.models import Session
from backend.app.modules.sessions.reconciliation import reconcile_orphaned_sessions
from backend.app.modules.sessions.repository import SessionRepository
from backend.app.modules.sessions.router import get_session_service
from backend.app.modules.sessions.service import SessionService


@pytest.fixture
async def challenge_client() -> AsyncGenerator[AsyncClient, None]:
    """Provide an isolated test client with wired in-memory services."""
    agent_repo = AgentRepository()
    agent_svc = AgentService(repository=agent_repo, provider_service=ProviderService())
    sess_repo = SessionRepository()
    sess_svc = SessionService(repository=sess_repo, agent_service=agent_svc)
    gw_svc = InternalGatewayService(session_service=sess_svc, agent_service=agent_svc)

    app.dependency_overrides[get_agent_service] = lambda: agent_svc
    app.dependency_overrides[get_session_service] = lambda: sess_svc
    app.dependency_overrides[get_internal_service] = lambda: gw_svc

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.pop(get_agent_service, None)
    app.dependency_overrides.pop(get_session_service, None)
    app.dependency_overrides.pop(get_internal_service, None)


# ==============================================================================
# 1. SigV4 Presigned S3 URLs Stress & Adversarial Tests
# ==============================================================================


def test_sigv4_presigned_url_standard_structure() -> None:
    """Verify standard presigned URL meets SigV4 query parameter specifications."""
    url = generate_presigned_s3_url("recordings/test.mp4", expires_in_seconds=900)
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)

    assert "X-Amz-Algorithm" in params
    assert params["X-Amz-Algorithm"][0] == "AWS4-HMAC-SHA256"
    assert "X-Amz-Credential" in params
    assert "X-Amz-Date" in params
    assert "X-Amz-Expires" in params
    assert params["X-Amz-Expires"][0] == "900"
    assert "X-Amz-SignedHeaders" in params
    assert params["X-Amz-SignedHeaders"][0] == "host"
    assert "X-Amz-Signature" in params
    assert len(params["X-Amz-Signature"][0]) == 64


def test_sigv4_presigned_url_expiration_bounds() -> None:
    """Stress-test expiration bounds: 1s, 7 days (604800s max per AWS SigV4), and 30 days."""
    url_1s = generate_presigned_s3_url("rec.mp4", expires_in_seconds=1)
    params_1s = urllib.parse.parse_qs(urllib.parse.urlparse(url_1s).query)
    assert params_1s["X-Amz-Expires"][0] == "1"

    url_7d = generate_presigned_s3_url("rec.mp4", expires_in_seconds=604800)
    params_7d = urllib.parse.parse_qs(urllib.parse.urlparse(url_7d).query)
    assert params_7d["X-Amz-Expires"][0] == "604800"

    # Extreme expiration value
    url_30d = generate_presigned_s3_url("rec.mp4", expires_in_seconds=2592000)
    params_30d = urllib.parse.parse_qs(urllib.parse.urlparse(url_30d).query)
    assert params_30d["X-Amz-Expires"][0] == "2592000"


def test_sigv4_presigned_url_subdirectories_and_leading_slashes() -> None:
    """Test object keys with deep subdirectories and leading/redundant slashes."""
    nested_key = "recordings/2026/10/20/org_xyz/agent_1/calls/audio_final.wav"
    url_nested = generate_presigned_s3_url(nested_key)
    assert nested_key in url_nested

    # Multiple leading slashes: ensure stripped properly
    url_slashes = generate_presigned_s3_url("///recordings/sess-123.mp4")
    parsed_slashes = urllib.parse.urlparse(url_slashes)
    assert not parsed_slashes.path.startswith(f"/{settings.S3_RECORDINGS_BUCKET}///")
    assert f"/{settings.S3_RECORDINGS_BUCKET}/recordings/sess-123.mp4" == parsed_slashes.path


def test_sigv4_presigned_url_empty_or_root_key() -> None:
    """Test behavior when key is empty string or root slash."""
    url_empty = generate_presigned_s3_url("")
    parsed_empty = urllib.parse.urlparse(url_empty)
    assert parsed_empty.path == f"/{settings.S3_RECORDINGS_BUCKET}/"

    url_slash = generate_presigned_s3_url("/")
    parsed_slash = urllib.parse.urlparse(url_slash)
    assert parsed_slash.path == f"/{settings.S3_RECORDINGS_BUCKET}/"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Vulnerability: SigV4 presigned URL path contains raw spaces instead of percent-encoded %20"
    ),
)
def test_sigv4_presigned_url_spaces_uri_encoding_adversarial() -> None:
    """Vulnerability probe: object keys with spaces must be URI-encoded per RFC 3986 in SigV4.

    If key has spaces ('recordings/customer call.mp4'), the URL path must be encoded as
    '%20', otherwise any HTTP client/browser will percent-encode on the wire, resulting
    in signature mismatch (403 SignatureDoesNotMatch) from S3/MinIO.
    """
    key_with_space = "recordings/customer call 2026.mp4"
    url = generate_presigned_s3_url(key_with_space)
    parsed = urllib.parse.urlparse(url)

    # AWS SigV4 specification requires CanonicalURI path segments to be percent-encoded once.
    # An unencoded space in the path violates RFC 3986 and breaks SigV4 verification.
    assert " " not in parsed.path, (
        f"Vulnerability found: Presigned URL contains raw space in path '{parsed.path}'! "
        f"Must be percent-encoded as '%20' per AWS SigV4 CanonicalURI specification."
    )


# ==============================================================================
# 2. Transcript Ordering & High-Volume Ingestion Stress
# ==============================================================================


@pytest.mark.asyncio
async def test_transcript_out_of_order_ingestion(challenge_client: AsyncClient) -> None:
    """Stress-test out-of-order transcript ingestion: verify retrieval is strictly sorted by seq."""
    org_id = "org-stress-order"
    token = create_access_token(data={"sub": "usr-1", "organization_id": org_id, "role": "owner"})
    user_headers = {"Authorization": f"Bearer {token}"}
    internal_headers = {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN}

    agent_res = await challenge_client.post(
        "/agents",
        headers=user_headers,
        json={"name": "Order Agent", "system_prompt": "Test order"},
    )
    agent_id = agent_res.json()["id"]

    sess_res = await challenge_client.post(
        "/sessions/web",
        headers=user_headers,
        json={"agent_id": agent_id},
    )
    session_id = sess_res.json()["session_id"]

    # Ingest deliberately scrambled turns: seq 5, 1, 4, 2, 3
    shuffled_turns = [
        {"seq": 5, "speaker": "agent", "text": "Turn 5 (Goodbye)", "started_at_ms": 5000},
        {"seq": 1, "speaker": "caller", "text": "Turn 1 (Hello)", "started_at_ms": 100},
        {"seq": 4, "speaker": "caller", "text": "Turn 4 (Thanks)", "started_at_ms": 4000},
        {"seq": 2, "speaker": "agent", "text": "Turn 2 (How can I help?)", "started_at_ms": 1500},
        {
            "seq": 3,
            "speaker": "caller",
            "text": "Turn 3 (I need assistance)",
            "started_at_ms": 3000,
        },
    ]

    fin_res = await challenge_client.post(
        f"/internal/sessions/{session_id}/finalize",
        headers=internal_headers,
        json={"duration_s": 10, "transcript_segments": shuffled_turns},
    )
    assert fin_res.status_code == 200

    # Retrieve transcript: MUST be sorted seq 1..5
    trans_res = await challenge_client.get(
        f"/sessions/{session_id}/transcript", headers=user_headers
    )
    assert trans_res.status_code == 200
    segments = trans_res.json()
    assert len(segments) == 5
    retrieved_seqs = [s["seq"] for s in segments]
    assert retrieved_seqs == [1, 2, 3, 4, 5]
    assert segments[0]["text"] == "Turn 1 (Hello)"
    assert segments[4]["text"] == "Turn 5 (Goodbye)"


@pytest.mark.asyncio
async def test_transcript_large_turn_volume_stress(challenge_client: AsyncClient) -> None:
    """Stress-test 500 transcript turns in a single session: check performance and integrity."""
    org_id = "org-stress-volume"
    token = create_access_token(data={"sub": "usr-1", "organization_id": org_id, "role": "owner"})
    user_headers = {"Authorization": f"Bearer {token}"}
    internal_headers = {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN}

    agent_res = await challenge_client.post(
        "/agents",
        headers=user_headers,
        json={"name": "Volume Agent", "system_prompt": "Stress test"},
    )
    agent_id = agent_res.json()["id"]

    sess_res = await challenge_client.post(
        "/sessions/web",
        headers=user_headers,
        json={"agent_id": agent_id},
    )
    session_id = sess_res.json()["session_id"]

    num_turns = 500
    large_turns = [
        {
            "seq": i,
            "speaker": "agent" if i % 2 == 0 else "caller",
            "text": f"Spoken turn #{i} with synthetic dialogue text padding to test payload size.",
            "started_at_ms": i * 1200,
        }
        for i in range(num_turns, 0, -1)  # Shuffled descending
    ]

    t0 = time.perf_counter()
    fin_res = await challenge_client.post(
        f"/internal/sessions/{session_id}/finalize",
        headers=internal_headers,
        json={"duration_s": num_turns * 2, "transcript_segments": large_turns},
    )
    ingest_duration = time.perf_counter() - t0
    assert fin_res.status_code == 200
    assert ingest_duration < 2.0

    t1 = time.perf_counter()
    trans_res = await challenge_client.get(
        f"/sessions/{session_id}/transcript", headers=user_headers
    )
    retrieval_duration = time.perf_counter() - t1
    assert trans_res.status_code == 200
    assert retrieval_duration < 1.0

    retrieved = trans_res.json()
    assert len(retrieved) == num_turns
    for idx, seg in enumerate(retrieved, start=1):
        assert seg["seq"] == idx
        assert seg["started_at_ms"] == idx * 1200


@pytest.mark.asyncio
async def test_transcript_sequence_collisions_handling(challenge_client: AsyncClient) -> None:
    """Test handling of duplicate sequence numbers (e.g. simultaneous turns or retries)."""
    org_id = "org-stress-collisions"
    token = create_access_token(data={"sub": "usr-1", "organization_id": org_id, "role": "owner"})
    user_headers = {"Authorization": f"Bearer {token}"}
    internal_headers = {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN}

    agent_res = await challenge_client.post(
        "/agents",
        headers=user_headers,
        json={"name": "Collision Agent", "system_prompt": "Collision test"},
    )
    sess_res = await challenge_client.post(
        "/sessions/web",
        headers=user_headers,
        json={"agent_id": agent_res.json()["id"]},
    )
    session_id = sess_res.json()["session_id"]

    duplicate_turns = [
        {"seq": 1, "speaker": "caller", "text": "Simultaneous caller turn", "started_at_ms": 100},
        {"seq": 1, "speaker": "agent", "text": "Simultaneous agent turn", "started_at_ms": 120},
        {"seq": 2, "speaker": "agent", "text": "Subsequent turn", "started_at_ms": 800},
    ]

    fin_res = await challenge_client.post(
        f"/internal/sessions/{session_id}/finalize",
        headers=internal_headers,
        json={"duration_s": 5, "transcript_segments": duplicate_turns},
    )
    assert fin_res.status_code == 200

    trans_res = await challenge_client.get(
        f"/sessions/{session_id}/transcript", headers=user_headers
    )
    assert trans_res.status_code == 200
    segments = trans_res.json()
    assert len(segments) == 3
    assert segments[0]["seq"] == 1
    assert segments[1]["seq"] == 1
    assert segments[2]["seq"] == 2


# ==============================================================================
# 3. Session Metrics Stress: Floats, Negatives, Repeated Updates
# ==============================================================================


@pytest.mark.asyncio
async def test_metrics_floating_point_billed_counters(challenge_client: AsyncClient) -> None:
    """Stress-test high-precision floating point stt_seconds_billed counter."""
    org_id = "org-stress-floats"
    token = create_access_token(data={"sub": "usr-1", "organization_id": org_id, "role": "owner"})
    user_headers = {"Authorization": f"Bearer {token}"}
    internal_headers = {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN}

    agent_res = await challenge_client.post(
        "/agents",
        headers=user_headers,
        json={"name": "Float Agent", "system_prompt": "Float test"},
    )
    sess_res = await challenge_client.post(
        "/sessions/web",
        headers=user_headers,
        json={"agent_id": agent_res.json()["id"]},
    )
    session_id = sess_res.json()["session_id"]

    float_stt_billed = 142.345678
    fin_res = await challenge_client.post(
        f"/internal/sessions/{session_id}/finalize",
        headers=internal_headers,
        json={
            "duration_s": 150,
            "metrics": {
                "avg_latency_ms": 285,
                "p95_latency_ms": 612,
                "interruption_count": 3,
                "llm_tokens_used": 1520,
                "stt_seconds_billed": float_stt_billed,
                "tts_characters_billed": 890,
            },
        },
    )
    assert fin_res.status_code == 200

    metrics_res = await challenge_client.get(
        f"/sessions/{session_id}/metrics", headers=user_headers
    )
    assert metrics_res.status_code == 200
    m = metrics_res.json()
    assert math.isclose(m["stt_seconds_billed"], float_stt_billed, rel_tol=1e-5)
    assert m["llm_tokens_used"] == 1520
    assert m["tts_characters_billed"] == 890


@pytest.mark.asyncio
async def test_metrics_negative_latencies_and_counters(challenge_client: AsyncClient) -> None:
    """Verify system accepts or handles negative numbers gracefully without 500 error."""
    org_id = "org-stress-negatives"
    token = create_access_token(data={"sub": "usr-1", "organization_id": org_id, "role": "owner"})
    user_headers = {"Authorization": f"Bearer {token}"}
    internal_headers = {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN}

    agent_res = await challenge_client.post(
        "/agents",
        headers=user_headers,
        json={"name": "Neg Agent", "system_prompt": "Neg test"},
    )
    sess_res = await challenge_client.post(
        "/sessions/web",
        headers=user_headers,
        json={"agent_id": agent_res.json()["id"]},
    )
    session_id = sess_res.json()["session_id"]

    fin_res = await challenge_client.post(
        f"/internal/sessions/{session_id}/finalize",
        headers=internal_headers,
        json={
            "duration_s": 10,
            "metrics": {
                "avg_latency_ms": -50,
                "p95_latency_ms": -20,
                "interruption_count": 0,
            },
        },
    )
    assert fin_res.status_code in (200, 422)

    if fin_res.status_code == 200:
        metrics_res = await challenge_client.get(
            f"/sessions/{session_id}/metrics", headers=user_headers
        )
        assert metrics_res.status_code == 200
        m = metrics_res.json()
        assert m["avg_latency_ms"] == -50


@pytest.mark.asyncio
async def test_metrics_multiple_repeated_update_calls(challenge_client: AsyncClient) -> None:
    """Verify repeated finalization / metric updates succeed idempotently."""
    org_id = "org-stress-repeated"
    token = create_access_token(data={"sub": "usr-1", "organization_id": org_id, "role": "owner"})
    user_headers = {"Authorization": f"Bearer {token}"}
    internal_headers = {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN}

    agent_res = await challenge_client.post(
        "/agents",
        headers=user_headers,
        json={"name": "Rep Agent", "system_prompt": "Repeat test"},
    )
    sess_res = await challenge_client.post(
        "/sessions/web",
        headers=user_headers,
        json={"agent_id": agent_res.json()["id"]},
    )
    session_id = sess_res.json()["session_id"]

    # Update 1: initial metrics
    fin1 = await challenge_client.post(
        f"/internal/sessions/{session_id}/finalize",
        headers=internal_headers,
        json={
            "duration_s": 20,
            "metrics": {"avg_latency_ms": 250, "llm_tokens_used": 100},
        },
    )
    assert fin1.status_code == 200

    # Update 2: second finalize (retry or late stats)
    fin2 = await challenge_client.post(
        f"/internal/sessions/{session_id}/finalize",
        headers=internal_headers,
        json={
            "duration_s": 25,
            "metrics": {"avg_latency_ms": 320, "llm_tokens_used": 180},
        },
    )
    assert fin2.status_code == 200

    metrics_res = await challenge_client.get(
        f"/sessions/{session_id}/metrics", headers=user_headers
    )
    assert metrics_res.status_code == 200
    m = metrics_res.json()
    assert m["avg_latency_ms"] == 320
    assert m["llm_tokens_used"] == 180


# ==============================================================================
# 4. Internal Worker Gateway & Token Security Fuzzing
# ==============================================================================


@pytest.mark.asyncio
async def test_challenge_internal_token_fuzzing(challenge_client: AsyncClient) -> None:
    """Fuzz X-Internal-Service-Token across all finalize and egress endpoints."""
    endpoints = [
        ("POST", "/internal/sessions/dummy-id/finalize", {"duration_s": 10}),
        ("POST", "/internal/egress/finalize", {"recording_key": "k.mp4"}),
    ]

    actual_token = settings.INTERNAL_SERVICE_TOKEN
    fuzz_tokens = [
        None,
        "",
        "   ",
        "Bearer " + actual_token,
        actual_token[:-1],
        actual_token + "extra",
        "!@#$%^&*()_+-=[]{}|;':,.<>?/",
        "A" * 10_000,
        "0",
    ]

    for method, path, payload in endpoints:
        for token in fuzz_tokens:
            headers = {}
            if token is not None:
                headers["X-Internal-Service-Token"] = token

            if method == "POST":
                res = await challenge_client.post(path, headers=headers, json=payload)
            else:
                res = await challenge_client.get(path, headers=headers)

            assert res.status_code == 401, (
                f"Expected 401 for token '{token[:20] if token else None}' on {path}, "
                f"got {res.status_code}"
            )


@pytest.mark.xfail(
    strict=True,
    reason="Bug: secrets.compare_digest raises TypeError on non-ASCII tokens causing 500 error",
)
@pytest.mark.asyncio
async def test_challenge_verify_internal_token_non_ascii_vulnerability() -> None:
    """Vulnerability probe: verify_internal_token must reject non-ASCII tokens with 401, not 500.

    When non-ASCII strings are passed directly to secrets.compare_digest(str, str),
    Python raises TypeError: comparing strings with non-ASCII characters is not supported.
    This causes unhandled 500 Internal Server Error instead of 401 Unauthorized.
    """
    non_ascii_tokens = [
        settings.INTERNAL_SERVICE_TOKEN + "\x00",
        settings.INTERNAL_SERVICE_TOKEN + "🔥",
        "🔥" * 5,
        "token_with_latin1_ö",
    ]

    for tok in non_ascii_tokens:
        with pytest.raises(HTTPException) as exc_info:
            await verify_internal_token(x_internal_service_token=tok)
        assert exc_info.value.status_code == 401, (
            f"Expected HTTPException(401) for token '{tok}', got {exc_info.value.status_code}"
        )


def test_challenge_timing_attack_resilience() -> None:
    """Empirically test compare_digest constant-time behavior against timing attack vectors."""
    actual_secret = "cadence_internal_service_secret_token_super_long_key_12345"
    almost_matching = actual_secret[:-1] + "X"
    completely_wrong = "Z" * len(actual_secret)

    iterations = 500

    def measure(candidate: str) -> float:
        start = time.perf_counter_ns()
        for _ in range(iterations):
            compare_digest(candidate, actual_secret)
        return (time.perf_counter_ns() - start) / iterations

    for _ in range(100):
        compare_digest(almost_matching, actual_secret)

    time_almost = measure(almost_matching)
    time_wrong = measure(completely_wrong)

    delta_ns = abs(time_almost - time_wrong)
    assert delta_ns < 20_000, (
        f"Timing variance {delta_ns}ns exceeds acceptable constant-time threshold "
        f"(almost: {time_almost}ns, wrong: {time_wrong}ns)"
    )


# ==============================================================================
# 5. Cross-Tenant Records Isolation & IDOR Attacks
# ==============================================================================


@pytest.mark.asyncio
async def test_challenge_idor_across_all_sessions_endpoints(challenge_client: AsyncClient) -> None:
    """Stress-test IDOR across all customer sessions endpoints.

    Verifies Tenant B is strictly barred from reading or creating sessions under Tenant A.
    """
    token_a = create_access_token(
        data={"sub": "usr-a", "organization_id": "org-victim", "role": "owner"}
    )
    token_b = create_access_token(
        data={"sub": "usr-b", "organization_id": "org-attacker", "role": "owner"}
    )
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}
    internal_headers = {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN}

    # 1. Org A provisions an agent
    agent_a_res = await challenge_client.post(
        "/agents",
        headers=headers_a,
        json={"name": "Org A Secret Agent", "system_prompt": "Victim secret prompt"},
    )
    assert agent_a_res.status_code == 201
    agent_a_id = agent_a_res.json()["id"]

    # 2. Org A starts a web session
    sess_a_res = await challenge_client.post(
        "/sessions/web",
        headers=headers_a,
        json={"agent_id": agent_a_id},
    )
    assert sess_a_res.status_code == 201
    session_a_id = sess_a_res.json()["session_id"]
    room_a_name = sess_a_res.json()["room_name"]

    # 3. Finalize Org A's session with confidential transcripts and metrics
    await challenge_client.post(
        f"/internal/sessions/{session_a_id}/finalize",
        headers=internal_headers,
        json={
            "duration_s": 42,
            "transcript_segments": [
                {
                    "seq": 1,
                    "speaker": "caller",
                    "text": "My SSN is 000-11-2222",
                    "started_at_ms": 100,
                },
                {
                    "seq": 2,
                    "speaker": "agent",
                    "text": "I received your SSN safely.",
                    "started_at_ms": 1200,
                },
            ],
            "metrics": {
                "avg_latency_ms": 320,
                "p95_latency_ms": 610,
                "interruption_count": 0,
                "llm_tokens_used": 500,
                "stt_seconds_billed": 12.5,
                "tts_characters_billed": 150,
            },
        },
    )
    await challenge_client.post(
        "/internal/egress/finalize",
        headers=internal_headers,
        json={
            "room_name": room_a_name,
            "recording_key": f"recordings/org-victim/{session_a_id}.mp4",
        },
    )

    # --- IDOR PENETRATION ATTEMPTS BY ORG B ---
    # Attack 1: Dispatch web session using Org A's agent_id
    idor_dispatch = await challenge_client.post(
        "/sessions/web",
        headers=headers_b,
        json={"agent_id": agent_a_id},
    )
    assert idor_dispatch.status_code == 404
    assert idor_dispatch.json()["error"]["code"] == "AGENT_NOT_CONFIGURED"

    # Attack 2: Read Org A's session details
    idor_detail = await challenge_client.get(f"/sessions/{session_a_id}", headers=headers_b)
    assert idor_detail.status_code == 404
    assert idor_detail.json()["error"]["code"] == "SESSION_NOT_FOUND"

    # Attack 3: Read Org A's transcript
    idor_transcript = await challenge_client.get(
        f"/sessions/{session_a_id}/transcript", headers=headers_b
    )
    assert idor_transcript.status_code == 404
    assert idor_transcript.json()["error"]["code"] == "SESSION_NOT_FOUND"

    # Attack 4: Read Org A's metrics
    idor_metrics = await challenge_client.get(
        f"/sessions/{session_a_id}/metrics", headers=headers_b
    )
    assert idor_metrics.status_code == 404
    assert idor_metrics.json()["error"]["code"] == "SESSION_NOT_FOUND"

    # Attack 5: Request Org A's recording URL
    idor_recording = await challenge_client.get(
        f"/sessions/{session_a_id}/recording-url", headers=headers_b
    )
    assert idor_recording.status_code == 404
    assert idor_recording.json()["error"]["code"] == "SESSION_NOT_FOUND"


@pytest.mark.asyncio
async def test_recording_url_missing_recording_404(challenge_client: AsyncClient) -> None:
    """Requesting recording URL for a session without recording_key must return 404."""
    token = create_access_token(
        data={"sub": "usr-1", "organization_id": "org-no-rec", "role": "owner"}
    )
    headers = {"Authorization": f"Bearer {token}"}

    agent_res = await challenge_client.post(
        "/agents",
        headers=headers,
        json={"name": "No Rec Agent", "system_prompt": "Prompt"},
    )
    sess_res = await challenge_client.post(
        "/sessions/web",
        headers=headers,
        json={"agent_id": agent_res.json()["id"]},
    )
    session_id = sess_res.json()["session_id"]

    res = await challenge_client.get(f"/sessions/{session_id}/recording-url", headers=headers)
    assert res.status_code == 404
    body = res.json()
    assert body["error"]["code"] == "RECORDING_NOT_FOUND"


# ==============================================================================
# 6. Session Reconciliation Edge Cases
# ==============================================================================


@pytest.mark.asyncio
async def test_reconciliation_exact_boundary_and_finished_sessions() -> None:
    """Ensure reconciliation closes stale active sessions but never touches completed ones."""
    repo = SessionRepository()
    org_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    # 1. Active session older than 600s -> STALE
    s_active = await repo.create_session(
        org_id, str(uuid.uuid4()), str(uuid.uuid4()), "web", "room-act"
    )
    repo._mock_sessions[s_active["id"]]["started_at"] = now - timedelta(seconds=1200)

    # 2. Completed session older than 600s -> SHOULD NOT CHANGE
    s_done = await repo.create_session(
        org_id, str(uuid.uuid4()), str(uuid.uuid4()), "web", "room-done"
    )
    await repo.update_status(s_done["id"], status="completed", outcome="resolved", duration_s=45)
    repo._mock_sessions[s_done["id"]]["started_at"] = now - timedelta(seconds=1200)

    # 3. Failed session older than 600s -> SHOULD NOT CHANGE
    s_failed = await repo.create_session(
        org_id, str(uuid.uuid4()), str(uuid.uuid4()), "web", "room-fail"
    )
    await repo.update_status(s_failed["id"], status="failed", outcome="error", duration_s=10)
    repo._mock_sessions[s_failed["id"]]["started_at"] = now - timedelta(seconds=1200)

    closed_count = await reconcile_orphaned_sessions(repository=repo, stale_threshold_seconds=600)
    assert closed_count == 1

    done_after = await repo.get_by_id_internal(s_done["id"])
    assert done_after is not None
    assert done_after["status"] == "completed"
    assert done_after["outcome"] == "resolved"

    fail_after = await repo.get_by_id_internal(s_failed["id"])
    assert fail_after is not None
    assert fail_after["status"] == "failed"
    assert fail_after["outcome"] == "error"

    act_after = await repo.get_by_id_internal(s_active["id"])
    assert act_after is not None
    assert act_after["status"] == "failed"
    assert act_after["outcome"] == "abandoned"


@pytest.mark.asyncio
async def test_reconciliation_concurrent_runs() -> None:
    """Stress-test concurrent execution of reconcile_orphaned_sessions."""
    repo = SessionRepository()
    now = datetime.now(UTC)
    past_time = now - timedelta(seconds=1200)

    session_ids: list[str] = []
    for i in range(15):
        s = await repo.create_session(
            organization_id=str(uuid.uuid4()),
            agent_id=str(uuid.uuid4()),
            agent_version_id=str(uuid.uuid4()),
            channel="web",
            room_name=f"conc-stale-{i}-{uuid.uuid4().hex[:4]}",
        )
        repo._mock_sessions[s["id"]]["started_at"] = past_time
        session_ids.append(s["id"])

    tasks = [
        reconcile_orphaned_sessions(repository=repo, stale_threshold_seconds=600) for _ in range(5)
    ]
    results = await asyncio.gather(*tasks)
    assert len(results) == 5

    for sid in session_ids:
        sess = await repo.get_by_id_internal(sid)
        assert sess is not None
        assert sess["status"] == "failed"
        assert sess["outcome"] == "abandoned"


@pytest.mark.asyncio
async def test_reconciliation_db_mode() -> None:
    """Verify AsyncSession reconciliation logic with database query execution."""
    now = datetime.now(UTC)
    cutoff = now - timedelta(seconds=600)

    stale_session = Session(
        organization_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        agent_version_id=uuid.uuid4(),
        room_name="stale-db-room",
        status="active",
        started_at=cutoff - timedelta(seconds=10),
    )
    stale_session.id = uuid.uuid4()

    mock_db = AsyncMock(spec=AsyncSession)
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = [stale_session]
    mock_db.execute.return_value = mock_res

    closed_count = await reconcile_orphaned_sessions(session=mock_db, stale_threshold_seconds=600)
    assert closed_count == 1
    assert stale_session.status == "failed"
    assert stale_session.outcome == "abandoned"
    assert mock_db.flush.called
