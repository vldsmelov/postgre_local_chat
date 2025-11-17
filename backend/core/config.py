import os

DB_USER = os.getenv("DB_USER", "alabuga_app")
DB_PASSWORD = os.getenv("DB_PASSWORD", "alabuga_password")
DB_NAME = os.getenv("DB_NAME", "alabuga_chat")
DB_HOST = os.getenv("DB_HOST", "db")
DB_PORT = os.getenv("DB_PORT", "5432")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/api")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "granite32-vision-2b-4g")
