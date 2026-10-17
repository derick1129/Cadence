# AGENTS.md

Rules for AI coding agents working in this repo. These are mandatory.
Keep this file short. Detail lives in `docs/`.

## Project

Multi-tenant AI voice agent platform.

- `backend/`: FastAPI modular monolith (Python, Pydantic v2, PostgreSQL, Redis, S3/MinIO)
- `worker/`: LiveKit voice agent worker (`livekit-agents`), stateless
- `frontend/`: Next.js (App Router), Tailwind, SWR

Read before starting any task:

1. `docs/PLAN.md`: the current milestone and its acceptance criteria
2. `docs/ARCHITECTURE.md`: module map and import boundaries
3. `docs/DECISIONS.md`: choices already made. Do not re-litigate them.

## Commands (adjust here if tooling changes)

```
Backend lint:     ruff check . && ruff format --check .
Backend types:    mypy backend worker
Backend tests:    pytest -q
Boundaries:       lint-imports
Frontend lint:    pnpm lint
Frontend types:   pnpm typecheck
Frontend tests:   pnpm test
```

Run the relevant commands before every commit. See "Verification".

## Workflow

1. Read `docs/PLAN.md`. Work on the current milestone only.
2. If the task is unclear or touches more than one module, state a short plan and wait for approval.
3. Create a branch: `feat/<scope>-<short-name>` or `fix/<scope>-<short-name>`. Never commit to `main`.
4. Write a failing test first for any new behavior or bug fix. Then implement.
5. Make small changes. Stop at the milestone's acceptance criteria. Do not start the next milestone.
6. Report anything out of scope that you noticed instead of fixing it.

## Verification (no claims without evidence)

- Never say "done", "fixed", "passing" or "should work" unless you ran the checks in this session and read the output.
- Before finishing a task, run lint, types, tests and the boundary check. Paste the summary lines (pass/fail counts, exit status).
- For a bug fix, prove the test fails without the fix and passes with it.
- If a check fails and you cannot fix it within scope, say so plainly. Do not skip, delete or weaken tests to get green.

## Code quality

- Type-annotate all Python. Frontend is strict TypeScript, with no `any` unless justified in a comment.
- No dead code, no commented-out code, no debug prints, no unused imports or variables.
- No TODO without an issue reference.
- No bare `except:` and no swallowed errors. Handle errors at the layer that can act on them.
- No new dependencies without asking. State the reason, the alternatives and the license.
- Functions do one thing. Prefer under 40 lines. Files under 300 lines. Split before exceeding.
- Names say what things are. Comments explain why, not what.
- Config comes only from the settings module (env-driven). No hardcoded URLs, keys or magic numbers.
- Do not touch files unrelated to the task. No drive-by reformatting or renames.

## Modularity

Backend modules: `auth`, `organizations`, `agents`, `providers`, `telephony`, `campaigns`, `knowledge`, `tools`, `sessions`, `billing`, `internal`.

- Each module has `router.py` (HTTP only), `service.py` (business logic), `repository.py` (DB access), `schemas.py`.
- Routers call services. Services call repositories. Never skip a layer.
- A module may import another module only through that module's public `__init__.py` interface. Never import another module's repository or models directly.
- Third-party vendors (Deepgram, Cartesia, ElevenLabs, OpenAI, Twilio, Plivo, Telnyx, Stripe) live behind an interface in `providers/` or the relevant module. Business logic never imports a vendor SDK directly.
- The worker is stateless. It fetches config from the backend `runtime-config` endpoint and executes tools only through the backend tool gateway. Do not add direct DB access to the worker.
- Every tenant-scoped query must be filtered by `organization_id`. Add a test for cross-tenant access on every new endpoint.
- Frontend: feature folders with colocated components, hooks and API calls. No cross-feature imports except through shared `components/ui` and `lib/`.

## Git commits

- One logical change per commit. Each commit must leave lint, types and tests passing.
- Never mix refactoring, formatting and behavior changes in one commit.
- Format (Conventional Commits): `type(scope): imperative summary`
  - types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `perf`, `build`, `ci`
  - summary 72 characters or fewer, lowercase, no trailing period
  - body (when non-trivial) explains why, not what
- Bad: `update`, `fix stuff`, `WIP`, `changes`, `final`, `address review`.
- Stage deliberately with `git add -p`. Run `git diff --staged` and read it before every commit.
- Do not commit generated files, build output, `.env` files, secrets, or unrelated lockfile churn.
- Never force-push, rewrite shared history, or amend commits already pushed.
- Keep branches short-lived. One milestone, or part of one, per branch.

## Safety

Ask for explicit approval before:

- deleting files or directories
- creating or running database migrations, especially destructive ones
- changing auth, RBAC, billing or tenant-isolation code
- anything that sends real calls, SMS or emails, or charges money
- adding or upgrading dependencies
- running commands that affect anything outside this repo

Always:

- Use mocks, fakes or test numbers for telephony and providers. Never place real calls from tests or scripts.
- Never read, print, log or commit secrets. Use `.env.example` with placeholder values.
- Do not log PII (phone numbers, transcripts, audio paths) at info level or above.
- Outbound campaign code must enforce consent and calling-window checks. Do not bypass them, even in tests.

## Voice pipeline rules

- Keep the per-turn path (STT, LLM, TTS) free of blocking I/O. Anything slow goes to a background task or is cached.
- Any new per-turn network call needs a timeout and a stated latency cost in the PR description.
- Handle barge-in (caller interrupts) and silence timeouts explicitly. Add a test for each.
- Always finalize the session (transcript, metrics, recording path) even if the call fails or the worker crashes.

## When unsure

Stop and ask. A short question is cheaper than a wrong large change.
Do not guess about requirements, security or data-loss risks.
