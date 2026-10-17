from fastapi import FastAPI
from fastapi.responses import JSONResponse

from backend.app.core import db
from backend.app.core.errors import AppError, app_error_handler

app = FastAPI(title="Cadence API", version="0.1.0")
app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]


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
