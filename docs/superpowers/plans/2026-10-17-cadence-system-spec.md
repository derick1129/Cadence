# Cadence Master System Specification

> **Status**: Approved Base Specification
> **Source Documents**: `docs/intent.md`, `docs/ARCHITECTURE.md`, `docs/PLAN.md`, `docs/DECISIONS.md`
> **Target Product**: Cadence Multi-Tenant AI Voice Agent Platform

---

## 1. System Overview & Scope

Cadence is a multi-tenant voice automation platform where businesses configure autonomous AI agents that converse over the telephone (PSTN) and web browsers.

### Architecture Topology
1. **Frontend (`frontend/`)**: Next.js App Router (React 19, TypeScript, Tailwind CSS, SWR, `@livekit/components-react`).
2. **Backend Control Plane (`backend/`)**: Python FastAPI Modular Monolith (Pydantic v2, SQLAlchemy async, PostgreSQL, Redis, S3/MinIO).
3. **Voice Execution Worker (`worker/`)**: Stateless Python voice agent worker (`livekit-agents`), running the `classic` pipeline (STT -> LLM -> TTS).
4. **Real-Time Media Cluster**: LiveKit Media Server (WebRTC), LiveKit SIP (telephony gateway), LiveKit Egress (call audio capture).

---

## 2. Core Backend Modules & Boundaries

Each backend module in `backend/app/modules/` adheres to strict layer isolation:
- `router.py`: HTTP endpoints, request/response models only. Never calls repository directly.
- `service.py`: Business logic, permissions, quota checks, event emissions.
- `repository.py`: Database access, SQLAlchemy queries. Enforces `organization_id` on every query.
- `schemas.py`: Pydantic request and response schemas.
- `__init__.py`: Public interface. Modules may only import from other modules' `__init__.py`.

### Module Directory
| Module | Responsibility | Primary Tables Owned |
| :--- | :--- | :--- |
| `auth` | User signup, login, JWT issuance, refresh token rotation, CSRF | `users`, `refresh_tokens` |
| `organizations` | Tenant management, team memberships, role enforcement, invitations | `organizations`, `memberships` |
| `agents` | Agent configuration, immutable versioning, greeting, prompt, silence timeouts | `agents`, `agent_versions` |
| `providers` | Static model/voice catalogs, provider credential lookup, interfaces | Static Catalog |
| `tools` | Custom tool definitions (`http`, `transfer`), execution, audit logging | `tools`, `agent_tools`, `tool_calls` |
| `telephony` | E.164 phone numbers, SIP trunk configurations, agent-to-number mapping | `phone_numbers` |
| `sessions` | Web and phone session lifecycles, transcripts, recordings, turn metrics | `sessions`, `transcript_segments`, `session_metrics` |
| `billing` | Subscription plans, concurrency tracking, minute quotas, Stripe webhooks | `plans`, `usage_events` |
| `internal` | Gateway endpoints for workers (`X-Internal-Service-Token`) and LiveKit/Egress webhooks | Cross-cutting worker façade |

---

## 3. Database Schema Specification

All tables use `UUID` primary keys (`id`), timestamps `created_at` and `updated_at`. Every tenant-scoped table enforces a non-null, indexed `organization_id` foreign key.

```sql
-- Organizations & Tenancy
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    plan_id UUID NOT NULL REFERENCES plans(id),
    stripe_customer_id VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE memberships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    role VARCHAR(32) NOT NULL CHECK (role IN ('owner', 'admin', 'member')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, organization_id)
);

CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Agents & Versioning
CREATE TABLE agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    current_version_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE agent_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    version_no INTEGER NOT NULL,
    system_prompt TEXT NOT NULL,
    greeting TEXT,
    stt_config JSONB NOT NULL,
    llm_config JSONB NOT NULL,
    tts_config JSONB NOT NULL,
    silence_timeout_s INTEGER NOT NULL DEFAULT 15,
    max_duration_s INTEGER NOT NULL DEFAULT 600,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (agent_id, version_no)
);

ALTER TABLE agents ADD CONSTRAINT fk_current_version FOREIGN KEY (current_version_id) REFERENCES agent_versions(id);

-- Tools
CREATE TABLE tools (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(32) NOT NULL CHECK (type IN ('http', 'transfer')),
    config JSONB NOT NULL,
    json_schema JSONB NOT NULL,
    outcome_label VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE agent_tools (
    agent_version_id UUID NOT NULL REFERENCES agent_versions(id) ON DELETE CASCADE,
    tool_id UUID NOT NULL REFERENCES tools(id) ON DELETE CASCADE,
    PRIMARY KEY (agent_version_id, tool_id)
);

-- Telephony
CREATE TABLE phone_numbers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    e164 VARCHAR(32) UNIQUE NOT NULL,
    carrier VARCHAR(32) NOT NULL,
    agent_id UUID REFERENCES agents(id) ON DELETE SET NULL,
    trunk_ref VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Sessions & Observability
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES agents(id),
    agent_version_id UUID NOT NULL REFERENCES agent_versions(id),
    channel VARCHAR(16) NOT NULL CHECK (channel IN ('web', 'phone')),
    status VARCHAR(32) NOT NULL CHECK (status IN ('initiated', 'active', 'completed', 'failed')),
    outcome VARCHAR(32) CHECK (outcome IN ('completed', 'transferred', 'failed', 'abandoned')),
    outcome_label VARCHAR(64),
    room_name VARCHAR(255) UNIQUE NOT NULL,
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    duration_s INTEGER DEFAULT 0,
    recording_key VARCHAR(512),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE transcript_segments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    seq INTEGER NOT NULL,
    speaker VARCHAR(16) NOT NULL CHECK (speaker IN ('caller', 'agent')),
    text TEXT NOT NULL,
    started_at_ms INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE session_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID UNIQUE NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    avg_latency_ms INTEGER,
    p95_latency_ms INTEGER,
    interruption_count INTEGER DEFAULT 0,
    llm_tokens_used INTEGER DEFAULT 0,
    stt_seconds_billed NUMERIC(10, 2) DEFAULT 0,
    tts_characters_billed INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE tool_calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    tool_id UUID REFERENCES tools(id),
    tool_name VARCHAR(255) NOT NULL,
    arguments JSONB NOT NULL,
    result JSONB,
    status VARCHAR(32) NOT NULL CHECK (status IN ('success', 'failed', 'timeout')),
    latency_ms INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Plans & Billing
CREATE TABLE plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(64) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    max_agents INTEGER NOT NULL,
    max_concurrency INTEGER NOT NULL,
    monthly_minutes INTEGER NOT NULL,
    price_cents INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE usage_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    seconds INTEGER NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 4. Voice Runtime & Worker Protocol

### Session Inception & Token Generation
1. Web caller triggers `POST /api/v1/sessions/web { "agent_id": "..." }`.
2. Backend verifies concurrency against Redis key: `org:{org_id}:active_calls`.
3. Backend creates a `sessions` record, pinning `current_version_id`.
4. Backend creates a LiveKit Room (`cadence-session-{session_id}`) and returns a scoped LiveKit token to frontend.
5. LiveKit Room triggers agent dispatch.

### Worker Interaction via Internal API
1. Worker joins the room and requests configuration:
   `GET /internal/sessions/{session_id}/runtime-config`
   Headers: `X-Internal-Service-Token: <SECRET>`
   Response: System prompt, model settings (STT, LLM, TTS), greeting text, attached tool schemas.
2. Worker runs `VoicePipelineAgent` with Deepgram (STT) -> OpenAI (LLM) -> Cartesia (TTS).
3. Tool Execution: When LLM calls a function:
   `POST /internal/sessions/{session_id}/tools/invoke`
   Backend validates SSRF, executes webhook, records audit log, and returns result.
4. Session Finalization: On call disconnect:
   `POST /internal/sessions/{session_id}/finalize`
   Worker transmits transcripts, turn latencies, interruption counts, and call outcome.
5. LiveKit Egress streams recording to MinIO bucket `cadence-recordings` and fires signed webhook to backend to set `recording_key`.

---

## 5. Security & Isolation Invariants

1. **Multi-Tenancy**: Every database query in repositories must require `organization_id`. Cross-tenant automated tests run against every endpoint.
2. **SSRF Guard**: Custom HTTP webhooks block private IP spaces (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `127.0.0.0/8`, `169.254.0.0/16`) and restrict redirects.
3. **Internal Gateway**: `/internal/*` routes are excluded from public Nginx reverse proxy routes and require constant-time validation of `X-Internal-Service-Token`.
4. **Secrets Encryption**: Tool webhook credentials and provider API keys are encrypted at rest with AES-256-GCM.
