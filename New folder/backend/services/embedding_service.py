import time
import requests
import openai

from ..config import settings
from .monitoring_service import log_metric


def embed_texts(texts):
    start_time = time.perf_counter()
    provider = settings.LLM_PROVIDER
    if provider == "openai":
        openai.api_key = settings.OPENAI_API_KEY
        response = openai.Embedding.create(model=settings.EMBEDDING_MODEL, input=texts)
        embeddings = [item["embedding"] for item in response["data"]]
    elif provider == "azure":
        openai.api_type = "azure"
        openai.api_base = settings.AZURE_ENDPOINT
        openai.api_version = settings.AZURE_API_VERSION
        openai.api_key = settings.AZURE_API_KEY
        response = openai.Embedding.create(model=settings.EMBEDDING_MODEL, input=texts)
        embeddings = [item["embedding"] for item in response["data"]]
    elif provider == "ollama":
        endpoint = f"{settings.OLLAMA_URL}/embeddings"
        payload = {"model": settings.EMBEDDING_MODEL, "input": texts}
        response = requests.post(endpoint, json=payload, timeout=(10, settings.LLM_TIMEOUT_SECONDS))
        response.raise_for_status()
        data = response.json()
        embeddings = [item["embedding"] for item in data.get("data", [])]
    else:
        raise ValueError(f"Unsupported embedding provider: {provider}")

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
    log_metric("embedding_latency_ms", elapsed_ms, extra=f"count={len(texts)}")
    return embeddings
