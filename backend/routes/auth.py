from fastapi import APIRouter, HTTPException, status

from schemas.user import UserCreate, UserLogin, UserResponse
from repositories.user_repo import (
    get_user_by_email,
    create_user,
    verify_user_credentials,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse)
def register(user: UserCreate):
    existing = get_user_by_email(user.email)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким email уже существует",
        )

    row = create_user(user)
    return UserResponse(
        id=row["id"],
        email=row["email"],
        display_name=row["display_name"],
        streaming_enabled=row["streaming_enabled"],
        preferred_model=row["preferred_model"],
    )


@router.post("/login", response_model=UserResponse)
def login(data: UserLogin):
    row = verify_user_credentials(data.email, data.password)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
        )

    return UserResponse(
        id=row["id"],
        email=row["email"],
        display_name=row["display_name"],
        streaming_enabled=row["streaming_enabled"],
        preferred_model=row["preferred_model"],
    )
