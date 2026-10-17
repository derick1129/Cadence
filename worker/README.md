# Cadence Voice Agent Worker

The Cadence Voice Agent Worker (`worker/`) executes real-time voice conversations across WebRTC rooms powered by LiveKit Agents.

## Architectural Principles

1. **Strictly Stateless**: The worker maintains zero persistent state and possesses **no direct database access**. It scales horizontally across compute nodes and handles each call as an ephemeral job dispatched by LiveKit Server.
2. **Control Plane Decoupling**: All tenant isolation, business rules, tool executions, billing quotas, and session states are managed exclusively by the backend control plane (`backend/`).
3. **Session-Pinned Configuration**: When a call begins, the worker fetches runtime configuration pinned to the specific `agent_version_id` associated with that session. Prompt or tool updates made during an active call do not alter in-flight conversations.

## Interaction with Backend Control Plane

The worker communicates with `backend/` over private internal HTTP endpoints authenticated via the `X-Internal-Service-Token` header:

```
┌────────────────────────────────────────────────────────┐
│                   LiveKit Server                       │
└──────────────────────────┬─────────────────────────────┘
                           │ Dispatches Job
                           ▼
┌────────────────────────────────────────────────────────┐
│                   Voice Worker                         │
│                                                        │
│  1. Fetch runtime config:                              │
│     GET /internal/sessions/{id}/runtime-config         │
│                                                        │
│  2. Run cascaded voice pipeline:                       │
│     STT -> LLM -> TTS (Streaming)                      │
│                                                        │
│  3. Delegate tool execution:                           │
│     POST /internal/sessions/{id}/tools/invoke          │
│                                                        │
│  4. Persist call outcome & transcript:                 │
│     POST /internal/sessions/{id}/finalize              │
└──────────────────────────┬─────────────────────────────┘
                           │ Internal HTTP API
                           ▼
┌────────────────────────────────────────────────────────┐
│             Backend Monolith Control Plane             │
└────────────────────────────────────────────────────────┘
```

### Key Endpoints

- `GET /internal/sessions/{session_id}/runtime-config`: Fetches the pinned system prompt, voice parameters, STT/LLM/TTS provider keys, greeting phrase, and tool schemas.
- `POST /internal/sessions/{session_id}/tools/invoke`: Executes customer tools through the backend's SSRF-guarded gateway.
- `POST /internal/sessions/{session_id}/finalize`: Submits the final transcript segments, latency metrics, and termination status upon call completion or error.

## Voice Pipeline Architecture

For MVP, Cadence implements a `classic` cascaded pipeline:

- **Speech-to-Text (STT)**: Sub-300ms transcription (default: Deepgram `nova-2`).
- **Large Language Model (LLM)**: Streaming token generation with tool calling (default: OpenAI `gpt-4o-mini`).
- **Text-to-Speech (TTS)**: Low-latency audio stream synthesis (default: Cartesia `sonic-english`).

All vendors sit behind abstract interfaces (`STTProvider`, `LLMProvider`, `TTSProvider`), ensuring zero vendor lock-in and straightforward testing via mocked providers.

## Package Structure

```
worker/
├── README.md               # Worker architecture and operations
├── pyproject.toml          # Worker package manifest & dependencies
├── agent/
│   ├── __init__.py         # Package exports
│   └── entrypoint.py       # LiveKit WorkerOptions and job dispatching
├── providers/
│   ├── __init__.py         # Provider exports
│   └── interfaces.py       # Abstract Base Classes (STT, LLM, TTS)
└── tests/
    ├── __init__.py
    └── test_worker_smoke.py # Unit tests for schemas and provider contracts
```
