from sqlalchemy import create_engine, text
from backend.config import settings
from backend.services.qdrant_service import client

engine = create_engine(settings.DATABASE_URL, connect_args={'check_same_thread': False})
print('DB file:', settings.DATABASE_URL)
with engine.connect() as conn:
    print('pdf_rows:', conn.execute(text('select id,pdf_name,total_pages,status,file_path,file_hash from pdf_documents')).fetchall())
    print('chunk_count:', conn.execute(text('select count(*) from pdf_chunks')).scalar())
try:
    cols = client.get_collections().collections
    print('qdrant cols:', [c.name for c in cols])
    print('count:', client.count(cols[0].name).count if cols else None)
except Exception as e:
    print('qdrant error', repr(e))
