from typing import List, Mapping

from sqlalchemy import text

from core.db import engine


def get_messages_for_user(user_id: int, limit: int = 50) -> List[Mapping]:
    query = text("""
        SELECT id, user_id, role, content, created_at
        FROM messages
        WHERE user_id = :user_id
        ORDER BY created_at ASC
        LIMIT :limit
    """)
    with engine.connect() as conn:
        result = conn.execute(query, {"user_id": user_id, "limit": limit})
        return result.mappings().all()


def add_message(user_id: int, role: str, content: str) -> Mapping:
    query = text("""
        INSERT INTO messages (user_id, role, content)
        VALUES (:user_id, :role, :content)
        RETURNING id, user_id, role, content, created_at
    """)
    params = {"user_id": user_id, "role": role, "content": content}
    with engine.connect() as conn:
        result = conn.execute(query, params)
        conn.commit()
        return result.mappings().first()
