from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.core import db
from backend.app.core.errors import AppError, app_error_handler
from backend.app.modules.agents import router as agents_router
from backend.app.modules.auth import router as auth_router
from backend.app.modules.billing import router as billing_router
from backend.app.modules.internal import router as internal_router
from backend.app.modules.organizations import router as organizations_router
from backend.app.modules.providers import router as providers_router
from backend.app.modules.sessions import router as sessions_router
from backend.app.modules.telephony import router as telephony_router
from backend.app.modules.tools import router as tools_router

app = FastAPI(title="Cadence API", version="0.1.0")
app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(organizations_router)
app.include_router(billing_router)
app.include_router(agents_router)
app.include_router(providers_router)
app.include_router(tools_router)
app.include_router(telephony_router)
app.include_router(sessions_router)
app.include_router(internal_router)


@app.get("/health/live", tags=["health"])
async def health_live() -> dict[str, str]:
    """Process-only liveness check independent of database."""
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
async def health_ready() -> JSONResponse:
    """Readiness check testing database and redis connectivity."""
    db_ok = await db.check_db_ready()
    redis_ok = await db.check_redis_ready()
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
