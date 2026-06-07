from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from .database import Base


class PdfDocument(Base):
    __tablename__ = "pdf_documents"

    id = Column(Integer, primary_key=True, index=True)
    pdf_name = Column(String(255), nullable=False)
    folder_name = Column(String(255), nullable=True)
    file_path = Column(String(1024), nullable=False, unique=True)
    file_hash = Column(String(128), nullable=False, unique=True)
    total_pages = Column(Integer, nullable=False, default=0)
    status = Column(String(32), nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PdfChunk(Base):
    __tablename__ = "pdf_chunks"

    id = Column(Integer, primary_key=True, index=True)
    pdf_id = Column(Integer, ForeignKey("pdf_documents.id", ondelete="CASCADE"), nullable=False)
    chunk_id = Column(String(128), nullable=False, unique=True)
    chunk_text = Column(Text, nullable=False)
    page_number = Column(Integer, nullable=False)
    chunk_hash = Column(String(128), nullable=False)
    embedding_status = Column(String(32), nullable=False, default="pending")
    qdrant_point_id = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
