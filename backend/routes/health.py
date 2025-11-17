from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from core.db import engine

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    """Простой пинг, чтобы понять, что API живо."""
    return {"status": "ok"}


@router.get("/db-test")
def db_test():
    """Пробуем сделать простой запрос в БД."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            _ = result.scalar()
        return {"db": "ok"}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"db": "error", "details": str(e)}
        )
