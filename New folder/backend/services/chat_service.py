import json
import logging
import time
from typing import Any, Dict, Generator, List, Optional

import openai
import requests

from ..config import settings
from ..database import SessionLocal
from ..models import PdfDocument
from .qdrant_service import search_vectors
from .monitoring_service import log_metric

SYSTEM_PROMPT = (
    "Answer only using the provided PDF context. Do not use outside knowledge. "
    "If the answer is not found, say the information is not available in the selected PDF."
)
logger = logging.getLogger(__name__)


def build_system_message() -> Dict[str, str]:
    return {"role": "system", "content": SYSTEM_PROMPT}


def get_history_value(item: Any, key: str, default: str = "") -> str:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def build_user_message(question: str, contexts: List[str], history: Optional[List[Any]] = None) -> Dict[str, str]:
    joined = "\n\n".join(contexts)
    history_text = ""
    if history:
        history_text = "\n\nConversation history:\n"
        for item in history:
            role = str(get_history_value(item, "role", "user") or "user").capitalize()
            message = str(get_history_value(item, "message", "") or "").strip()
            if not message:
                continue
            history_text += f"{role}: {message}\n"
    prompt = (
        "Use the following PDF excerpts to answer the question. "
        "Do not invent answers outside of these excerpts.\n\n"
        f"Context:\n{joined}{history_text}\nQuestion: {question}"
    )
    return {"role": "user", "content": prompt}


def iter_openai_compatible_stream(response: requests.Response) -> Generator[str, None, None]:
    for line in response.iter_lines(decode_unicode=True):
        if not line:
            continue
        line = line.strip()
        if line.startswith("data:"):
            line = line.removeprefix("data:").strip()
        if not line or line == "[DONE]":
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            logger.debug("Skipping malformed LLM stream line: %s", line[:200])
            continue

        choices = event.get("choices") or []
        if not choices:
            continue

        choice = choices[0]
        delta = choice.get("delta") or {}
        message = choice.get("message") or {}
        content = delta.get("content") or message.get("content") or ""
        if content:
            yield content


def find_pdf_record(pdf_id: Optional[int], pdf_name: Optional[str]):
    db = SessionLocal()
    try:
        if pdf_id is not None:
            return db.get(PdfDocument, pdf_id)
        if pdf_name:
            return db.query(PdfDocument).filter(PdfDocument.pdf_name == pdf_name).first()
        return None
    finally:
        db.close()


def collect_context_for_pdf(pdf_id: Optional[int], pdf_name: Optional[str], question: str):
    from .embedding_service import embed_texts

    placeholder = question if question else ""
    embeddings = embed_texts([placeholder])
    if not embeddings:
        return [], []
    query_vector = embeddings[0]
    raw_results = search_vectors(query_vector, pdf_id=pdf_id, pdf_name=pdf_name, top_k=settings.TOP_K)
    contexts = []
    page_set = set()
    for hit in raw_results:
        payload = hit.payload or {}
        page = payload.get("page_number")
        chunk_text = payload.get("chunk_text", "")
        if not chunk_text:
            continue
        citation = f"[Page {page}]" if page is not None else ""
        contexts.append(f"{citation} {chunk_text}".strip())
        if page is not None:
            page_set.add(page)
    return contexts, sorted(page_set)


def make_stream_response(question: str, contexts: List[str], page_numbers: List[int], history: Optional[List[Any]] = None) -> Generator[str, None, None]:
    provider = settings.LLM_PROVIDER
    messages = [build_system_message(), build_user_message(question, contexts, history)]

    if provider in ("openai", "azure"):
        openai.api_key = settings.OPENAI_API_KEY
        if provider == "azure":
            openai.api_type = "azure"
            openai.api_base = settings.AZURE_ENDPOINT
            openai.api_version = settings.AZURE_API_VERSION
            openai.api_key = settings.AZURE_API_KEY

        stream = openai.ChatCompletion.create(
            model=settings.CHAT_MODEL,
            messages=messages,
            temperature=0.0,
            stream=True,
        )

        for event in stream:
            delta = event.choices[0].delta
            text = delta.get("content", "")
            if text:
                yield text
    elif provider == "ollama":
        endpoint = f"{settings.OLLAMA_URL}/chat/completions"
        payload = {
            "model": settings.CHAT_MODEL,
            "messages": messages,
            "temperature": 0.0,
            "stream": True,
        }
        response = requests.post(
            endpoint,
            json=payload,
            stream=True,
            timeout=(10, settings.LLM_TIMEOUT_SECONDS),
        )
        response.raise_for_status()
        yield from iter_openai_compatible_stream(response)
    else:
        yield "This information is not available in the selected PDF."

    if page_numbers:
        citation = ", ".join(f"[Page {p}]" for p in page_numbers)
        yield f"\n\nSources: {citation}"


def ask_question(pdf_id: Optional[int], pdf_name: Optional[str], question: str, chat_history: Optional[List[Any]] = None) -> Generator[str, None, None]:
    start_time = time.perf_counter()
    pdf_record = find_pdf_record(pdf_id, pdf_name)
    if not pdf_record:
        yield "This information is not available in the selected PDF."
        return
    if pdf_record.status != "ingested":
        yield f"The selected PDF is not ready yet. Current status: {pdf_record.status}."
        return

    contexts, pages = collect_context_for_pdf(pdf_id=pdf_id, pdf_name=pdf_name, question=question)
    if not contexts:
        yield "This information is not available in the selected PDF."
        return

    for token in make_stream_response(question, contexts, pages):
        yield token

    log_metric("query_response_time_ms", int((time.perf_counter() - start_time) * 1000), extra=f"pdf_id={pdf_record.id}")
