# Single PDF Chatbot

A production-ready single PDF chatbot built with FastAPI, Qdrant, PyMuPDF, and streaming SSE.

 Screensho of pdf_chabot Application
 <img width="1907" height="962" alt="image" src="https://github.com/user-attachments/assets/c6a29163-2498-48df-91db-07b7e817cfff" />

 After uploading PDF.
 <img width="1878" height="972" alt="image" src="https://github.com/user-attachments/assets/a123fe5e-2be6-4459-bc98-5ec0a65893f4" />
 Asking Questions to Chatbot
 <img width="1552" height="747" alt="image" src="https://github.com/user-attachments/assets/5c768eaa-d415-4157-b7a0-c1c61f35059a" />
 PDFS which are saved in library 
 
 <img width="316" height="402" alt="image" src="https://github.com/user-attachments/assets/175e1e3c-8d76-4221-8d24-e16c37f2009b" />
 VectorBD|Qdrant
 
 <img width="1891" height="966" alt="image" src="https://github.com/user-attachments/assets/3992ede6-42d1-49b2-86f5-30fcea0138f5" />
 <img width="1138" height="656" alt="image" src="https://github.com/user-attachments/assets/a671382f-c207-4e2a-9b39-a36c7eb154ca" />
<img width="1882" height="968" alt="image" src="https://github.com/user-attachments/assets/b673f1ae-78f0-4201-b51e-f6b25d38ee2b" />




 


 

## Features

- Upload a single PDF and ingest it automatically
- Select from ingested PDFs in the folder
- Ask questions about the selected PDF only
- Token-by-token streaming answer delivery
- Page-based source citations in responses
- Qdrant vector search with PDF-specific filtering
- SQL tracking for documents and chunks
- CPU-aware ingestion and batch embeddings

## Project structure

- `backend/`
  - `main.py`
  - `config.py`
  - `database.py`
  - `models.py`
  - `schemas.py`
  - `services/`
  - `routers/`
- `frontend/`
  - `index.html`
  - `style.css`
  - `app.js`
- `.env`
- `requirements.txt`

## Setup

1. Create a Python environment and install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Configure `.env` with your database, Qdrant, Ollama, and model settings.

3. Start Qdrant locally or point `QDRANT_URL` to your Qdrant instance:

```powershell
docker run -p 6333:6333 qdrant/qdrant
```

4. Start Ollama and make sure the configured models are installed:

```powershell
ollama serve
ollama pull nomic-embed-text:latest
ollama pull qwen2.5:3b
```

5. Run the app from the project root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

6. Open `http://127.0.0.1:8000` in your browser.

## Usage

- Upload a PDF from the left panel
- Select a PDF from the list
- Ask a question using the chat box
- Answers stream live, and citations appear as `[Page X]`

## Notes

- The chatbot is restricted to the selected PDF only.
- Unchanged PDFs are skipped during folder ingestion.
- Embeddings are batched and reused when possible.

## Testing

1. Upload a PDF file using the UI.
2. Wait for ingestion to complete.
3. Select the uploaded PDF.
4. Ask a question related to the PDF.
5. Confirm the response includes a page citation and explains missing info when necessary.
