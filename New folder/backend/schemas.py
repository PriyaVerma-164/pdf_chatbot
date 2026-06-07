from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class PdfDocumentResponse(BaseModel):
    id: int
    pdf_name: str
    folder_name: Optional[str]
    file_path: str
    file_hash: str
    total_pages: int
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UploadResponse(BaseModel):
    message: str
    pdf_id: int
    pdf_name: str
    status: str


class PdfListResponse(BaseModel):
    pdfs: List[PdfDocumentResponse]


class ChatHistoryItem(BaseModel):
    role: str
    message: str


class ChatRequest(BaseModel):
    pdf_id: Optional[int] = None
    pdf_name: Optional[str] = None
    question: str
    chat_history: List[ChatHistoryItem] = Field(default_factory=list)
