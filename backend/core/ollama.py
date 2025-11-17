import requests
from fastapi import HTTPException

from core.config import OLLAMA_BASE_URL
from repositories.message_repo import get_messages_for_user


def generate_assistant_reply_from_ollama(user_id: int, user_content: str, model_name: str) -> str:
    """
    Вызывает Ollama /api/chat с историей диалога + новым сообщением.
    Возвращает текст ответа модели.
    """
    history_rows = get_messages_for_user(user_id=user_id, limit=50)

    messages_for_ollama = [
        {"role": row["role"], "content": row["content"]}
        for row in history_rows
    ]
    messages_for_ollama.append({"role": "user", "content": user_content})

    payload = {
        "model": model_name,
        "messages": messages_for_ollama,
        "stream": False,
    }

    try:
        resp = requests.post(f"{OLLAMA_BASE_URL}/chat", json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        return data["message"]["content"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ollama error: {e}")
