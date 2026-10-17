# Intent

> This document says **what we are building and why**. It is the source of truth for scope and priorities.
> `docs/PLAN.md` says how and in what order. `docs/ARCHITECTURE.md` says how it is structured.
> If code and this document disagree, stop and resolve it here first.

## 1. What we are building

We are building **Cadence**, a multi-tenant platform where businesses create AI voice agents that hold natural, real-time phone and browser conversations on their behalf.

A business signs up, configures an agent (prompt, voice, language model, tools, knowledge), connects a phone number, and the agent handles calls without a human. The platform runs the calls, records and transcribes them, and shows the business what happened.

## 2. Why it exists

Businesses lose time and money on repetitive phone work: answering the same support questions, booking and rescheduling appointments, qualifying leads, and chasing contacts through outbound calls. Hiring for this does not scale, and old IVR menus frustrate callers.

Modern speech and language models make natural conversation possible, but wiring telephony, speech, models, tools, knowledge and billing together is hard. We provide that as a product, so a non-engineer can have a working voice agent in minutes.

## 3. Who it is for

- **Primary:** small and mid-sized businesses that need call automation without building it themselves (clinics, agencies, support teams, sales teams).
- **Secondary:** developers who want to embed voice agents into their own products through an API.

## 4. Core capabilities

**Must exist in the first usable version:**

1. **Agent builder:** create and edit agents with a system prompt, greeting, voice, model choice and silence handling. Keep version history.
2. **Inbound calls:** a caller dials a number, reaches an agent, and has a real-time conversation.
3. **Browser calling:** talk to an agent from the dashboard for testing and from an embeddable widget.
4. **Tools:** agents can call HTTP webhooks and transfer the call to a human.
5. **Call records:** every call produces a recording, transcript, duration and latency metrics, visible in the dashboard.
6. **Multi-tenancy and access control:** organizations, members and roles, with strict data isolation between tenants.
7. **Billing and quotas:** subscription plans with limits on agents, concurrency and call minutes.

**Planned after that:**

8. **Knowledge base:** upload documents, scrape URLs and sync Drive. The agent searches them during calls.
9. **Outbound campaigns:** upload contacts, schedule by timezone, limit concurrency, retry with backoff, and personalize with variables.
10. **MCP tools:** agents can use tools from remote MCP servers.
11. **Bring your own keys:** customers supply their own provider credentials.
12. **External API:** trigger outbound calls and manage agents from other systems.
13. **Multiple voice pipelines:** classic (speech-to-text, LLM, text-to-speech) plus native speech-to-speech models.

## 5. Principles

- **Voice must feel natural.** Low latency, correct interruption handling and graceful silence behavior matter more than feature count.
- **Workers are thin; the backend owns configuration.** Changing an agent never requires redeploying workers.
- **Vendors are replaceable.** Speech, model and telephony providers sit behind interfaces. No vendor is hard-wired into business logic.
- **Tenant isolation is non-negotiable.** Every query is scoped to an organization.
- **Everything about a call is observable.** Recording, transcript, tool calls and latency are logged and auditable.
- **Consent and compliance are built in.** Outbound calling enforces consent and calling windows. This is not optional.
- **Modular monolith first.** Clear module boundaries, one deployable backend. Split into services only when forced by real constraints.
- **Small, verified, reviewable changes.** See `AGENTS.md`.

## 6. Non-goals (for now)

- Building our own telephony carrier or media server. We use LiveKit and existing carriers.
- Training our own speech or language models.
- A visual drag-and-drop workflow builder.
- Mobile apps.
- Multi-region deployment and enterprise SSO.
- Matching any competitor feature for feature.

## 7. Success looks like

- A new user creates an agent and completes a real test call in under 10 minutes.
- Median end-to-end response latency is low enough that conversation feels natural (target to be set during the first milestone, then tracked).
- No cross-tenant data access, proven by automated tests on every endpoint.
- Every completed call has a recording, a transcript and metrics, even when the call fails midway.
- Usage and billing match: minutes used equal minutes billed.

## 8. High-level shape

- **Frontend:** Next.js dashboard and calling widget.
- **Backend:** FastAPI modular monolith on PostgreSQL, with Redis for events and concurrency, and S3-compatible storage for audio and documents.
- **Voice layer:** LiveKit (rooms, SIP, egress) with Python `livekit-agents` workers.
- **Providers:** pluggable STT, LLM, TTS and telephony carriers.

Details belong in `docs/ARCHITECTURE.md`.

## 9. Constraints and assumptions

- Built with AI coding agents under the rules in `AGENTS.md`.
- Early development uses mocks and test numbers. No real outbound calls until compliance checks exist.
- Provider and model choices are reviewed against current versions at build time, not copied from older references.
- This intent is informed by studying an existing commercial product's public architecture. We build our own implementation, naming and branding.

## 10. Open questions

- Positioning and tagline for Cadence. Confirm domain, trademark and app-store availability for the name.
- Target launch market and the telephony regions it implies.
- Hosted-only, or self-hostable as well?
- Pricing model and whether minutes are bundled with provider cost or passed through.
- Which provider combination is the default for the first release?
- Data retention and recording-consent rules per region.
