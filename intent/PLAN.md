# Cadence MVP Plan

Read `intent.md` (why) and `docs/ARCHITECTURE.md` (how) first. Rules are in `AGENTS.md`.

## How to use this plan

- Work on **one milestone at a time**, in order. Do not start the next until the current one's acceptance criteria are verified with evidence (command output).
- Each milestone is split into tasks small enough for one agent session and one branch. Each task is one or more atomic commits.
- If a task reveals a design problem, stop and record it in `docs/DECISIONS.md` before changing the architecture.
- Mark progress by editing the **Status** line only.

## MVP definition

A user can sign up, create an agent, test it by voice from the browser, receive a real phone call on a number mapped to it, see the recording, transcript and metrics afterwards, let the agent call a webhook or transfer the call, and be limited by a plan. Data from different organizations is fully isolated.

## Design reference

The dashboard design demo is the visual and functional target for the frontend tasks below: https://claude.ai/artifact/57pXXKME5BAwzpgHL7Ezm2

Screen contents that the plan must deliver (its numbers and copy are sample data):
- **App shell:** sidebar (Agents, Calls, Numbers, Tools, Billing, Settings) and a plan-usage card showing minutes used against the plan limit.
- **Agent editor:** header with name, version label and last-saved time; "Save new version" and "Start test call" actions; fields for greeting, system prompt, model, voice, silence timeout; attached tools as chips; stat tiles (calls today, median response time, tool calls, live calls against the concurrency limit).
- **Test call panel:** connection state and timer, live waveform, live caller/agent transcript, live tool-call lines with latency, mute and end-call.
- **Recent calls table:** caller, channel, duration, outcome badge, start time.

Landing page design (approved direction for the whole brand): https://claude.ai/artifact/CTq8DJAaEeXeUXQCmytveL

**Brand direction** (from the landing page; applies to the marketing site and the app):
- **Light mode:** pure white background (`#FFFFFF`), near-black text (`#0A0A0A`), light gray borders (`#EAEAEA`), black primary buttons. No purple, no tinted backgrounds.
- **Dark mode:** neutral near-black (`#0A0A0A`), cards `#111111`, borders `#242424`, white primary buttons. Follows the system setting, with a manual toggle.
- **One small accent:** green for live, success and tool states (`#0A7F5E` light, `#3DD9A8` dark).
- **Type:** Bricolage Grotesque for headings, Hanken Grotesk for body.
- **Whitespace as a premium cue:** about 160px between sections and 88px between a section heading and its content on desktop, 40px card padding, 24px grid gaps. Spacing scales down on mobile. When in doubt, add space instead of content.
- **Motion:** one orchestrated hero moment (word-by-word headline, live call card), a cursor glow on cards, a one-time staggered reveal, a slow logo strip. Reduced-motion settings turn all of it off. Built with Framer Motion, shadcn/ui and Aceternity-style components.

**Known mismatch:** the dashboard demo above was drawn with a vermilion accent and different fonts (Sora, Instrument Sans). Restyle it to the brand direction before building the M2 frontend, so the app and the marketing site look like one product.

Screens not yet designed: login and signup, call detail, numbers, tools, billing. Design each one before building it (see M1, M4, M5, M6, M7). Colors, type, spacing and both themes become shared tokens in `frontend/src/lib/tokens` during M0 and are not re-invented per screen.

Out of scope for the MVP: knowledge base, outbound campaigns, MCP tools, bring-your-own keys, native speech-to-speech modes, automated number provisioning, overage billing.

## Milestone map

| # | Milestone | Outcome | Status |
|---|---|---|---|
| M0 | Foundation | Repo, local stack, CI, guardrails | Not started |
| M1 | Auth and tenancy | Signup, login, orgs, roles, isolation tests | Not started |
| M2 | Agents | Agent CRUD with immutable versions, dashboard UI | Not started |
| M3 | Voice walking skeleton | Talk to an agent from the browser | Not started |
| M4 | Sessions and records | Recording, transcript, metrics, call history | Not started |
| M5 | Tools | Webhook and transfer tools with audit log | Not started |
| M6 | Inbound phone | Real call to a number reaches an agent | Not started |
| M7 | Plans and quotas | Usage metering, limits, Stripe | Not started |
| M8 | Hardening and launch | Security, reliability, observability, deploy | Not started |
| MS | Marketing site | Landing page live, can run in parallel from M3 | Not started |

Order rationale: M3 comes early because voice latency and quality are the main product risk. Telephony and billing come after the core loop works. The marketing site (MS) is independent of the backend milestones and can be built in parallel once M0 is done, but it must not launch before the product it describes works.

---

## M0: Foundation

**Goal:** a repo where every later change is automatically checked.

Tasks:
1. Monorepo skeleton matching `ARCHITECTURE.md` section 2, with empty packages and READMEs.
2. `deploy/docker-compose.yml` for PostgreSQL, Redis, MinIO and LiveKit (dev config). One command starts everything.
3. Backend: FastAPI app, settings module (env-based), DB connection, migrations tool, `/health/live` and `/health/ready`.
4. Quality tooling: ruff, mypy, pytest, import-linter (with the module boundary contracts), pre-commit, commitlint.
5. CI: lint, types, tests and boundary check on every PR. `main` protected.
6. Frontend: Next.js app with lint, typecheck and test scripts passing on the empty shell. Add design tokens (colors, type, spacing, light and dark themes) from the brand direction above, set up shadcn/ui and Framer Motion, and add the sidebar layout component with route placeholders.
7. `.env.example`, `docs/DECISIONS.md` with the first entries (provider defaults, carrier, billing rounding, retention).

Acceptance criteria:
- `docker compose up` brings up all infrastructure and backend `/health/ready` returns OK.
- Every command in `AGENTS.md` runs and passes.
- A deliberately illegal cross-module import fails the boundary check (prove it, then revert).
- A commit with a bad message is rejected by the hook.
- CI is green on a trivial PR.

## M1: Auth and tenancy

**Goal:** secure multi-tenant foundation. Nothing else is built on an insecure base.

Tasks:
1. Models and migrations: `organizations`, `users`, `memberships`, `refresh_tokens`.
2. Signup (creates user and organization), login, refresh with rotation, logout.
3. Auth dependency that yields `{user_id, organization_id, role}`. Role-check helpers.
4. Tenant-scoped repository base that requires `organization_id`.
5. Test harness for cross-tenant access, reusable by later modules.
6. Members: invite, list, change role, remove (owner/admin only).
7. Design the login and signup screens in the same visual language, then build them. Add session handling, route guards and the app shell (sidebar and top area) from the design reference. The plan-usage card renders a placeholder until M7.
8. Rate limiting on auth endpoints.

Acceptance criteria:
- Signup, login, refresh rotation and logout work end to end, including from the UI.
- A reused or revoked refresh token is rejected.
- Role checks have tests for each role on each protected action.
- Tenant isolation test harness exists and passes against the members endpoints.

## M2: Agents

**Goal:** configure an agent, with safe versioning.

Tasks:
1. Provider catalog (static): available STT, LLM, TTS options and voices, validated server-side.
2. `agents` and `agent_versions` with migrations. Saving edits creates a new immutable version and moves `current_version_id`.
3. CRUD endpoints, version history, restore a previous version.
4. Validation: prompt length limits, supported config only, silence timeout bounds.
5. Frontend: agent list, then the agent editor from the design reference (greeting, system prompt, model, voice, silence timeout, version label and last-saved time, "Save new version"), plus version history and restore. Tool chips are read-only placeholders until M5. Stat tiles show real values from M4 onward.
6. Cross-tenant tests for every agents endpoint.

Acceptance criteria:
- Editing an agent never mutates an existing version (test proves it).
- Invalid provider or voice choices are rejected with a clear error.
- Cross-tenant tests pass.
- A user can create and edit an agent from the UI.

## M3: Voice walking skeleton

**Goal:** a real spoken conversation with an agent from the browser. This is the riskiest milestone. Take it slowly and measure.

Tasks:
1. Backend: `POST /api/v1/sessions/web`. Creates a session, pins the version, creates the LiveKit room with metadata, returns a scoped token. Internal `GET /internal/sessions/{id}/runtime-config`.
2. Worker: entrypoint, explicit dispatch, joins the room, fetches runtime config, speaks the greeting. No LLM yet.
3. Provider interfaces with fakes. One real adapter each for STT, LLM, TTS (defaults from `DECISIONS.md`).
4. Full `classic` pipeline: STT -> LLM -> TTS, streaming, with the agent's prompt.
5. Barge-in, silence timeout, maximum call duration.
6. Per-stage latency capture, sent to the backend at the end of the call.
7. Frontend: the test call panel from the design reference: connection state and timer, live waveform from the audio track, mute and end call.
8. Live transcript: the worker publishes caller and agent transcript text to the room as it happens (LiveKit's transcription or data channel), and the panel renders it. This is display only. The authoritative transcript is still stored at finalize (M4).
9. Test mode where fake providers allow automated end-to-end tests with no spend.

Acceptance criteria:
- A manual call from the browser has a natural back-and-forth conversation.
- Interrupting the agent stops it quickly and it responds to the new input (automated test with scripted audio plus manual check).
- Silence handling and maximum duration work (tests).
- A latency report from at least 20 real turns is saved in `docs/` and the target latency is set in `DECISIONS.md`.
- The live transcript in the test call panel matches what was said, within a turn of delay, and matches the stored transcript after the call (M4).
- The automated end-to-end test with fake providers passes in CI.

## M4: Sessions and records

**Goal:** every call leaves a complete, trustworthy record.

Tasks:
1. Finalize endpoint stores transcript segments and metrics. The worker calls it on success and on every error path.
2. LiveKit Egress to object storage, signed webhook that stores `recording_key`.
3. Heartbeat and reconciliation job that closes orphaned sessions as `failed`.
4. Recording playback endpoint with ownership check and short-lived access.
5. Session list (filters, pagination) and detail endpoints. Sessions get an `outcome` (`completed`, `transferred`, `failed`, `abandoned`) set at finalize, and an optional `outcome_label` (see M5).
6. Stats endpoint for the dashboard tiles: calls today, median response time, tool calls, and live calls against the concurrency limit. Tenant-scoped, with a time-zone-aware "today".
7. Design the call detail screen, then build it: transcript, tool calls, metrics, audio player. Build the recent-calls table and call history from the design reference (caller, channel, duration, outcome badge, start time).

Acceptance criteria:
- Killing the worker mid-call still results in a closed session and usable partial record (test).
- Another organization cannot access a recording or transcript (test).
- A completed call shows recording, transcript and latency in the UI.

## M5: Tools

**Goal:** agents can do things during a call, safely.

Tasks:
1. `tools` and `agent_tools` tables. CRUD with JSON schema validation.
2. `POST /internal/sessions/{id}/tools/invoke` with version check, argument validation, size and timeout limits.
3. HTTP webhook tool with encrypted auth headers and an SSRF guard.
4. Transfer tool behind the telephony interface, with a mock implementation.
5. `tool_calls` audit table. Rate and count limits per session.
6. Worker bridge: expose tools to the LLM, return results or errors verbally.
7. Optional `outcome_label` on a tool (for example a "Book appointment" tool labels the call "Booked"). It is applied to the session on successful invocation.
8. Design the tools screen, then build it: tool management and attaching tools to an agent. The agent editor's tool chips become live. Tool calls appear as live lines in the test call panel and on call detail.

Acceptance criteria:
- A call where the agent calls a test webhook shows the tool call in the record.
- Requests to private and loopback addresses are blocked (tests).
- A slow or failing tool leads to a graceful spoken recovery (test).
- A tool not attached to the session's version cannot be invoked (test).
- A successful tool with an `outcome_label` shows that label on the call in the recent-calls table.

## M6: Inbound phone

**Goal:** a real phone call reaches an agent.

Tasks:
1. Telephony interface plus one carrier implementation (per `DECISIONS.md`).
2. Number records and mapping to agents. Config endpoints, plus a numbers screen (design it first, then build).
3. SIP dispatch and the `sessions/intake` endpoint. Reject when over quota or unknown number.
4. Documented manual runbook for trunk and number setup.
5. Real transfer implementation, verified against a test number.
6. Phone channel tests with simulated SIP where possible.

Acceptance criteria:
- Calling the number reaches the correct agent and the call is fully recorded.
- Unknown numbers and over-limit calls are rejected cleanly.
- The runbook lets someone else reproduce the setup.

## M7: Plans and quotas

**Goal:** the product can limit and charge.

Tasks:
1. `plans`, subscription state on organizations, seeded plans.
2. Usage events from finalized sessions, using the rounding rule in `DECISIONS.md`.
3. Quota enforcement: agents, concurrency (Redis counters with TTL safety), monthly minutes.
4. Stripe Checkout and Billing Portal. Verified, idempotent webhook handling.
5. Design the billing screen, then build it: plan and usage page, upgrade flow, clear limit messages. The sidebar plan-usage card now shows real minutes used against the limit.

Acceptance criteria:
- Limits are enforced for every dimension (tests, including concurrent starts).
- Stripe test-mode upgrade changes the plan and limits. Replayed webhooks do nothing.
- Billed minutes equal recorded session minutes in a reconciliation test.

## M8: Hardening and launch

**Goal:** safe to put in front of real customers.

Tasks:
1. Security review against `ARCHITECTURE.md` section 13. Fix findings.
2. Rate limits on all public endpoints. Dependency scanning.
3. Error tracking, structured logs, dashboards for latency and failures, alerts.
4. Backups and a tested restore for PostgreSQL and recordings.
5. Load test: concurrent calls up to the largest plan limit. Record results.
6. Production deployment and runbooks (deploy, rollback, incident basics).
7. Privacy: recording consent notice option, retention job, data deletion on request.
8. Final pass: remove dead code, update docs, regenerate API client.

Acceptance criteria:
- Security checklist items are all checked or have recorded exceptions.
- A restore from backup is demonstrated.
- Load test meets the targets set in `DECISIONS.md`.
- A new engineer can deploy from the runbook.

---

## MS: Marketing site

**Goal:** a premium, fast landing page that tells the truth about the product. Design reference: https://claude.ai/artifact/CTq8DJAaEeXeUXQCmytveL

Tasks:
1. A `(marketing)` route group in the Next.js app, statically generated, with its own layout and no dependency on auth or the backend.
2. Build the landing page from the design: header with theme toggle, hero (word-by-word headline and a looping sample call card), provider strip, bento feature grid, how-it-works steps, closing call to action, footer. Use shadcn/ui `Button` and `Card`, Aceternity-style Spotlight, Bento Grid, Moving Border and Text Generate Effect components, and Framer Motion for animation. The sample call is an illustration, not a live call.
3. Copy review before launch: every claim must be true of the shipped product. Features not shipped keep the "Coming soon" label. The provider strip lists only integrations that exist. No invented statistics, customers or prices.
4. Real destinations: "Start free" goes to signup (M1). Add privacy, terms and contact pages. Add a pricing section built from the real plans once M7 is done.
5. SEO and sharing: page metadata, Open Graph image, sitemap, robots.
6. Accessibility and performance: visible keyboard focus, AA contrast in both themes, reduced motion respected, usable down to 360px wide, no layout shift from web fonts. Performance targets are set in `docs/DECISIONS.md`.

Acceptance criteria:
- The page renders correctly in light and dark mode, and with reduced motion enabled all animation stops.
- Every link and button goes somewhere real.
- The copy review checklist is complete, with each claim matched to a shipped feature.
- Accessibility and performance targets are met, with the measurements saved in `docs/`.

---

## Global definition of done (every task)

- Lint, types, tests and boundary check pass, with output shown.
- Tests exist for new behavior, and cross-tenant tests for new endpoints.
- No dead code, TODOs without issues, or unrelated changes.
- Docs updated if behavior or structure changed.
- Commits are atomic, with Conventional Commit messages.

## Key risks

| Risk | Mitigation |
|---|---|
| Voice latency feels slow | Measure from M3. Stream everywhere. Keep per-turn network calls minimal |
| Provider API versions change | Adapters behind interfaces. Check current docs before building each |
| Cross-tenant data leak | Tenant-scoped repository base. Mandatory isolation tests |
| Runaway cost in tests or loops | Fake providers in CI. Call duration and tool call limits. Spend alerts |
| Orphaned sessions and wrong billing | Heartbeat, reconciliation job, billing reconciliation test |
| Telephony setup is fragile | Runbook, one carrier first, simulated tests |
| Live transcript lags or disagrees with the stored one | Treat it as display only. Test that both match after a call |
| Frontend drifts from the design | Shared tokens from M0. Every new screen is designed before it is built |
| Landing page promises features that do not exist | "Coming soon" labels, copy review in MS, no launch before the core loop works |
| Heavy animation hurts speed or accessibility | Motion limited to the marketing site, reduced-motion support, performance targets in MS |
| Compliance for recording and calling | Consent options in M8. No outbound until a compliance design exists |

## After the MVP (in rough order)

1. Knowledge base and retrieval
2. Outbound calls and campaigns, with consent and calling windows
3. MCP tools
4. Bring-your-own provider keys
5. API keys and external API
6. Native speech-to-speech pipelines
7. Overage billing and automated number provisioning
