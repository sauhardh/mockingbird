"""
HTTP client for the existing RAG service — query/response only.
Does not modify RAG internals; calls POST /rag/query on port 8005.
"""

import os
import logging
from typing import Any

logger = logging.getLogger(__name__)

RAG_BASE_URL = os.environ.get("RAG_BASE_URL", "http://127.0.0.1:8005")


def query_rag(query: str, top_k: int = 5) -> dict[str, Any]:
    """
    POST /rag/query → { answer, sources, context_used, retrieved_chunks }
    Returns empty dict if RAG service is unavailable.
    """
    try:
        import httpx
    except ImportError:
        logger.warning("httpx not installed; RAG queries disabled")
        return {}

    url = f"{RAG_BASE_URL.rstrip('/')}/rag/query"
    payload = {"query": query, "top_k": top_k}

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.warning("RAG query failed: %s", e)
        return {}


async def query_rag_async(query: str, top_k: int = 5) -> dict[str, Any]:
    """Async variant for background enrichment tasks."""
    try:
        import httpx
    except ImportError:
        return {}

    url = f"{RAG_BASE_URL.rstrip('/')}/rag/query"
    payload = {"query": query, "top_k": top_k}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.warning("RAG async query failed: %s", e)
        return {}


def species_context_query(species_code: str, common_name: str) -> str:
    return (
        f"Provide habitat, altitude range, conservation status, and ecological "
        f"importance of {common_name} ({species_code.replace('_', ' ')}) in Nepal forests."
    )
