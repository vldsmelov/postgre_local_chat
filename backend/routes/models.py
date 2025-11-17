import requests
from fastapi import APIRouter, HTTPException

from core.config import OLLAMA_BASE_URL
from schemas.models import ModelsListResponse

router = APIRouter(prefix="/models", tags=["models"])


@router.get("/names", response_model=ModelsListResponse)
def list_model_names():
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/tags", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        names = [m["name"] for m in data.get("models", [])]
        return ModelsListResponse(models=names)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения списка моделей: {e}",
        )
