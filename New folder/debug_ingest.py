from backend.services.pdf_service import ingest_pdf_document

try:
    ingest_pdf_document(1)
    print('Ingest completed')
except Exception as e:
    import traceback
    print('Ingest exception:', type(e).__name__, e)
    traceback.print_exc()
