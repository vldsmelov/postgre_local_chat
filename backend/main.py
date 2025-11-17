import logging

from fastapi import FastAPI

from routes.health import router as health_router
from routes.auth import router as auth_router
from routes.chat import router as chat_router
from routes.users import router as users_router
from routes.models import router as models_router

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Alabuga Chat API")

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(users_router)
app.include_router(models_router)
