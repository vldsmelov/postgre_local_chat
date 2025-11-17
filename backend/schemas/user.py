from pydantic import BaseModel, EmailStr
from typing import Optional


class UserCreate(BaseModel):
    email: EmailStr
    display_name: str
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    display_name: str
    streaming_enabled: bool
    preferred_model: Optional[str] = None


class UserSettingsUpdate(BaseModel):
    streaming_enabled: bool
    preferred_model: str
