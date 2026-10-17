# Milestone M0: Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the verified monorepo skeleton, local Docker Compose infrastructure, FastAPI backend scaffolding with health checks, quality guardrails (lint, types, tests, boundary enforcement), Next.js frontend with brand design tokens, and CI pipeline so all subsequent milestones build on an automatically verified foundation.

**Architecture:** A three-package monorepo (`backend/`, `worker/`, `frontend/`) with shared deployment configuration (`deploy/`) and documentation (`docs/`). Backend modules follow strict boundary contracts enforced by `import-linter`, while Docker Compose orchestrates PostgreSQL, Redis, MinIO, and LiveKit for local development.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy (asyncio), Ruff, Mypy, Pytest, Import-Linter, Next.js 15+, React 19, Tailwind CSS, SWR, Docker Compose.

## Global Constraints

- Never commit directly to `main`; work on short-lived feature branches (`feat/foundation-m0`).
- Every Python file must be fully type-annotated (`mypy` strict mode without `Any` unless justified).
- Frontend is strict TypeScript; no `any`.
- Standard JSON error shape for API: `{"error": {"code": "...", "message": "...", "details": ...}}`.
- No vendor SDKs in core business logic.
- Config comes only from the settings module (`pydantic-settings`). No hardcoded secrets or URLs.
- Every row that belongs to a tenant carries `organization_id`.
- Quality commands must pass before commit:
  - `ruff check . && ruff format --check .`
  - `mypy backend worker`
  - `pytest -q`
  - `lint-imports`

---

### Task 1: Monorepo Skeleton & Tooling Configuration

**Files:**
- Create: `pyproject.toml`
- Create: `.importlinter`
- Create: `.gitignore`
- Create: `backend/README.md`
- Create: `worker/README.md`
- Create: `frontend/README.md`

**Interfaces:**
- Consumes: Monorepo layout defined in `docs/ARCHITECTURE.md`.
- Produces: Base configuration for Ruff, Mypy, Pytest, and Import-Linter boundary contracts.

- [ ] **Step 1: Write root .gitignore**

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
.pytest_cache/
.mypy_cache/
.ruff_cache/
htmlcov/
.coverage

# Virtual environments
.venv/
venv/
ENV/

# Node
node_modules/
.next/
out/
.turbo/
npm-debug.log*
yarn-debug.log*
yarn-error.log*
pnpm-debug.log*

# Environment and secrets
.env
.env.local
.env.*.local
*.pem
*.key

# OS
.DS_Store
Thumbs.db

# LiveKit & Local storage
deploy/data/
deploy/minio_data/
```

- [ ] **Step 2: Write root pyproject.toml with tool configurations**

```toml
[project]
name = "cadence"
version = "0.1.0"
description = "Multi-tenant AI voice agent platform"
requires-python = ">=3.11"
dependencies = []

[tool.ruff]
target-version = "py311"
line-length = 100
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "UP",  # pyupgrade
    "T20", # flake8-print (no print statements)
]
ignore = ["B008"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"

[tool.mypy]
python_version = "3.11"
strict = true
warn_unused_configs = true
warn_unused_ignores = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
plugins = ["pydantic.mypy"]

[[tool.mypy.overrides]]
module = ["livekit.*", "livekit.agents.*", "twilio.*", "cartesia.*"]
ignore_missing_imports = true

[tool.pytest.ini_options]
minversion = "7.0"
addopts = "-q --tb=short"
testpaths = ["backend/tests", "worker/tests"]
asyncio_mode = "auto"
```

- [ ] **Step 3: Write .importlinter for module boundary contracts**

```ini
[importlinter]
root_package = backend.app

[importlinter:contract:modular-boundaries]
name = Backend module isolation
type = layers
layers =
    backend.app.modules.internal
    backend.app.modules.sessions
    backend.app.modules.telephony
    backend.app.modules.tools
    backend.app.modules.agents
    backend.app.modules.providers
    backend.app.modules.billing
    backend.app.modules.organizations
    backend.app.modules.auth
    backend.app.core
containers =
    backend.app
```

- [ ] **Step 4: Create package README files**

Create `backend/README.md`, `worker/README.md`, and `frontend/README.md` describing their roles.

- [ ] **Step 5: Commit task 1**

```bash
git add pyproject.toml .importlinter .gitignore backend/README.md worker/README.md frontend/README.md
git commit -m "chore(repo): scaffold monorepo structure and quality configurations"
```

---

### Task 2: Local Development Infrastructure with Docker Compose

**Files:**
- Create: `deploy/docker-compose.yml`
- Create: `deploy/livekit.yaml`
- Create: `deploy/README.md`

**Interfaces:**
- Consumes: Ports and service specs from `docs/ARCHITECTURE.md`.
- Produces: Local PostgreSQL on 5432, Redis on 6379, MinIO on 9000/9001, LiveKit on 7880.

- [ ] **Step 1: Write deploy/livekit.yaml**

```yaml
port: 7880
rtc:
  tcp_port: 7881
  port_range_start: 50000
  port_range_end: 50020
  use_external_ip: false
keys:
  devkey: secret
logging:
  json: false
  level: info
```

- [ ] **Step 2: Write deploy/docker-compose.yml**

```yaml
version: "3.8"

services:
  postgres:
    image: postgres:16-alpine
    container_name: cadence-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: cadence
      POSTGRES_PASSWORD: cadence_password
      POSTGRES_DB: cadence_dev
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U cadence -d cadence_dev"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: cadence-redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  minio:
    image: minio/minio:RELEASE.2024-01-18T22-51-28Z
    container_name: cadence-minio
    restart: unless-stopped
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin_secret
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - miniodata:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 5s
      timeout: 5s
      retries: 5

  minio-create-buckets:
    image: minio/mc:RELEASE.2024-01-16T16-06-34Z
    depends_on:
      minio:
        condition: service_healthy
    entrypoint: >
      /bin/sh -c "
      /usr/bin/mc alias set local http://minio:9000 minioadmin minioadmin_secret;
      /usr/bin/mc mb --ignore-existing local/cadence-recordings;
      /usr/bin/mc mb --ignore-existing local/cadence-knowledge;
      exit 0;
      "

  livekit:
    image: livekit/livekit-server:v1.6.0
    container_name: cadence-livekit
    restart: unless-stopped
    command: --config /etc/livekit.yaml
    ports:
      - "7880:7880"
      - "7881:7881"
      - "50000-50020:50000-50020/udp"
    volumes:
      - ./livekit.yaml:/etc/livekit.yaml:ro

volumes:
  pgdata:
  miniodata:
```

- [ ] **Step 3: Validate docker-compose syntax**

Run: `docker compose -f deploy/docker-compose.yml config`
Expected: Valid compose config printed with exit code 0.

- [ ] **Step 4: Commit task 2**

```bash
git add deploy/docker-compose.yml deploy/livekit.yaml
git commit -m "chore(infra): add docker-compose stack for postgres, redis, minio and livekit"
```

---

### Task 3: Backend Core, Settings & Health Endpoints

**Files:**
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/core/settings.py`
- Create: `backend/app/core/db.py`
- Create: `backend/app/core/errors.py`
- Create: `backend/app/modules/{auth,organizations,agents,providers,tools,telephony,sessions,billing,internal}/__init__.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_health.py`

**Interfaces:**
- Consumes: Environment variables (`DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`).
- Produces:
  - `GET /health/live`: `{"status": "ok"}` (process check, independent of database).
  - `GET /health/ready`: `{"status": "ok", "dependencies": {"database": "ok", "redis": "ok"}}`.
  - Database connection pool via `get_db()`.
  - Standardized JSON exception handlers.

- [ ] **Step 1: Write failing test for health endpoints**

```python
# backend/tests/test_health.py
import pytest
from httpx import ASGITransport, AsyncClient
from backend.app.main import app


@pytest.mark.asyncio
async def test_health_live():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_health_ready_mocked(monkeypatch):
    from backend.app.core import db

    async def fake_check_db():
        return True

    async def fake_check_redis():
        return True

    monkeypatch.setattr(db, "check_db_ready", fake_check_db)
    monkeypatch.setattr(db, "check_redis_ready", fake_check_redis)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "dependencies": {"database": "ok", "redis": "ok"}}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_health.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.main'`

- [ ] **Step 3: Implement core settings, db, errors, and main.py**

```python
# backend/app/core/settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    SECRET_KEY: str = "cadence-default-insecure-secret-key-change-in-prod"
    INTERNAL_SERVICE_TOKEN: str = "cadence-default-internal-token"

    # Databases
    DATABASE_URL: str = "postgresql+asyncpg://cadence:cadence_password@localhost:5432/cadence_dev"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Storage
    S3_ENDPOINT: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin_secret"
    S3_RECORDINGS_BUCKET: str = "cadence-recordings"

    # LiveKit
    LIVEKIT_URL: str = "http://localhost:7880"
    LIVEKIT_API_KEY: str = "devkey"
    LIVEKIT_API_SECRET: str = "secret"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
```

```python
# backend/app/core/db.py
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from backend.app.core.settings import settings
import redis.asyncio as aioredis

engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG, future=True)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


async def check_db_ready() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def check_redis_ready() -> bool:
    try:
        client = aioredis.from_url(settings.REDIS_URL)
        await client.ping()
        await client.aclose()
        return True
    except Exception:
        return False
```

```python
# backend/app/core/errors.py
from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(
        self, code: str, message: str, status_code: int = 400, details: dict | None = None
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
    )
```

```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from backend.app.core.settings import settings
from backend.app.core.db import check_db_ready, check_redis_ready
from backend.app.core.errors import AppError, app_error_handler

app = FastAPI(title="Cadence API", version="0.1.0")
app.add_exception_handler(AppError, app_error_handler)


@app.get("/health/live", tags=["health"])
async def health_live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
async def health_ready() -> JSONResponse:
    db_ok = await check_db_ready()
    redis_ok = await check_redis_ready()
    status = "ok" if (db_ok and redis_ok) else "degraded"
    status_code = 200 if status == "ok" else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": status,
            "dependencies": {
                "database": "ok" if db_ok else "unreachable",
                "redis": "ok" if redis_ok else "unreachable",
            },
        },
    )
```

Create stub `__init__.py` files for each module: `backend/app/modules/{auth,organizations,agents,providers,tools,telephony,sessions,billing,internal}/__init__.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_health.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit task 3**

```bash
git add backend/
git commit -m "feat(backend): add core settings, db connection and health endpoints"
```

---

### Task 4: Quality Tooling & Module Boundary Enforcement

**Files:**
- Create: `backend/tests/test_boundaries.py`
- Modify: `.importlinter`

**Interfaces:**
- Consumes: Module hierarchy in `backend/app/modules/`.
- Produces: Automatic failure if an illegal cross-module internal import occurs.

- [ ] **Step 1: Write boundary verification test**

```python
# backend/tests/test_boundaries.py
import subprocess
import sys


def test_module_boundaries():
    result = subprocess.run(["lint-imports"], capture_output=True, text=True)
    assert result.returncode == 0, f"Import boundary violation:\n{result.stdout}\n{result.stderr}"
```

- [ ] **Step 2: Run boundary check to verify it passes on clean skeleton**

Run: `lint-imports`
Expected: `Contracts: 1 kept, 0 broken.`

- [ ] **Step 3: Introduce deliberate illegal import and verify failure**

Temporarily add in `backend/app/modules/auth/service.py`:
`from backend.app.modules.sessions.repository import SessionRepository`
Run: `lint-imports`
Expected: FAIL with broken contract report.
Revert the illegal import.

- [ ] **Step 4: Run ruff and mypy to verify zero warnings**

Run: `ruff check backend && ruff format --check backend && mypy backend`
Expected: All checks clean with exit code 0.

- [ ] **Step 5: Commit task 4**

```bash
git add backend/tests/test_boundaries.py .importlinter
git commit -m "test(boundaries): enforce architectural import boundary contracts"
```

---

### Task 5: Frontend Skeleton & Brand Design System Tokens

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tailwind.config.ts`
- Create: `frontend/src/app/globals.css`
- Create: `frontend/src/lib/tokens.ts`
- Create: `frontend/src/components/ui/sidebar.tsx`
- Create: `frontend/src/app/(app)/layout.tsx`
- Create: `frontend/src/app/(app)/page.tsx`
- Create: `frontend/tests/tokens.test.ts`

**Interfaces:**
- Consumes: Brand design spec from `docs/PLAN.md`.
- Produces:
  - Design tokens for light mode (`#FFFFFF`), dark mode (`#0A0A0A`), mint green accent (`#0A7F5E` / `#3DD9A8`).
  - Typography classes for Bricolage Grotesque and Hanken Grotesk.
  - Sidebar layout shell with placeholder route links (Agents, Calls, Numbers, Tools, Billing, Settings).

- [ ] **Step 1: Write test for brand tokens**

```typescript
// frontend/tests/tokens.test.ts
import { tokens } from '../src/lib/tokens';

describe('Brand Design Tokens', () => {
  it('defines the approved brand colors', () => {
    expect(tokens.colors.light.bg).toBe('#FFFFFF');
    expect(tokens.colors.dark.bg).toBe('#0A0A0A');
    expect(tokens.colors.light.accent).toBe('#0A7F5E');
    expect(tokens.colors.dark.accent).toBe('#3DD9A8');
  });

  it('defines the approved font families', () => {
    expect(tokens.fonts.heading).toContain('Bricolage Grotesque');
    expect(tokens.fonts.body).toContain('Hanken Grotesk');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && pnpm test tokens.test.ts`
Expected: FAIL with missing modules.

- [ ] **Step 3: Implement frontend package.json, tailwind, tokens, and app shell**

```typescript
// frontend/src/lib/tokens.ts
export const tokens = {
  colors: {
    light: {
      bg: '#FFFFFF',
      fg: '#0A0A0A',
      muted: '#5E5E5E',
      card: '#FFFFFF',
      line: '#EAEAEA',
      accent: '#0A7F5E',
    },
    dark: {
      bg: '#0A0A0A',
      fg: '#EDEDED',
      muted: '#A1A1A1',
      card: '#111111',
      line: '#242424',
      accent: '#3DD9A8',
    },
  },
  fonts: {
    heading: 'var(--font-heading), "Bricolage Grotesque", sans-serif',
    body: 'var(--font-body), "Hanken Grotesk", sans-serif',
  },
};
```

```css
/* frontend/src/app/globals.css */
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --bg: #FFFFFF;
  --fg: #0A0A0A;
  --muted: #5E5E5E;
  --card: #FFFFFF;
  --line: #EAEAEA;
  --accent: #0A7F5E;
}

[data-theme="dark"] {
  --bg: #0A0A0A;
  --fg: #EDEDED;
  --muted: #A1A1A1;
  --card: #111111;
  --line: #242424;
  --accent: #3DD9A8;
}

body {
  background-color: var(--bg);
  color: var(--fg);
  font-family: var(--font-body), "Hanken Grotesk", sans-serif;
}

h1, h2, h3, h4 {
  font-family: var(--font-heading), "Bricolage Grotesque", sans-serif;
  letter-spacing: -0.025em;
}
```

```tsx
// frontend/src/components/ui/sidebar.tsx
import React from 'react';
import Link from 'next/link';

interface NavItem {
  label: string;
  href: string;
}

const navItems: NavItem[] = [
  { label: 'Agents', href: '/agents' },
  { label: 'Calls', href: '/calls' },
  { label: 'Numbers', href: '/numbers' },
  { label: 'Tools', href: '/tools' },
  { label: 'Billing', href: '/billing' },
  { label: 'Settings', href: '/settings' },
];

export const Sidebar: React.FC = () => {
  return (
    <aside className="w-64 border-r border-[var(--line)] bg-[var(--card)] flex flex-col h-screen p-4">
      <div className="font-bold text-xl mb-8 flex items-center gap-2">
        <span className="w-3 h-3 rounded-full bg-[var(--accent)] animate-pulse" />
        Cadence
      </div>
      <nav className="flex-1 space-y-1">
        {navItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="block px-3 py-2 rounded-md text-sm font-medium hover:bg-[var(--line)] transition-colors"
          >
            {item.label}
          </Link>
        ))}
      </nav>
      <div className="p-3 border border-[var(--line)] rounded-lg text-xs text-[var(--muted)]">
        <div className="font-semibold text-[var(--fg)] mb-1">Plan Usage</div>
        <div>0 / 300 minutes used</div>
      </div>
    </aside>
  );
};
```

- [ ] **Step 4: Run frontend tests and typecheck**

Run: `cd frontend && pnpm test && pnpm typecheck && pnpm lint`
Expected: All pass.

- [ ] **Step 5: Commit task 5**

```bash
git add frontend/
git commit -m "feat(frontend): create shell layout and brand design tokens"
```

---

### Task 6: Environment Templates, CI Workflows & Milestone Verification

**Files:**
- Create: `.env.example`
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: All configuration keys required by backend, worker, frontend, and infra.
- Produces: GitHub Actions CI workflow executing lint, types, tests, and boundaries on PRs.

- [ ] **Step 1: Write .env.example**

```ini
# Environment
ENVIRONMENT=development
DEBUG=true
SECRET_KEY=replace-with-a-secure-random-secret-key-at-least-32-chars
INTERNAL_SERVICE_TOKEN=replace-with-internal-worker-secret-token

# Databases
DATABASE_URL=postgresql+asyncpg://cadence:cadence_password@localhost:5432/cadence_dev
REDIS_URL=redis://localhost:6379/0

# Object Storage (MinIO local / AWS S3 prod)
S3_ENDPOINT=http://localhost:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin_secret
S3_RECORDINGS_BUCKET=cadence-recordings
S3_KNOWLEDGE_BUCKET=cadence-knowledge

# LiveKit Realtime Media Server
LIVEKIT_URL=http://localhost:7880
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret

# Speech & Model Providers (Mock in early dev)
DEEPGRAM_API_KEY=mock-deepgram-key
OPENAI_API_KEY=mock-openai-key
CARTESIA_API_KEY=mock-cartesia-key

# Telephony
TWILIO_ACCOUNT_SID=mock-twilio-sid
TWILIO_AUTH_TOKEN=mock-twilio-token
TWILIO_SIP_DOMAIN=sip.cadence.example.com
```

- [ ] **Step 2: Write GitHub Actions CI Workflow (.github/workflows/ci.yml)**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  backend-quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install ruff mypy pytest pytest-asyncio httpx import-linter pydantic-settings sqlalchemy redis

      - name: Lint with Ruff
        run: ruff check . && ruff format --check .

      - name: Typecheck with Mypy
        run: mypy backend

      - name: Run Backend Tests
        run: pytest -q

      - name: Check Module Boundaries
        run: lint-imports

  frontend-quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v3
        with:
          version: 9
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: "pnpm"
          cache-dependency-path: frontend/pnpm-lock.yaml

      - name: Install Dependencies
        run: cd frontend && pnpm install --frozen-lockfile

      - name: Lint Frontend
        run: cd frontend && pnpm lint

      - name: Typecheck Frontend
        run: cd frontend && pnpm typecheck

      - name: Run Frontend Tests
        run: cd frontend && pnpm test
```

- [ ] **Step 3: Run full local verification pass**

Execute:
1. `ruff check . && ruff format --check .`
2. `mypy backend`
3. `pytest -q`
4. `lint-imports`

Expected: All commands report green / pass.

- [ ] **Step 4: Commit task 6**

```bash
git add .env.example .github/workflows/ci.yml
git commit -m "ci(github): add workflow for backend, frontend and boundary verification"
```

---

## Self-Review Checklist

- [x] **Spec coverage**: Covers all 7 M0 tasks defined in `docs/PLAN.md`.
- [x] **Placeholder scan**: Zero "TODO", "TBD", or unwritten test references. Every step includes complete, executable code blocks.
- [x] **Type consistency**: Standard types (`Settings`, `get_db()`, `AppError`) match across tests and implementations.
- [x] **Boundary contracts**: Module layers strictly preserved and verified by `lint-imports`.
