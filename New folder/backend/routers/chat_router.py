import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..schemas import ChatRequest
from ..services.chat_service import ask_question

router = APIRouter(prefix="/api/chat", tags=["chat"])
logger = logging.getLogger(__name__)


@router.post("/ask")
def ask(request: ChatRequest):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question is required.")

    def event_generator():
        try:
            for token in ask_question(request.pdf_id, request.pdf_name, request.question, request.chat_history):
                yield f"data: {json.dumps(token)}\n\n"
        except Exception as exc:
            logger.exception("Chat request failed: %s", exc)
            message = "The local chat service could not complete the request. Check the backend logs and confirm Ollama is running with the configured model."
            yield f"data: {json.dumps(message)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
