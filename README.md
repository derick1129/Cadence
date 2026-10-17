# Cadence 🎙️⚡

> **Multi-Tenant Real-Time AI Voice Agent Platform**  
> Sub-500ms voice agents that listen, reply in real time, handle caller interruptions gracefully, and execute actions mid-call across browser WebRTC and PSTN telephony.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-1.0.0-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js 15](https://img.shields.io/badge/Next.js-15.1-black.svg?logo=next.js&logoColor=white)](https://nextjs.org/)
[![LiveKit](https://img.shields.io/badge/LiveKit-WebRTC-FF4F00.svg?logo=livekit&logoColor=white)](https://livekit.io/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind-3.4-38B2AC.svg?logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)

---

## Table of Contents

- [Overview](#overview)
- [System Architecture](#system-architecture)
- [Voice Pipelines & Flow Diagrams](#voice-pipelines--flow-diagrams)
  - [1. Inbound Call & Voice Pipeline Sequence](#1-inbound-call--voice-pipeline-sequence)
  - [2. Outbound Campaign Dispatch Pipeline](#2-outbound-campaign-dispatch-pipeline)
  - [3. Mid-Call Tool Execution Pipeline](#3-mid-call-tool-execution-pipeline)
  - [4. Backend Modular Monolith Layer Contract](#4-backend-modular-monolith-layer-contract)
- [Key Features](#key-features)
- [Repository Structure](#repository-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [1. Environment Setup](#1-environment-setup)
  - [2. Local Infrastructure](#2-local-infrastructure)
  - [3. Backend API](#3-backend-api)
  - [4. Frontend Web Application](#4-frontend-web-application)
  - [5. Voice Agent Worker](#5-voice-agent-worker)
- [Quality Verification & Testing](#quality-verification--testing)
- [Architecture & Design System](#architecture--design-system)

---

## Overview

Cadence is a developer-friendly, multi-tenant platform for building, testing, deploying, and monitoring autonomous voice agents. 

Unlike traditional interactive voice response (IVR) phone menus, Cadence agents operate on high-speed streaming pipelines connecting **streaming speech-to-text (STT)**, **large language models (LLMs)**, and **streaming text-to-speech (TTS)**. Callers can interrupt mid-sentence without acoustic echo, while the agent tracks conversation history, queries internal knowledge, calls backend tools, or transfers callers when needed.

---

## System Architecture

The monorepo is organized into three decoupled runtimes:
1. **Frontend (`frontend/`)**: Next.js App Router with Tailwind CSS, Aceternity UI, and shadcn/ui components.
2. **Backend (`backend/`)**: FastAPI modular monolith with strict domain layering enforced by `import-linter`.
3. **Voice Worker (`worker/`)**: Stateless Python worker powered by `livekit-agents` and WebRTC/SIP media pipelines.

```mermaid
flowchart TD
    subgraph Clients["Clients & Telephony"]
        WebCaller["Web Browser Client (WebRTC Audio)"]
        PhoneCaller["Phone PSTN Caller (SIP Inbound/Outbound)"]
    end

    subgraph MediaPlane["Media & Ingestion Plane"]
        LiveKitServer["LiveKit Server (WebRTC / SIP Dispatcher)"]
        LiveKitEgress["LiveKit Egress (Audio Composite Recorder)"]
    end

    subgraph VoiceWorkerPool["Stateless Voice Worker Pool"]
        Worker["LiveKit Voice Worker (livekit-agents)"]
        STT["STT Stream (Deepgram Nova-2)"]
        LLM["LLM Stream (OpenAI / Claude / Gemini)"]
        TTS["TTS Stream (Cartesia Sonic / ElevenLabs)"]
    end

    subgraph ControlPlane["Backend Control Plane (FastAPI Modular Monolith)"]
        API["FastAPI Monolith (Port 8000)"]
        InternalGW["Internal Gateway (/internal/*)"]
        AuthModule["Auth & Organizations"]
        AgentModule["Agent Versioning & Prompts"]
        ToolsModule["Tool Sandbox & Gateway"]
        SessionsModule["Session Lifecycle & Analytics"]
        TelephonyModule["Phone Number Registry & SIP Routing"]
        BillingModule["Usage Quotas & Metering"]
    end

    subgraph Storage["Data & Storage Plane"]
        Postgres[("PostgreSQL 16 (Multi-tenant DB)")]
        RedisDB[("Redis 7 (Concurrency, Pub/Sub, Cache)")]
        MinIOStorage[("MinIO / S3 (Audio Recordings & Transcripts)")]
    end

    WebCaller <-->|WebRTC Audio Stream| LiveKitServer
    PhoneCaller <-->|SIP Trunking| LiveKitServer
    LiveKitServer <-->|Room Audio Pipeline| Worker

    Worker -->|Streaming Audio| STT
    STT -->|Transcribed Text Tokens| LLM
    LLM -->|Synthesized Sentences| TTS
    TTS -->|Streaming Audio Frames| Worker

    Worker -->|Fetch Session Config| InternalGW
    Worker -->|Execute Mid-Call Tools| InternalGW
    Worker -->|Finalize Session & Metrics| InternalGW

    LiveKitEgress -->|Upload Recording| MinIOStorage
    API --> Postgres
    API --> RedisDB
    API --> MinIOStorage
```

---

## Voice Pipelines & Flow Diagrams

### 1. Inbound Call & Voice Pipeline Sequence

This sequence highlights the sub-turn streaming loop, barge-in detection (caller interruptions), and session audit logging.

```mermaid
sequenceDiagram
    autonumber
    actor Caller as Caller (Phone or Web)
    participant LK as LiveKit Media Server
    participant W as LiveKit Voice Worker
    participant BE as Backend Control Plane
    participant STT as Deepgram STT
    participant LLM as OpenAI / Anthropic
    participant TTS as Cartesia TTS
    participant S3 as MinIO / S3 Storage

    Caller->>LK: Connects audio (WebRTC / SIP)
    LK->>W: Assigns room & caller participant
    W->>BE: GET /internal/sessions/{id}/runtime-config
    BE-->>W: Returns pinned agent prompt, voice, & tool definitions
    
    rect rgb(240, 248, 255)
        note over Caller, TTS: Sub-turn conversational streaming loop (< 500ms)
        Caller->>W: Streams voice audio packets
        W->>STT: Continuous audio stream
        STT-->>W: Final transcript ("I'd like to book a tour")
        W->>LLM: Stream transcript with chat history
        LLM-->>W: Stream text chunks ("Sure! What date works best?")
        W->>TTS: Stream text chunks
        TTS-->>W: Stream PCM audio frames
        W-->>LK: Stream audio frames to room
        LK-->>Caller: Plays natural voice reply
    end

    rect rgb(255, 245, 245)
        note over Caller, LK: Interruption (Barge-In) Handling
        Caller->>W: Caller starts speaking while agent is talking
        W->>W: VAD detects voice interrupt (< 150ms)
        W->>LK: Truncate playback & clear audio buffer
        W->>TTS: Cancel ongoing synthesis
        W->>LLM: Cancel pending token generation
        W->>STT: Process new speech input immediately
    end

    Caller->>LK: Hangs up call
    LK->>W: Participant disconnected
    W->>BE: POST /internal/sessions/{id}/finalize (Metrics, Latencies, Transcript)
    BE->>S3: Archive recording audio & JSON transcript
    BE-->>W: 200 OK (Session closed & billed)
```

---

### 2. Outbound Campaign Dispatch Pipeline

Automated campaign dialing with strict consent verification, legal time-window controls, and concurrency limiting.

```mermaid
flowchart TD
    StartCampaign(["Trigger Outbound Campaign"]) --> ValidateConfig["Validate Campaign Config & Agent Version"]
    ValidateConfig --> FetchContacts["Query Contacts List (Postgres)"]
    
    FetchContacts --> CheckConsent{"Explicit Consent Valid?"}
    CheckConsent -- No --> SkipConsent["Log Skipped (Missing Consent)"]
    CheckConsent -- Yes --> CheckWindow{"Current Time in Legal Window?<br/>(8:00 AM - 8:00 PM Local)"}
    
    CheckWindow -- No --> Reschedule["Queue for Next Permissible Window"]
    CheckWindow -- Yes --> AcquireSlot{"Acquire Org Concurrency Slot<br/>(Redis Atomic Counter)"}
    
    AcquireSlot -- Limit Reached --> DelayRetry["Exponential Backoff & Re-queue"]
    AcquireSlot -- Slot Granted --> InitSIP["Initialize Outbound SIP Call (Twilio / Telnyx)"]
    
    InitSIP --> CallAnswered{"Recipient Answered?"}
    CallAnswered -- Busy / No Answer --> LogDisposition["Record Unanswered Disposition & Retry Counter"]
    CallAnswered -- Answering Machine --> AMDAction{"AMD Behavior Config"}
    AMDAction -- Hangup --> EndCall["Disconnect Call"]
    AMDAction -- Leave Message --> PlayVoicemail["Stream Recorded Message"]
    
    CallAnswered -- Human Answered --> BridgeLK["Bridge SIP Stream to LiveKit Room"]
    BridgeLK --> SpawnWorker["Dispatch Worker & Start Real-Time Voice Conversation"]
    SpawnWorker --> FinalizeCall["Release Redis Slot & Audit Session in Postgres"]
```

---

### 3. Mid-Call Tool Execution Pipeline

When the agent requires external data (checking calendar, querying an order, transfer), execution is safely routed through the backend tool gateway.

```mermaid
sequenceDiagram
    autonumber
    actor Caller as Caller
    participant W as Voice Worker
    participant LLM as LLM Provider
    participant BE as Backend Tool Gateway (/internal)
    participant Ext as External API (e.g. CRM / Calendar)

    Caller->>W: "Can you check if tomorrow at 10 AM is free?"
    W->>LLM: Forward user message
    LLM-->>W: Function Call: check_calendar(date="2026-10-18", time="10:00")
    
    note over W, BE: Worker executes tools only through backend gateway
    W->>BE: POST /internal/sessions/{id}/tools/invoke
    BE->>BE: Check tenant tool permissions & decrypt secrets
    BE->>Ext: Dispatch HTTP request to calendar service
    Ext-->>BE: Response: {"available": true, "slot_id": "slot-10am"}
    BE->>BE: Record immutable tool execution audit log
    BE-->>W: Returns tool result payload
    
    W->>LLM: Provide tool output to LLM context
    LLM-->>W: Stream text: "Yes, 10 AM tomorrow is open. Should I book it?"
    W-->>Caller: Speaks voice confirmation
```

---

### 4. Backend Modular Monolith Layer Contract

To maintain modularity and avoid tight coupling, all backend modules adhere to a unidirectional dependency hierarchy strictly enforced by `import-linter`.

```mermaid
flowchart TD
    subgraph Layer9["Layer 9: Internal Worker Gateway"]
        M_internal["backend.app.modules.internal"]
    end
    subgraph Layer8["Layer 8: Session Orchestration"]
        M_sessions["backend.app.modules.sessions"]
    end
    subgraph Layer7["Layer 7: Telephony Routing"]
        M_telephony["backend.app.modules.telephony"]
    end
    subgraph Layer6["Layer 6: Tool Gateway"]
        M_tools["backend.app.modules.tools"]
    end
    subgraph Layer5["Layer 5: Agents & Versions"]
        M_agents["backend.app.modules.agents"]
    end
    subgraph Layer4["Layer 4: AI Providers"]
        M_providers["backend.app.modules.providers"]
    end
    subgraph Layer3["Layer 3: Billing & Usage"]
        M_billing["backend.app.modules.billing"]
    end
    subgraph Layer2["Layer 2: Multi-Tenant Orgs"]
        M_organizations["backend.app.modules.organizations"]
    end
    subgraph Layer1["Layer 1: Identity & Authentication"]
        M_auth["backend.app.modules.auth"]
    end
    subgraph Layer0["Layer 0: Core Foundation"]
        M_core["backend.app.core (Settings, DB, Errors, Security)"]
    end

    M_internal --> M_sessions
    M_sessions --> M_telephony
    M_telephony --> M_tools
    M_tools --> M_agents
    M_agents --> M_providers
    M_providers --> M_billing
    M_billing --> M_organizations
    M_organizations --> M_auth
    M_auth --> M_core

    classDef allowed stroke:#0A7F5E,stroke-width:2px,fill:#0A7F5E10;
    class M_internal,M_sessions,M_telephony,M_tools,M_agents,M_providers,M_billing,M_organizations,M_auth,M_core allowed;
```

> [!IMPORTANT]
> A module may **only** import from another module through its public `__init__.py` interface. Cross-importing private models or repositories is automatically blocked by `lint-imports` in CI.

---

## Key Features

- **Ultra-Low Latency Pipeline**: Streaming STT + streaming LLM tokens + streaming TTS chunks deliver sub-500ms voice response latency.
- **Barge-In Interruption Handling**: Immediate speech playback truncation upon caller vocalization with acoustic echo suppression.
- **Two Doors, One Agent**: Pinned agent configuration can answer both high-fidelity browser WebRTC sessions and PSTN phone calls via SIP trunking.
- **Dynamic Mid-Call Tool Execution**: Safe tool invocation gateway with audit logging and secret isolation.
- **Immutable Agent Versioning**: Each prompt, provider, or voice tweak creates an immutable revision. Live conversations remain locked to their starting version.
- **Multi-Tenant Isolation**: Every database record, recording, and usage metric is strictly partitioned by `organization_id`.
- **Modern UI**: Polished marketing landing page and dashboard shell powered by Next.js 15, Tailwind CSS, Aceternity UI effects (`BackgroundBeams`, `CardSpotlight`, `BentoGrid`, `TextGenerateEffect`), and shadcn primitives.

---

## Repository Structure

```
├── .github/
│   └── workflows/ci.yml       # GitHub Actions verification workflow
├── backend/
│   ├── app/
│   │   ├── core/              # Settings, DB session, Security, Errors
│   │   ├── modules/           # Domain modules (auth, orgs, agents, tools, etc.)
│   │   └── main.py            # FastAPI application entrypoint
│   └── tests/                 # Health, module, and boundary test suite
├── worker/
│   ├── agent/                 # LiveKit worker entrypoint and runtime fetcher
│   ├── providers/             # Abstract interfaces (STT, LLM, TTS)
│   └── tests/                 # Worker interface and dispatch smoke tests
├── frontend/
│   ├── src/
│   │   ├── app/               # Next.js App Router ((marketing) and (app)/dashboard)
│   │   ├── components/        # Aceternity UI, shadcn components & marketing sections
│   │   └── lib/               # Design tokens and utilities
│   └── tests/                 # Vitest test suite for tokens, shell & landing page
├── deploy/
│   ├── docker-compose.yml     # Local stack: Postgres, Redis, MinIO, LiveKit
│   └── livekit.yaml           # Development LiveKit server configuration
├── docs/                      # Architectural specs, milestone plans, and ADRs
├── scripts/
│   └── verify_all.sh          # Global 7-step quality verification runner
└── pyproject.toml             # Python tools config (Ruff, Mypy, Pytest)
```

---

## Getting Started

### Prerequisites

- **Python**: `3.11+` with [`uv`](https://github.com/astral-sh/uv)
- **Node.js**: `20+` with [`pnpm`](https://pnpm.io/)
- **Docker**: Docker Desktop (v24.0+ with Docker Compose v2.20+)

---

### 1. Environment Setup

Create local environment configuration files from the templates:

```bash
# Root project environment
cp .env.example .env

# Docker compose infrastructure environment
cp deploy/env.example deploy/.env
```

---

### 2. Local Infrastructure

Start the local backing services (PostgreSQL, Redis, MinIO, and LiveKit):

```bash
docker compose -f deploy/docker-compose.yml up -d
```

Verify service health:

```bash
docker compose -f deploy/docker-compose.yml ps
```

| Service | Port | Default Credentials |
| :--- | :--- | :--- |
| **PostgreSQL 16** | `5432` | User: `cadence`, Password: `cadence_password`, DB: `cadence_dev` |
| **Redis 7** | `6379` | None |
| **MinIO API / Console** | `9000` / `9001` | User: `minioadmin`, Password: `minioadmin_secret` |
| **LiveKit Server** | `7880` (HTTP/WS) | Key: `devkey`, Secret: `secret` |

---

### 3. Backend API

Run the FastAPI control plane:

```bash
uv run --with uvicorn uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

- **Health check**: [http://127.0.0.1:8000/health/live](http://127.0.0.1:8000/health/live)
- **Readiness probe**: [http://127.0.0.1:8000/health/ready](http://127.0.0.1:8000/health/ready)
- **Interactive OpenAPI Documentation**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

### 4. Frontend Web Application

Start the Next.js development server:

```bash
cd frontend
pnpm dev
```

- **Marketing Landing Page**: [http://localhost:3000](http://localhost:3000)
- **Dashboard App Shell**: [http://localhost:3000/dashboard](http://localhost:3000/dashboard)

---

### 5. Voice Agent Worker

Start the LiveKit agent worker in development mode:

```bash
uv run python -m worker.agent.entrypoint dev
```

---

## Quality Verification & Testing

Cadence enforces strict quality gates across linting, type safety, test suites, and boundary isolation.

To run the entire suite in one command:

```bash
./scripts/verify_all.sh
```

Or run individual verification commands:

```bash
# 1. Backend Linting & Formatting
uv run ruff check . && uv run ruff format --check .

# 2. Strict Type Checking (Python)
uv run mypy backend worker

# 3. Backend Unit & Health Tests
uv run pytest -q

# 4. Architectural Boundary Enforcement
uv run lint-imports

# 5. Frontend Linting
cd frontend && pnpm lint

# 6. Frontend Strict TypeScript Check
cd frontend && pnpm typecheck

# 7. Frontend Vitest Suite
cd frontend && pnpm test
```

---

## Architecture & Design System

- **Technical Architecture**: See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for data schemas, security checklists, and deployment topologies.
- **Roadmap & Milestones**: See [docs/PLAN.md](docs/PLAN.md) for Milestone M0 through M8 acceptance criteria.
- **Architectural Decisions (ADRs)**: See [docs/DECISIONS.md](docs/DECISIONS.md) for rationale behind core technology choices.
- **Reverse Engineering Analysis**: See [intent/reverse-engineering-report.md](intent/reverse-engineering-report.md) for technical teardown and benchmarking.
