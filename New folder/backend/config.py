import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads")).resolve()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

INGEST_FOLDERS = [Path(item.strip()).resolve() for item in os.getenv("INGEST_FOLDERS", "./data,./finance").split(",") if item.strip()]
for folder in INGEST_FOLDERS:
    folder.mkdir(parents=True, exist_ok=True)

class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'app.db'}")
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY", "")
    QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "pdf_embeddings")

    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai").lower()
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    AZURE_API_KEY: str = os.getenv("AZURE_API_KEY", "")
    AZURE_ENDPOINT: str = os.getenv("AZURE_ENDPOINT", "")
    AZURE_API_VERSION: str = os.getenv("AZURE_API_VERSION", "2024-06-01-preview")
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434/v1").rstrip("/")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "nomic-embed-text:latest")
    EMBEDDING_DIMENSIONS: int = int(os.getenv("EMBEDDING_DIMENSIONS", "3072"))
    CHAT_MODEL: str = os.getenv("CHAT_MODEL", "gpt-4o-mini")
    LLM_TIMEOUT_SECONDS: int = int(os.getenv("LLM_TIMEOUT_SECONDS", "300"))

    MAX_WORKERS: int = int(os.getenv("MAX_WORKERS", "2"))
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "700"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "80"))
    TOP_K: int = int(os.getenv("TOP_K", "4"))
    MAX_UPLOAD_MB: int = int(os.getenv("MAX_UPLOAD_MB", "25"))
    CPU_THRESHOLD: int = int(os.getenv("CPU_THRESHOLD", "50"))

    ALLOWED_ORIGINS = [item.strip() for item in os.getenv("ALLOWED_ORIGINS", "http://localhost:8000").split(",") if item.strip()]
    UPLOAD_DIR = UPLOAD_DIR
    INGEST_FOLDERS = INGEST_FOLDERS

settings = Settings()
