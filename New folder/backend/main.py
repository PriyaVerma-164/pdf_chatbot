import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import Base, engine
from .routers import chat_router, pdf_router
from .services.qdrant_service import init_qdrant_collection

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(message)s")

app = FastAPI(title="Single PDF Chatbot")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

app.include_router(pdf_router.router)
app.include_router(chat_router.router)

frontend_path = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")


@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)
    init_qdrant_collection()
