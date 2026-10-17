# Architecture & Technology Decisions (ADR)

> This document records architectural, technology, and policy choices already made.
> Do not re-litigate decisions documented here without explicit approval.

---

## 1. Provider Defaults (MVP)

* **Decision**: 
  - **Speech-to-Text (STT)**: Deepgram (`nova-2`). Default model for high accuracy and sub-300ms transcription latency.
  - **Large Language Model (LLM)**: OpenAI (`gpt-4o-mini` as standard low-latency default, `gpt-4o` for complex tool-calling).
  - **Text-to-Speech (TTS)**: Cartesia (`sonic-english`) for ultra-low latency streaming voice responses (<100ms first byte). ElevenLabs (`eleven_turbo_v2_5`) available as alternate voice profile.
* **Rationale**:
  - The cascaded voice pipeline requires sub-second turn latency to feel conversational. Deepgram + Cartesia provides the fastest time-to-first-byte (TTFB) in 2026.
  - All providers reside behind the internal provider interfaces (`STTProvider`, `LLMProvider`, `TTSProvider`), ensuring zero vendor lock-in.

---

## 2. Telephony Carrier Default (MVP)

* **Decision**: Twilio SIP Trunking.
* **Rationale**:
  - Twilio has mature programmable SIP trunking, broad regional number availability, clean BYOC documentation, and predictable test mocking capabilities.
  - Telephony logic sits behind `TelephonyProvider` to allow adding Plivo, Telnyx, or direct SIP peering post-MVP without altering business logic.

---

## 3. Call Duration & Billing Rounding Rule

* **Decision**: Call duration is measured in integer seconds. For billing against monthly subscription quotas, session durations are rounded up to the nearest **15-second increment** (with a 15-second minimum per completed or answered call).
* **Rationale**:
  - 15-second increments prevent micro-call abuse while remaining fair to small business customers compared to punitive 60-second carrier rounding.
  - Abandoned/unconnected calls (<1 second duration with no speech) consume 0 quota minutes.

---

## 4. Call Recording & Transcript Retention

* **Decision**: Default retention period is **90 days** per organization.
* **Rationale**:
  - 90 days provides ample window for QA, dispute resolution, and call analytics without accumulating unbounded object storage costs on MinIO/S3.
  - Organizations will have configurable retention settings (30, 90, 365 days, or indefinite) in M8.

---

## 5. Media & Voice Pipeline Architecture

* **Decision**: Single `classic` pipeline mode (STT -> LLM -> TTS) for MVP.
* **Rationale**:
  - Cascaded pipelines offer maximum control over prompt injection, tool calling, transcription inspection, and vendor interchangeability.
  - Multimodal native audio (e.g. Gemini Multimodal Live, OpenAI Realtime API) is designed as a drop-in pipeline mode post-MVP.

---

## 6. Worker Topology & Decoupling

* **Decision**: The LiveKit voice agent worker (`worker/`) is stateless, holds no database credentials, and communicates with `backend/` strictly over internal HTTP endpoints authenticated via `X-Internal-Service-Token`.
* **Rationale**:
  - Keeps voice workers lightweight, horizontally scalable, and resilient against database connection pool exhaustion during call spikes.
  - Config is pinned by `session_id` at session inception so agent prompt edits never mutate live in-flight conversations.

---

## 7. Frontend Design System & Branding Tokens

* **Decision**:
  - Brand Palette: Pure white (`#FFFFFF`) light mode, near-black (`#0A0A0A`) dark mode.
  - Single Accent: Mint green (`#0A7F5E` light, `#3DD9A8` dark) for live call and success states.
  - Typography: Bricolage Grotesque (headings), Hanken Grotesk (body text).
  - Component Libraries: Tailwind CSS, shadcn/ui, Framer Motion.
* **Rationale**:
  - Creates a coherent, premium, uncluttered aesthetic across both the marketing site and the application dashboard.
