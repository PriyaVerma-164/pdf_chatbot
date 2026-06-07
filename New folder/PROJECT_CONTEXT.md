# Project Context

## 1. Architecture

- **Backend**: FastAPI application located in `backend/`.
  - `backend/main.py` configures FastAPI, CORS, static frontend mount, DB initialization, and Qdrant collection initialization.
  - Routers are registered before the frontend static mount to ensure API routes work correctly.
- **Frontend**: Static files served from `frontend/`.
- **Database**: SQLite database at `backend/app.db` managed with SQLAlchemy in `backend/database.py`.
- **Vector Database**: Qdrant, configured in `backend/services/qdrant_service.py`.
- **Embedding + LLM**: Implemented in `backend/services/embedding_service.py` and `backend/services/chat_service.py`.

## 2. Completed Files

- `backend/main.py`
- `backend/config.py`
- `backend/database.py`
- `backend/models.py`
- `backend/schemas.py`
- `backend/routers/pdf_router.py`
- `backend/routers/chat_router.py`
- `backend/services/pdf_service.py`
- `backend/services/qdrant_service.py`
- `backend/services/embedding_service.py`
- `backend/services/chat_service.py`
- `requirements.txt`
- `.env`

## 3. APIs

- `POST /api/pdf/upload`
  - Uploads a PDF file.
  - Saves it to the local upload directory.
  - Creates or updates a PDF record in SQLite.
  - Schedules ingestion in the background.
- `POST /api/pdf/ingest-folder`
  - Scans folders defined by `INGEST_FOLDERS`.
  - Creates PDF records for new/updated files.
  - Schedules ingestion for each file.
- `GET /api/pdf/list`
  - Returns a list of PDF documents and metadata.
- `POST /api/chat/ask`
  - Accepts `pdf_id`, `pdf_name`, `question`, and optional `chat_history`.
  - Uses embeddings to search Qdrant.
  - Sends context to the LLM and streams the response.

## 4. Database Schema

### `pdf_documents`
- `id`: Integer, PK
- `pdf_name`: String
- `folder_name`: String
- `file_path`: String
- `file_hash`: String
- `total_pages`: Integer
- `status`: String (`pending`, `ingesting`, `ingested`, `failed`)
- `created_at`: DateTime
- `updated_at`: DateTime

### `pdf_chunks`
- `id`: Integer, PK
- `pdf_id`: Integer, FK to `pdf_documents.id`
- `chunk_id`: String, unique
- `chunk_text`: Text
- `page_number`: Integer
- `chunk_hash`: String
- `embedding_status`: String (`pending`, `completed`)
- `qdrant_point_id`: String
- `created_at`: DateTime
- `updated_at`: DateTime

## 5. Environment Variables

Current working `.env` values:

- `DATABASE_URL=sqlite:///./backend/app.db`
- `QDRANT_URL=http://localhost:6333`
- `QDRANT_API_KEY=`
- `QDRANT_COLLECTION=pdf_embeddings`
- `LLM_PROVIDER=ollama`
- `OLLAMA_URL=http://localhost:11434/v1`
- `EMBEDDING_MODEL=nomic-embed-text:latest`
- `EMBEDDING_DIMENSIONS=768`
- `CHAT_MODEL=qwen2.5:3b`
- `MAX_WORKERS=2`
- `CHUNK_SIZE=700`
- `CHUNK_OVERLAP=80`
- `TOP_K=4`
- `MAX_UPLOAD_MB=25`
- `CPU_THRESHOLD=50`
- `ALLOWED_ORIGINS=http://localhost:8000`
- `INGEST_FOLDERS=./data,./finance`

## 6. Key Project Notes

- The Qdrant collection now recreates automatically if the configured embedding dimension does not match the existing collection.
- The ingestion pipeline now embeds pending chunks even when no new chunks are created.
- The app currently uses Ollama for chat and embeddings via the `ollama` provider.
- `qwen2.5:3b` is configured as the chat model and `nomic-embed-text:latest` as the embedding model.

## 7. Pending Tasks

- Confirm full frontend chat flow end-to-end after restart.
- Add error handling for Ollama chat fallback or if the model is unavailable.
- Add better ingestion status visibility in the frontend.
- Add search/filter options for PDF metadata or folder-specific search.
- Add documentation or a README for project setup and deployment.

## 8. Next Steps

1. Restart the backend:
   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
   ```
2. Confirm `.env` values are correct.
3. Upload or ingest the target PDF.
4. Wait for the PDF status to become `ingested`.
5. Ask a question in the chat UI.
6. If the chat still fails, inspect:
   - backend logs
   - Qdrant collection point count
   - frontend request/response to `/api/chat/ask`
