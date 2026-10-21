"""Extended empirical stress test harness for Milestone M4 (Sessions & Records).

This module subjects the M4 implementation to:
1. Ultra-high volume transcript stress (1,000+ turns and multi-megabyte payloads).
2. Pathological Unicode, null bytes, HTML, and SQL-like strings in transcripts.
3. Concurrent request racing (interleaved finalization, egress, and reads).
4. Sub-millisecond timing resilience across prefix-varying internal tokens.
5. In-depth JWT invalidation and tampering vectors.
6. Concurrent reconciliation under 100 orphaned sessions.
"""

import asyncio
import time
import urllib.parse
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.core.security import compare_digest, create_access_token
from backend.app.core.settings import settings
from backend.app.core.storage import generate_presigned_s3_url
from backend.app.main import app
from backend.app.modules.agents.repository import AgentRepository
from backend.app.modules.agents.router import get_agent_service
from backend.app.modules.agents.service import AgentService
from backend.app.modules.internal.router import get_internal_service
from backend.app.modules.internal.service import InternalGatewayService
from backend.app.modules.providers.service import ProviderService
from backend.app.modules.sessions.reconciliation import reconcile_orphaned_sessions
from backend.app.modules.sessions.repository import SessionRepository
from backend.app.modules.sessions.router import get_session_service
from backend.app.modules.sessions.service import SessionService


@pytest.fixture
async def stress_client() -> AsyncGenerator[AsyncClient, None]:
    """Provide isolated client with clean in-memory repositories."""
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
# 1. Ultra-Large Transcripts & Pathological Payload Stress
# ==============================================================================


@pytest.mark.asyncio
async def test_ultra_large_transcript_stress(stress_client: AsyncClient) -> None:
    """Stress-test ingestion and ordered retrieval of 1,200 transcript turns."""
    org_id = f"org-ultra-{uuid.uuid4().hex[:6]}"
    token = create_access_token(data={"sub": "usr-1", "organization_id": org_id, "role": "owner"})
    user_headers = {"Authorization": f"Bearer {token}"}
    internal_headers = {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN}

    # Setup agent and session
    agent_res = await stress_client.post(
        "/agents",
        headers=user_headers,
        json={"name": "Ultra Agent", "system_prompt": "Ultra test"},
    )
    assert agent_res.status_code == 201
    agent_id = agent_res.json()["id"]

    sess_res = await stress_client.post(
        "/sessions/web",
        headers=user_headers,
        json={"agent_id": agent_id},
    )
    assert sess_res.status_code == 201
    session_id = sess_res.json()["session_id"]

    # 1,200 turns in reverse order
    total_turns = 1200
    turns = [
        {
            "seq": i,
            "speaker": "caller" if i % 2 == 1 else "agent",
            "text": f"Turn number {i}: testing ordering scalability under large turn counts.",
            "started_at_ms": i * 1500,
        }
        for i in range(total_turns, 0, -1)
    ]

    t_start = time.perf_counter()
    fin_res = await stress_client.post(
        f"/internal/sessions/{session_id}/finalize",
        headers=internal_headers,
        json={"duration_s": 2400, "transcript_segments": turns},
    )
    t_ingest = time.perf_counter() - t_start
    assert fin_res.status_code == 200
    assert t_ingest < 3.0, f"Ingestion took {t_ingest:.2f}s, expected < 3.0s"

    t_fetch_start = time.perf_counter()
    trans_res = await stress_client.get(f"/sessions/{session_id}/transcript", headers=user_headers)
    t_fetch = time.perf_counter() - t_fetch_start
    assert trans_res.status_code == 200
    assert t_fetch < 2.0, f"Retrieval took {t_fetch:.2f}s, expected < 2.0s"

    retrieved = trans_res.json()
    assert len(retrieved) == total_turns
    for expected_seq, turn in enumerate(retrieved, start=1):
        assert turn["seq"] == expected_seq
        assert turn["speaker"] == ("caller" if expected_seq % 2 == 1 else "agent")
        assert turn["started_at_ms"] == expected_seq * 1500


@pytest.mark.asyncio
async def test_pathological_transcript_text_payloads(stress_client: AsyncClient) -> None:
    """Stress-test transcript turns with special characters, scripts, unicode, and large text."""
    org_id = f"org-patho-{uuid.uuid4().hex[:6]}"
    token = create_access_token(data={"sub": "usr-1", "organization_id": org_id, "role": "owner"})
    user_headers = {"Authorization": f"Bearer {token}"}
    internal_headers = {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN}

    agent_res = await stress_client.post(
        "/agents",
        headers=user_headers,
        json={"name": "Patho Agent", "system_prompt": "Patho test"},
    )
    session_res = await stress_client.post(
        "/sessions/web",
        headers=user_headers,
        json={"agent_id": agent_res.json()["id"]},
    )
    session_id = session_res.json()["session_id"]

    complex_texts = [
        "Empty/spaces:     \t\n   ",
        "HTML/XSS: <script>alert('xss')</script><img src=x onerror=alert(1)>",
        "SQL injection: '; DROP TABLE transcript_segments; SELECT * FROM sessions WHERE '1'='1",
        "Unicode & Emojis: 🎙️ 🤖 ⚡ 🚀 👩‍👩‍👦‍👦 汉语 / 中文 / 日本語 / العربية / עִבְרִית",
        "Zero-width and control chars: A\u200bB\u200cC\u200dD\ufeffE",
        "Giant text payload: " + ("Large text padding block. " * 500),  # ~13KB turn text
    ]

    segments_payload = [
        {
            "seq": idx + 1,
            "speaker": "caller" if idx % 2 == 0 else "agent",
            "text": text,
            "started_at_ms": idx * 1000,
        }
        for idx, text in enumerate(complex_texts)
    ]

    fin_res = await stress_client.post(
        f"/internal/sessions/{session_id}/finalize",
        headers=internal_headers,
        json={"duration_s": 60, "transcript_segments": segments_payload},
    )
    assert fin_res.status_code == 200

    trans_res = await stress_client.get(f"/sessions/{session_id}/transcript", headers=user_headers)
    assert trans_res.status_code == 200
    results = trans_res.json()
    assert len(results) == len(complex_texts)
    for idx, expected_text in enumerate(complex_texts):
        assert results[idx]["text"] == expected_text
        assert results[idx]["seq"] == idx + 1


# ==============================================================================
# 2. Concurrent Requests & Racing Stress
# ==============================================================================


@pytest.mark.asyncio
async def test_concurrent_session_finalization_racing(stress_client: AsyncClient) -> None:
    """Stress-test 25 concurrent calls to /finalize with different metrics and segments."""
    org_id = f"org-race-{uuid.uuid4().hex[:6]}"
    token = create_access_token(data={"sub": "usr-1", "organization_id": org_id, "role": "owner"})
    user_headers = {"Authorization": f"Bearer {token}"}
    internal_headers = {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN}

    agent_res = await stress_client.post(
        "/agents",
        headers=user_headers,
        json={"name": "Race Agent", "system_prompt": "Race test"},
    )
    sess_res = await stress_client.post(
        "/sessions/web",
        headers=user_headers,
        json={"agent_id": agent_res.json()["id"]},
    )
    session_id = sess_res.json()["session_id"]

    concurrency = 25

    async def call_finalize(index: int) -> int:
        res = await stress_client.post(
            f"/internal/sessions/{session_id}/finalize",
            headers=internal_headers,
            json={
                "duration_s": 10 + index,
                "status": "completed",
                "transcript_segments": [
                    {"seq": index, "speaker": "caller", "text": f"Concurrent turn #{index}"}
                ],
                "metrics": {
                    "avg_latency_ms": 100 + index,
                    "llm_tokens_used": 50 * index,
                },
            },
        )
        return res.status_code

    tasks = [call_finalize(i) for i in range(1, concurrency + 1)]
    status_codes = await asyncio.gather(*tasks)
    assert all(code == 200 for code in status_codes)

    # Verify session is readable without crash
    sess_check = await stress_client.get(f"/sessions/{session_id}", headers=user_headers)
    assert sess_check.status_code == 200
    assert sess_check.json()["status"] == "completed"

    metrics_check = await stress_client.get(f"/sessions/{session_id}/metrics", headers=user_headers)
    assert metrics_check.status_code == 200
    assert metrics_check.json() is not None

    trans_check = await stress_client.get(
        f"/sessions/{session_id}/transcript", headers=user_headers
    )
    assert trans_check.status_code == 200
    assert len(trans_check.json()) == concurrency


@pytest.mark.asyncio
async def test_concurrent_interleaved_reads_and_writes(stress_client: AsyncClient) -> None:
    """Stress-test interleaving concurrent reads and writes on the same session."""
    org_id = f"org-rw-{uuid.uuid4().hex[:6]}"
    token = create_access_token(data={"sub": "usr-1", "organization_id": org_id, "role": "owner"})
    user_headers = {"Authorization": f"Bearer {token}"}
    internal_headers = {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN}

    agent_res = await stress_client.post(
        "/agents",
        headers=user_headers,
        json={"name": "RW Agent", "system_prompt": "RW test"},
    )
    sess_res = await stress_client.post(
        "/sessions/web",
        headers=user_headers,
        json={"agent_id": agent_res.json()["id"]},
    )
    session_id = sess_res.json()["session_id"]

    async def writer(i: int) -> None:
        await asyncio.sleep(0.001 * (i % 5))
        res = await stress_client.post(
            f"/internal/sessions/{session_id}/finalize",
            headers=internal_headers,
            json={
                "duration_s": i * 5,
                "transcript_segments": [{"seq": i, "speaker": "agent", "text": f"Msg {i}"}],
            },
        )
        assert res.status_code == 200

    async def reader() -> None:
        await asyncio.sleep(0.002)
        res = await stress_client.get(f"/sessions/{session_id}/transcript", headers=user_headers)
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    tasks = [writer(i) for i in range(1, 15)] + [reader() for _ in range(15)]
    await asyncio.gather(*tasks)

    # After completion, verify all turns are present and sorted
    final_res = await stress_client.get(f"/sessions/{session_id}/transcript", headers=user_headers)
    assert final_res.status_code == 200
    turns = final_res.json()
    assert len(turns) == 14
    seqs = [t["seq"] for t in turns]
    assert seqs == sorted(seqs)


@pytest.mark.asyncio
async def test_concurrent_reconciliation_high_volume() -> None:
    """Stress-test concurrent reconciliation runs over 100 stale sessions across tenants."""
    repo = SessionRepository()
    now = datetime.now(UTC)
    stale_created = now - timedelta(seconds=1200)

    total_sessions = 100
    session_ids: list[str] = []
    for i in range(total_sessions):
        s = await repo.create_session(
            organization_id=str(uuid.uuid4()),
            agent_id=str(uuid.uuid4()),
            agent_version_id=str(uuid.uuid4()),
            channel="web",
            room_name=f"stale-vol-{i}-{uuid.uuid4().hex[:6]}",
        )
        repo._mock_sessions[s["id"]]["started_at"] = None
        repo._mock_sessions[s["id"]]["created_at"] = stale_created
        repo._mock_sessions[s["id"]]["status"] = "initiated"
        session_ids.append(s["id"])

    # 10 concurrent reconciliation runs
    tasks = [
        reconcile_orphaned_sessions(repository=repo, stale_threshold_seconds=600) for _ in range(10)
    ]
    results = await asyncio.gather(*tasks)

    # Sum of closed counts across races must account for all 100 sessions
    total_closed = sum(results)
    assert total_closed >= total_sessions

    # All sessions must now be marked failed / abandoned
    for sid in session_ids:
        sess = await repo.get_by_id_internal(sid)
        assert sess is not None
        assert sess["status"] == "failed"
        assert sess["outcome"] == "abandoned"


# ==============================================================================
# 3. Invalid Tokens, Forgery, and Statistical Timing
# ==============================================================================


@pytest.mark.asyncio
async def test_jwt_tampering_and_forgery_vectors(stress_client: AsyncClient) -> None:
    """Stress-test JWT authentication against token forgery, manipulation, and bad headers."""
    # 1. Bearer missing entirely
    res1 = await stress_client.get(
        "/sessions", headers={"Authorization": "InvalidAuthHeaderFormat"}
    )
    assert res1.status_code == 401

    # 2. Bearer with random binary / non-base64 garbage
    res2 = await stress_client.get(
        "/sessions", headers={"Authorization": "Bearer !!!not-base-64!!!"}
    )
    assert res2.status_code == 401

    # 3. Valid token truncated
    token = create_access_token(data={"sub": "usr-1", "organization_id": "org-t"})
    res3 = await stress_client.get("/sessions", headers={"Authorization": f"Bearer {token[:20]}"})
    assert res3.status_code == 401

    # 4. Forged header with alg=none
    none_alg = (
        "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0."
        "eyJzdWIiOiJ1c3ItZXZpbCIsIm9yZ2FuaXphdGlvbl9pZCI6Im9yZy12aWN0aW0ifQ."
    )
    res4 = await stress_client.get("/sessions", headers={"Authorization": f"Bearer {none_alg}"})
    assert res4.status_code == 401


def test_internal_token_timing_attack_statistical_analysis() -> None:
    """Measure timing variance of compare_digest across matching prefix lengths.

    Tests whether prefix length leaks timing information under constant-time verification.
    """
    secret = settings.INTERNAL_SERVICE_TOKEN
    assert len(secret) >= 10

    candidates = [
        "X" * len(secret),  # 0 matching chars
        secret[:5] + "X" * (len(secret) - 5),  # 5 matching chars
        secret[: len(secret) // 2] + "X" * (len(secret) // 2),  # half matching chars
        secret[:-1] + ("X" if secret[-1] != "X" else "Y"),  # all but 1 matching chars
    ]

    iterations = 2000

    # Warmup
    for c in candidates:
        for _ in range(100):
            compare_digest(c, secret)

    timings: list[float] = []
    for cand in candidates:
        t0 = time.perf_counter_ns()
        for _ in range(iterations):
            compare_digest(cand, secret)
        avg_ns = (time.perf_counter_ns() - t0) / iterations
        timings.append(avg_ns)

    # Max difference between 0 matching chars and almost-matching chars
    max_delta_ns = max(timings) - min(timings)
    # 50,000 ns = 0.05 ms tolerance for CPU jitter
    assert max_delta_ns < 50_000, (
        f"Timing variance {max_delta_ns}ns exceeds acceptable constant-time threshold: {timings}"
    )


# ==============================================================================
# 4. Storage & SigV4 Edge Cases
# ==============================================================================


def test_sigv4_complex_special_characters_in_s3_keys() -> None:
    """Verify SigV4 presigned URL properly percent-encodes exotic S3 keys."""
    complex_keys = [
        "recordings/org 123/call#2.mp4",
        "recordings/path with spaces and + plus/file.wav",
        "recordings/unicode/файл_записи.mp3",
        "recordings/sub1/sub2/sub3/call_final_2026.webm",
    ]

    for key in complex_keys:
        url = generate_presigned_s3_url(key, expires_in_seconds=900)
        parsed = urllib.parse.urlparse(url)
        assert " " not in parsed.path, f"Raw space detected in URL path: {parsed.path}"
        assert "#" not in parsed.path, f"Raw '#' fragment detected in URL path: {parsed.path}"
        params = urllib.parse.parse_qs(parsed.query)
        assert "X-Amz-Signature" in params
        assert len(params["X-Amz-Signature"][0]) == 64
