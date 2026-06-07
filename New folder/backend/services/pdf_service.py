import hashlib
import re
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import fitz
from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..config import settings
from ..database import SessionLocal
from ..models import PdfChunk, PdfDocument
from .embedding_service import embed_texts
from .monitoring_service import log_metric, throttle_cpu
from .qdrant_service import PointStruct, count_vectors, delete_vectors_for_pdf, upsert_vectors

PDF_HEADER = b"%PDF"


def sanitize_filename(filename: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]", "_", Path(filename).name)
    return (cleaned or "upload.pdf")[:220]


def compute_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_pdf_bytes(contents: bytes, filename: str) -> None:
    filename = filename or ""
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")
    if len(contents) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"PDF exceeds maximum size of {settings.MAX_UPLOAD_MB} MB.")
    if not contents.startswith(PDF_HEADER):
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid PDF.")


def save_upload_file(contents: bytes, filename: str) -> Path:
    safe_name = sanitize_filename(filename or "upload.pdf")
    destination = settings.UPLOAD_DIR / safe_name
    if destination.exists():
        destination = settings.UPLOAD_DIR / f"{Path(safe_name).stem}_{uuid.uuid4().hex[:8]}.pdf"
    with open(destination, "wb") as buffer:
        buffer.write(contents)
    return destination


def get_pdf_by_hash(db: Session, file_hash: str):
    return db.query(PdfDocument).filter(PdfDocument.file_hash == file_hash).first()


def get_pdf_by_path(db: Session, file_path: str):
    return db.query(PdfDocument).filter(PdfDocument.file_path == file_path).first()


def create_pdf_document(db: Session, file_path: Path, file_hash: str, folder_name: Optional[str] = None) -> PdfDocument:
    document = PdfDocument(
        pdf_name=file_path.name,
        folder_name=folder_name,
        file_path=str(file_path),
        file_hash=file_hash,
        total_pages=0,
        status="pending",
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def extract_page_texts(file_path: Path) -> List[str]:
    text_pages: List[str] = []
    with fitz.open(str(file_path)) as doc:
        for page in doc:
            page_text = page.get_text("text") or ""
            text_pages.append(page_text.strip())
    return text_pages


def build_chunks(page_texts: List[str]) -> List[Dict]:
    chunks = []
    page_token_limit = max(settings.CHUNK_SIZE, 1)
    overlap = min(max(settings.CHUNK_OVERLAP, 0), max(page_token_limit - 1, 0))
    step = max(page_token_limit - overlap, 1)
    for page_index, page_text in enumerate(page_texts, start=1):
        words = page_text.split()
        if not words:
            continue
        start = 0
        while start < len(words):
            throttle_cpu()
            end = min(start + page_token_limit, len(words))
            chunk_text = " ".join(words[start:end]).strip()
            chunk_hash = compute_hash(chunk_text.encode("utf-8"))
            chunks.append({
                "chunk_text": chunk_text,
                "page_number": page_index,
                "chunk_hash": chunk_hash,
            })
            if end == len(words):
                break
            start += step
    return chunks


def persist_chunks(db: Session, pdf: PdfDocument, chunks: List[Dict]) -> Tuple[List[PdfChunk], int, int]:
    existing_hashes = {
        row[0] for row in db.query(PdfChunk.chunk_hash).filter(PdfChunk.pdf_id == pdf.id).all()
    }
    new_chunks = []
    created = 0
    skipped = 0
    for chunk in chunks:
        if chunk["chunk_hash"] in existing_hashes:
            skipped += 1
            continue
        chunk_id = uuid.uuid4().hex
        pdf_chunk = PdfChunk(
            pdf_id=pdf.id,
            chunk_id=chunk_id,
            chunk_text=chunk["chunk_text"],
            page_number=chunk["page_number"],
            chunk_hash=chunk["chunk_hash"],
            embedding_status="pending",
        )
        db.add(pdf_chunk)
        new_chunks.append(pdf_chunk)
        created += 1
    db.commit()
    for chunk in new_chunks:
        db.refresh(chunk)
    return new_chunks, created, skipped


def embed_and_index_chunks(chunks: List[PdfChunk], pdf: PdfDocument):
    if not chunks:
        return
    texts = [chunk.chunk_text for chunk in chunks]
    embeddings = embed_texts(texts)
    if len(embeddings) != len(chunks):
        raise RuntimeError(f"Embedding count mismatch: expected {len(chunks)}, got {len(embeddings)}")

    points = []
    for chunk, vector in zip(chunks, embeddings):
        if len(vector) != settings.EMBEDDING_DIMENSIONS:
            raise RuntimeError(
                f"Embedding dimension mismatch for chunk {chunk.chunk_id}: "
                f"expected {settings.EMBEDDING_DIMENSIONS}, got {len(vector)}"
            )
        point_id = chunk.chunk_id
        payload = {
            "pdf_id": str(pdf.id),
            "pdf_name": pdf.pdf_name,
            "folder_name": pdf.folder_name or "",
            "page_number": chunk.page_number,
            "chunk_id": chunk.chunk_id,
            "chunk_text": chunk.chunk_text,
        }
        points.append(PointStruct(id=point_id, vector=vector, payload=payload))

    upsert_vectors(points)

    session = SessionLocal()
    try:
        for chunk in chunks:
            stored_chunk = session.get(PdfChunk, chunk.id)
            if stored_chunk:
                stored_chunk.embedding_status = "completed"
                stored_chunk.qdrant_point_id = chunk.chunk_id
        session.commit()
    finally:
        session.close()


def reset_pdf_for_new_file(db: Session, pdf: PdfDocument, file_hash: str) -> None:
    delete_vectors_for_pdf(pdf_id=pdf.id)
    db.query(PdfChunk).filter(PdfChunk.pdf_id == pdf.id).delete(synchronize_session=False)
    pdf.file_hash = file_hash
    pdf.total_pages = 0
    pdf.status = "pending"
    db.commit()
    db.refresh(pdf)


def get_chunks_for_reindex(db: Session, pdf: PdfDocument, new_chunks: List[PdfChunk]) -> List[PdfChunk]:
    if new_chunks:
        return new_chunks

    all_chunks = db.query(PdfChunk).filter(PdfChunk.pdf_id == pdf.id).all()
    pending_chunks = [chunk for chunk in all_chunks if chunk.embedding_status != "completed"]
    if pending_chunks:
        return pending_chunks

    indexed_count = count_vectors(pdf_id=pdf.id)
    if indexed_count < len(all_chunks):
        for chunk in all_chunks:
            chunk.embedding_status = "pending"
            chunk.qdrant_point_id = None
        db.commit()
        return all_chunks

    return []


def pdf_needs_ingestion(db: Session, pdf: PdfDocument) -> bool:
    if pdf.status != "ingested":
        return True

    chunk_count = db.query(PdfChunk).filter(PdfChunk.pdf_id == pdf.id).count()
    if chunk_count == 0:
        return True

    pending_count = db.query(PdfChunk).filter(
        PdfChunk.pdf_id == pdf.id,
        PdfChunk.embedding_status != "completed",
    ).count()
    if pending_count:
        return True

    return count_vectors(pdf_id=pdf.id) < chunk_count


def ingest_pdf_document(pdf_id: int) -> None:
    db = SessionLocal()
    start_time = time.time()
    try:
        pdf = db.get(PdfDocument, pdf_id)
        if not pdf:
            return
        pdf.status = "ingesting"
        db.commit()
        page_texts = extract_page_texts(Path(pdf.file_path))
        pdf.total_pages = len(page_texts)
        db.commit()
        chunks = build_chunks(page_texts)
        if not chunks:
            pdf.status = "failed"
            db.commit()
            return
        new_chunks, created, skipped = persist_chunks(db, pdf, chunks)
        pending_chunks = get_chunks_for_reindex(db, pdf, new_chunks)
        if pending_chunks:
            embed_and_index_chunks(pending_chunks, pdf)
        pdf.status = "ingested"
        db.commit()
        log_metric("pdf_ingestion_time_ms", int((time.time() - start_time) * 1000), extra=f"pdf_id={pdf.id} created={created} skipped={skipped}")
    except Exception:
        pdf = db.get(PdfDocument, pdf_id)
        if pdf:
            pdf.status = "failed"
            db.commit()
        raise
    finally:
        db.close()


def schedule_ingest_pdf_file(file_path: Path, folder_name: Optional[str] = None) -> PdfDocument:
    file_hash = compute_hash(file_path.read_bytes())
    db = SessionLocal()
    try:
        existing = get_pdf_by_hash(db, file_hash)
        if existing is not None:
            return existing
        document = get_pdf_by_path(db, str(file_path))
        if document is None:
            document = create_pdf_document(db, file_path, file_hash, folder_name)
        else:
            reset_pdf_for_new_file(db, document, file_hash)
        return document
    finally:
        db.close()


def ingest_folder_files() -> List[Dict]:
    results = []
    db = SessionLocal()
    try:
        for folder in settings.INGEST_FOLDERS:
            if not folder.exists():
                continue
            for path in folder.rglob("*.pdf"):
                try:
                    file_hash = compute_hash(path.read_bytes())
                    document = db.query(PdfDocument).filter(PdfDocument.file_path == str(path)).first()
                    if document and document.file_hash == file_hash:
                        if pdf_needs_ingestion(db, document):
                            document.status = "pending"
                            db.commit()
                            results.append({"pdf_id": document.id, "pdf_name": path.name, "status": "retry"})
                        else:
                            results.append({"pdf_id": document.id, "pdf_name": path.name, "status": "skipped"})
                        continue
                    if document is None:
                        document = create_pdf_document(db, path, file_hash, folder.name)
                        results.append({"pdf_id": document.id, "pdf_name": path.name, "status": "new"})
                    else:
                        reset_pdf_for_new_file(db, document, file_hash)
                        results.append({"pdf_id": document.id, "pdf_name": path.name, "status": "updated"})
                except Exception:
                    results.append({"pdf_name": path.name, "status": "error"})
        return results
    finally:
        db.close()


def list_pdf_documents() -> List[PdfDocument]:
    db = SessionLocal()
    try:
        return db.query(PdfDocument).order_by(PdfDocument.created_at.desc()).all()
    finally:
        db.close()


def upload_pdf_file(file: UploadFile) -> PdfDocument:
    contents = file.file.read()
    validate_pdf_bytes(contents, file.filename)
    file_hash = compute_hash(contents)
    db = SessionLocal()
    try:
        existing = get_pdf_by_hash(db, file_hash)
        if existing is not None:
            return existing
        save_path = save_upload_file(contents, file.filename)
        document = create_pdf_document(db, save_path, file_hash, folder_name="uploaded")
        return document
    finally:
        db.close()
