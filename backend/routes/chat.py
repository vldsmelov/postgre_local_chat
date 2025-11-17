import json
import logging

import requests
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from core.config import OLLAMA_BASE_URL, OLLAMA_MODEL
from core.ollama import generate_assistant_reply_from_ollama
from repositories.message_repo import get_messages_for_user, add_message
from repositories.user_repo import get_user_by_id
from schemas.chat import (
    ChatHistoryResponse,
    ChatSendRequest,
    ChatSendResponse,
    Message,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/history", response_model=ChatHistoryResponse)
def chat_history(user_id: int, limit: int = 50):
    user = get_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден",
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


@router.post("/send", response_model=ChatSendResponse)
def chat_send(req: ChatSendRequest):
    user = get_user_by_id(req.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден",
        )

    model_name = user["preferred_model"] or OLLAMA_MODEL

    logger.info("[chat_send] user_id=%s model=%s", req.user_id, model_name)

    user_row = add_message(user_id=req.user_id, role="user", content=req.content)

    assistant_text = generate_assistant_reply_from_ollama(
        user_id=req.user_id,
        user_content=req.content,
        model_name=model_name,
    )

    assistant_row = add_message(
        user_id=req.user_id,
        role="assistant",
        content=assistant_text,
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
        assistant_message=assistant_msg,
    )


@router.post("/send_stream")
def chat_send_stream(req: ChatSendRequest):
    user = get_user_by_id(req.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден",
        )

    model_name = user["preferred_model"] or OLLAMA_MODEL

    user_row = add_message(user_id=req.user_id, role="user", content=req.content)

    def event_stream():
        history_rows = get_messages_for_user(user_id=req.user_id, limit=50)
        messages_for_ollama = [
            {"role": row["role"], "content": row["content"]}
            for row in history_rows
        ]
        messages_for_ollama.append({"role": "user", "content": req.content})

        payload = {
            "model": model_name,
            "messages": messages_for_ollama,
            "stream": True,
            "options": {
                "num_predict": 256,
                "repeat_penalty": 1.1,
            },
        }

        full_text = ""

        try:
            with requests.post(
                f"{OLLAMA_BASE_URL}/chat",
                json=payload,
                stream=True,
                timeout=None,
            ) as r:
                r.raise_for_status()

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
                        full_text += delta
                        yield json.dumps(
                            {"type": "delta", "content": full_text}
                        ) + "\n"

                    if data.get("done"):
                        break
        except Exception as e:
            yield json.dumps({"type": "error", "detail": str(e)}) + "\n"
            return

        assistant_row = add_message(
            user_id=req.user_id,
            role="assistant",
            content=full_text,
        )

        yield json.dumps(
            {
                "type": "done",
                "content": full_text,
                "user_message_id": user_row["id"],
                "assistant_message_id": assistant_row["id"],
            }
        ) + "\n"

    return StreamingResponse(event_stream(), media_type="application/json")
