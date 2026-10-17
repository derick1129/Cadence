# Cadence MVP Plan

Read `docs/intent.md` (why) and `docs/ARCHITECTURE.md` (how) first. Rules are in `AGENTS.md`.

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
1. Monorepo skeleton matching `docs/ARCHITECTURE.md` section 2, with empty packages and READMEs.
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

## M2: Agents
**Goal:** configure an agent, with safe versioning.

## M3: Voice walking skeleton
**Goal:** a real spoken conversation with an agent from the browser.

## M4: Sessions and records
**Goal:** every call leaves a complete, trustworthy record.

## M5: Tools
**Goal:** agents can do things during a call, safely.

## M6: Inbound phone
**Goal:** a real phone call reaches an agent.

## M7: Plans and quotas
**Goal:** the product can limit and charge.

## M8: Hardening and launch
**Goal:** safe to put in front of real customers.

## MS: Marketing site
**Goal:** a premium, fast landing page that tells the truth about the product.

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
