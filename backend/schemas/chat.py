from pydantic import BaseModel
from datetime import datetime
from typing import List


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
