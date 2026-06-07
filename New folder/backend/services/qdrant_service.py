from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PointStruct,
    VectorParams,
)

from ..config import settings
from .monitoring_service import log_metric

client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY or None)


def build_pdf_filter(pdf_id=None, pdf_name=None):
    filters = []
    if pdf_id is not None:
        filters.append(FieldCondition(key="pdf_id", match=MatchValue(value=str(pdf_id))))
    elif pdf_name is not None:
        filters.append(FieldCondition(key="pdf_name", match=MatchValue(value=pdf_name)))
    return Filter(must=filters) if filters else None


def init_qdrant_collection() -> None:
    existing = [collection.name for collection in client.get_collections().collections]
    if settings.QDRANT_COLLECTION not in existing:
        client.recreate_collection(
            collection_name=settings.QDRANT_COLLECTION,
            vectors_config=VectorParams(size=settings.EMBEDDING_DIMENSIONS, distance=Distance.COSINE),
        )
        log_metric("qdrant_collection", 1, extra=f"name={settings.QDRANT_COLLECTION}")
        return

    collection = client.get_collection(collection_name=settings.QDRANT_COLLECTION)
    current_size = collection.config.params.vectors.size
    if current_size != settings.EMBEDDING_DIMENSIONS:
        client.recreate_collection(
            collection_name=settings.QDRANT_COLLECTION,
            vectors_config=VectorParams(size=settings.EMBEDDING_DIMENSIONS, distance=Distance.COSINE),
        )
        log_metric("qdrant_collection_recreated", 1, extra=f"name={settings.QDRANT_COLLECTION} old_size={current_size} new_size={settings.EMBEDDING_DIMENSIONS}")


def upsert_vectors(points):
    if not points:
        return
    client.upsert(collection_name=settings.QDRANT_COLLECTION, points=points)
    log_metric("qdrant_upsert", len(points), extra=f"collection={settings.QDRANT_COLLECTION}")


def delete_vectors_for_pdf(pdf_id=None, pdf_name=None):
    payload_filter = build_pdf_filter(pdf_id=pdf_id, pdf_name=pdf_name)
    if payload_filter is None:
        return
    client.delete(
        collection_name=settings.QDRANT_COLLECTION,
        points_selector=FilterSelector(filter=payload_filter),
    )
    log_metric("qdrant_delete", 1, extra=f"collection={settings.QDRANT_COLLECTION} pdf_id={pdf_id} pdf_name={pdf_name}")


def count_vectors(pdf_id=None, pdf_name=None) -> int:
    payload_filter = build_pdf_filter(pdf_id=pdf_id, pdf_name=pdf_name)
    result = client.count(
        collection_name=settings.QDRANT_COLLECTION,
        count_filter=payload_filter,
        exact=True,
    )
    return result.count


def search_vectors(query_vector, pdf_id=None, pdf_name=None, top_k=4):
    payload_filter = build_pdf_filter(pdf_id=pdf_id, pdf_name=pdf_name)
    results = client.search(
        collection_name=settings.QDRANT_COLLECTION,
        query_vector=query_vector,
        query_filter=payload_filter,
        limit=top_k,
        with_payload=True,
        with_vectors=False,
    )
    log_metric("qdrant_search", len(results), extra=f"top_k={top_k} pdf_id={pdf_id} pdf_name={pdf_name}")
    return results
