from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from core.db import engine
from repositories.user_repo import get_user_by_id
from schemas.user import UserSettingsUpdate, UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.patch("/{user_id}/settings", response_model=UserResponse)
def update_user_settings(user_id: int, payload: UserSettingsUpdate):
    user = get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    query = text("""
        UPDATE users
        SET streaming_enabled = :streaming_enabled,
            preferred_model = :preferred_model
        WHERE id = :id
        RETURNING id, email, display_name, streaming_enabled, preferred_model
    """)

    with engine.connect() as conn:
        result = conn.execute(
            query,
            {
                "id": user_id,
                "streaming_enabled": payload.streaming_enabled,
                "preferred_model": payload.preferred_model,
            },
        )
        conn.commit()
        row = result.mappings().first()

    return UserResponse(
        id=row["id"],
        email=row["email"],
        display_name=row["display_name"],
        streaming_enabled=row["streaming_enabled"],
        preferred_model=row["preferred_model"],
    )
