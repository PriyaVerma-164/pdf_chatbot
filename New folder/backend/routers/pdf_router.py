from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

from ..schemas import PdfListResponse, UploadResponse
from ..services.pdf_service import ingest_folder_files, ingest_pdf_document, list_pdf_documents, upload_pdf_file

router = APIRouter(prefix="/api/pdf", tags=["pdf"])


@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    try:
        document = upload_pdf_file(file)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    background_tasks.add_task(ingest_pdf_document, document.id)
    return UploadResponse(
        message="PDF uploaded successfully and scheduled for ingestion.",
        pdf_id=document.id,
        pdf_name=document.pdf_name,
        status=document.status,
    )


@router.post("/ingest-folder")
def ingest_folder(background_tasks: BackgroundTasks):
    results = ingest_folder_files()
    for entry in results:
        if entry["status"] in {"new", "updated", "retry"}:
            background_tasks.add_task(ingest_pdf_document, entry.get("pdf_id"))
    return {"detail": "Folder ingestion started.", "files": results}


@router.get("/list", response_model=PdfListResponse)
def list_pdfs():
    documents = list_pdf_documents()
    return PdfListResponse(pdfs=documents)
