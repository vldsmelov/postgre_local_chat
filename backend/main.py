from fastapi import FastAPI
from fastapi import HTTPException, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import create_engine, text
from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import List
import os
import requests
import json
import bcrypt
from typing import Optional
from typing import List
import logging



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


class Message(BaseModel):
    id: int
    user_id: int
    role: str
    content: str
    created_at: datetime


class ChatHistoryResponse(BaseModel):
    messages: List[Message]


class ChatSendRequest(BaseModel):
    user_id: int
    content: str


class ChatSendResponse(BaseModel):
    user_message: Message
    assistant_message: Message

class ModelsListResponse(BaseModel):
    models: List[str]


app = FastAPI()

# Берём настройки из переменных окружения
DB_USER = os.getenv("DB_USER", "alabuga_app")
DB_PASSWORD = os.getenv("DB_PASSWORD", "alabuga_password")
DB_NAME = os.getenv("DB_NAME", "alabuga_chat")
DB_HOST = os.getenv("DB_HOST", "db")  # имя сервиса из docker-compose
DB_PORT = os.getenv("DB_PORT", "5432")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL, echo=False, future=True)

# --- Настройки Ollama ---
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/api")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "granite32-vision-2b-4g") 

# Encrypt passes helpers

def hash_password(password: str) -> str:
    """
    Возвращает bcrypt-хэш пароля (строка для записи в БД).
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Проверяет, соответствует ли plain-пароль сохранённому bcrypt-хэшу.
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False


# ========= DB FUNCs ==========

# ========= USER FUNCs: START ==========
# take user by name
def get_user_by_email(email: str):
    query = text("""
        SELECT id, email, display_name, password_hash, streaming_enabled, preferred_model
        FROM users
        WHERE email = :email
    """)
    with engine.connect() as conn:
        result = conn.execute(query, {"email": email})
        row = result.mappings().first()
        return row  # dict-like объект или None

# REGISTRATION
def create_user(user: UserCreate):
    query = text("""
        INSERT INTO users (email, display_name, password_hash)
        VALUES (:email, :display_name, :password_hash)
        RETURNING id, email, display_name, streaming_enabled, preferred_model
    """)
    params = {
        "email": user.email,
        "display_name": user.display_name,
        "password_hash": hash_password(user.password),  # стало так
    }
    with engine.connect() as conn:
        result = conn.execute(query, params)
        conn.commit()
        row = result.mappings().first()
        return row


# LOGIN
def verify_user_credentials(email: str, password: str):
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
# ========= USER FUNCs: END ==========

# ========= CHAT FUNCs: START ==========
# Get chat history
def get_messages_for_user(user_id: int, limit: int = 50):
    query = text("""
        SELECT id, user_id, role, content, created_at
        FROM messages
        WHERE user_id = :user_id
        ORDER BY created_at ASC
        LIMIT :limit
    """)
    with engine.connect() as conn:
        result = conn.execute(query, {"user_id": user_id, "limit": limit})
        rows = result.mappings().all()
        return rows

# Send message
def add_message(user_id: int, role: str, content: str):
    query = text("""
        INSERT INTO messages (user_id, role, content)
        VALUES (:user_id, :role, :content)
        RETURNING id, user_id, role, content, created_at
    """)
    params = {
        "user_id": user_id,
        "role": role,
        "content": content
    }
    with engine.connect() as conn:
        result = conn.execute(query, params)
        conn.commit()
        row = result.mappings().first()
        return row

# User check
def get_user_by_id(user_id: int):
    # Проверям пользователя, чтобы не писать чат в несуществующего пользователя и не ловить ошибку БД
    query = text("""
        SELECT id, email, display_name, streaming_enabled, preferred_model
        FROM users
        WHERE id = :id
    """)
    with engine.connect() as conn:
        result = conn.execute(query, {"id": user_id})
        row = result.mappings().first()
        return row

# ========= CHAT FUNCs: END ==========

# ========= OLLAMA FUNCs: START ==========
def generate_assistant_reply_from_ollama(user_id: int, user_content: str, model_name: str) -> str:
    """
    Вызывает Ollama /api/chat с историей диалога + новым сообщением.
    Возвращает текст ответа модели.
    """
    # 1. Берём историю сообщений для пользователя
    history_rows = get_messages_for_user(user_id=user_id, limit=50)

    # 2. Собираем messages в формате Ollama
    messages_for_ollama = []

    for row in history_rows:
        messages_for_ollama.append({
            "role": row["role"],      # "user" или "assistant"
            "content": row["content"]
        })

    # Добавляем новое сообщение пользователя (ещё до записи в БД)
    messages_for_ollama.append({
        "role": "user",
        "content": user_content
    })

    payload = {
        "model": model_name,
        "messages": messages_for_ollama,
        "stream": False  # чтобы получить один JSON, а не поток
    }

    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/chat",
            json=payload,
            timeout=120
        )
        resp.raise_for_status()
        data = resp.json()
        # В соответствии с документацией, ответ лежит в data["message"]["content"] :contentReference[oaicite:1]{index=1}
        return data["message"]["content"]
    except Exception as e:
        # Можно залогировать и отдать понятную ошибку
        raise HTTPException(
            status_code=500,
            detail=f"Ollama error: {e}"
        )
# ========= OLLAMA FUNCs: END ==========

# ENDPOINTS
@app.get("/health")
def health():
    """Простой пинг, чтобы понять, что API живо."""
    return {"status": "ok"}


@app.get("/db-test")
def db_test():
    """Пробуем сделать простой запрос в БД."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            _ = result.scalar()
        return {"db": "ok"}
    except Exception as e:
        # В реальном коде так делать не стоит, но для дебага — нормально
        return JSONResponse(
            status_code=500,
            content={"db": "error", "details": str(e)}
        )

@app.post("/auth/register", response_model=UserResponse)
def register(user: UserCreate):
    # Проверяем, что пользователя с таким email ещё нет
    existing = get_user_by_email(user.email)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким email уже существует"
        )

    row = create_user(user)
    return UserResponse(
        id=row["id"],
        email=row["email"],
        display_name=row["display_name"],
        streaming_enabled=row["streaming_enabled"],
        preferred_model=row["preferred_model"]
    )


@app.post("/auth/login", response_model=UserResponse)
def login(data: UserLogin):
    row = verify_user_credentials(data.email, data.password)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль"
        )

    return UserResponse(
        id=row["id"],
        email=row["email"],
        display_name=row["display_name"],
        streaming_enabled=row["streaming_enabled"],
        preferred_model=row["preferred_model"]
    )

@app.get("/chat/history", response_model=ChatHistoryResponse)
def chat_history(user_id: int, limit: int = 50):
    # Можно проверить, что пользователь существует (опционально)
    user = get_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )

    rows = get_messages_for_user(user_id, limit=limit)
    messages = [
        Message(
            id=row["id"],
            user_id=row["user_id"],
            role=row["role"],
            content=row["content"],
            created_at=row["created_at"],
        )
        for row in rows
    ]
    return ChatHistoryResponse(messages=messages)


@app.post("/chat/send", response_model=ChatSendResponse)
def chat_send(req: ChatSendRequest):
    # Проверяем, что пользователь существует
    user = get_user_by_id(req.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )

    model_name = user["preferred_model"] or OLLAMA_MODEL

    logger.info(f"[chat_send] user_id=%s model=%s", req.user_id, model_name)

    # 1. Сохраняем сообщение пользователя
    user_row = add_message(
        user_id=req.user_id,
        role="user",
        content=req.content
    )

    # 2. Получаем ответ от модели Ollama с учётом контекста
    assistant_text = generate_assistant_reply_from_ollama(
        user_id=req.user_id,
        user_content=req.content,
        model_name=model_name
    )

    # 3. Сохраняем ответ ассистента
    assistant_row = add_message(
        user_id=req.user_id,
        role="assistant",
        content=assistant_text
    )

    user_msg = Message(
        id=user_row["id"],
        user_id=user_row["user_id"],
        role=user_row["role"],
        content=user_row["content"],
        created_at=user_row["created_at"],
    )

    assistant_msg = Message(
        id=assistant_row["id"],
        user_id=assistant_row["user_id"],
        role=assistant_row["role"],
        content=assistant_row["content"],
        created_at=assistant_row["created_at"],
    )

    return ChatSendResponse(
        user_message=user_msg,
        assistant_message=assistant_msg
    )


@app.post("/chat/send_stream")
def chat_send_stream(req: ChatSendRequest):
    # Проверяем, что пользователь существует
    user = get_user_by_id(req.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )

    model_name = user["preferred_model"] or OLLAMA_MODEL

    # Сохраняем сообщение пользователя сразу
    user_row = add_message(
        user_id=req.user_id,
        role="user",
        content=req.content
    )

    def event_stream():
        # 1. Берём историю для контекста
        history_rows = get_messages_for_user(user_id=req.user_id, limit=50)
        messages_for_ollama = []

        for row in history_rows:
            messages_for_ollama.append({
                "role": row["role"],
                "content": row["content"],
            })

        # Добавляем новое сообщение пользователя
        messages_for_ollama.append({
            "role": "user",
            "content": req.content
        })

        payload = {
            "model": model_name,
            "messages": messages_for_ollama,
            "stream": True,
                "options": {
                    "num_predict": 256,   # ограничим длину ответа
                    "repeat_penalty": 1.1 # слегка штрафуем повторения
                }
        }

        full_text = ""

        try:
            with requests.post(
                f"{OLLAMA_BASE_URL}/chat",
                json=payload,
                stream=True,
                timeout=None
            ) as r:
                r.raise_for_status()

                # Ollama отдаёт поток JSON-объектов, разделённых переводами строки :contentReference[oaicite:1]{index=1}
                for line in r.iter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line.decode("utf-8"))
                    except Exception:
                        continue

                    message = data.get("message") or {}
                    delta = message.get("content") or ""

                    if delta:
                        # Наращиваем полный текст
                        full_text += delta
                        # Отдаём клиенту «снимок» текущего текста
                        yield json.dumps({
                            "type": "delta",
                            "content": full_text
                        }) + "\n"

                    if data.get("done"):
                        break

        except Exception as e:
            # Сообщаем клиенту об ошибке
            yield json.dumps({
                "type": "error",
                "detail": str(e)
            }) + "\n"
            return

        # 2. Когда генерация закончилась — сохраняем ответ ассистента в БД
        assistant_row = add_message(
            user_id=req.user_id,
            role="assistant",
            content=full_text
        )

        # 3. Финальное событие
        yield json.dumps({
            "type": "done",
            "content": full_text,
            "user_message_id": user_row["id"],
            "assistant_message_id": assistant_row["id"],
        }) + "\n"

    return StreamingResponse(event_stream(), media_type="application/json")


class UserSettingsUpdate(BaseModel):
    streaming_enabled: bool
    preferred_model: str


@app.patch("/users/{user_id}/settings", response_model=UserResponse)
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
        result = conn.execute(query, {
            "id": user_id,
            "streaming_enabled": payload.streaming_enabled,
            "preferred_model": payload.preferred_model
        })
        conn.commit()
        row = result.mappings().first()

    return UserResponse(
        id=row["id"],
        email=row["email"],
        display_name=row["display_name"],
        streaming_enabled=row["streaming_enabled"],
        preferred_model=row["preferred_model"]
    )

@app.get("/models/names", response_model=ModelsListResponse)
def list_model_names():
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/tags", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        # Структура обычно: {"models": [{ "name": "llama3", ... }, ...]}
        names = [m["name"] for m in data.get("models", [])]
        return ModelsListResponse(models=names)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения списка моделей: {e}")
