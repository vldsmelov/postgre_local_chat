from typing import Optional, Mapping

from sqlalchemy import text

from core.db import engine
from core.security import hash_password, verify_password
from schemas.user import UserCreate


def get_user_by_email(email: str) -> Optional[Mapping]:
    query = text("""
        SELECT id, email, display_name, password_hash, streaming_enabled, preferred_model
        FROM users
        WHERE email = :email
    """)
    with engine.connect() as conn:
        result = conn.execute(query, {"email": email})
        return result.mappings().first()


def create_user(user: UserCreate) -> Mapping:
    query = text("""
        INSERT INTO users (email, display_name, password_hash)
        VALUES (:email, :display_name, :password_hash)
        RETURNING id, email, display_name, streaming_enabled, preferred_model
    """)
    params = {
        "email": user.email,
        "display_name": user.display_name,
        "password_hash": hash_password(user.password),
    }
    with engine.connect() as conn:
        result = conn.execute(query, params)
        conn.commit()
        return result.mappings().first()


def verify_user_credentials(email: str, password: str) -> Optional[Mapping]:
    query = text("""
        SELECT id, email, display_name, password_hash, streaming_enabled, preferred_model
        FROM users
        WHERE email = :email
    """)
    with engine.connect() as conn:
        result = conn.execute(query, {"email": email})
        row = result.mappings().first()
        if row is None:
            return None

        stored_hash = row["password_hash"]
        if not verify_password(password, stored_hash):
            return None

        return row


def get_user_by_id(user_id: int) -> Optional[Mapping]:
    query = text("""
        SELECT id, email, display_name, streaming_enabled, preferred_model
        FROM users
        WHERE id = :id
    """)
    with engine.connect() as conn:
        result = conn.execute(query, {"id": user_id})
        return result.mappings().first()
