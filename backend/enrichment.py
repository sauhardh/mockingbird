"""Async species enrichment via RAG HTTP query — never blocks scoring."""

import logging
from feature_builder.rag_client import query_rag_async, species_context_query
from db.helpers import save_species_enrichment

logger = logging.getLogger(__name__)


async def enrich_species(recording_id: str, species_list: list[dict], pool) -> None:
    """Fire-and-forget: query RAG for each species and store results."""
    if not species_list:
        return

    async with pool.acquire() as conn:
        for sp in species_list:
            code = sp.get("species_code", "")
            common = sp.get("common_name", code)
            query = species_context_query(code, common)
            try:
                result = await query_rag_async(query, top_k=3)
                if result:
                    await save_species_enrichment(conn, recording_id, code, result)
            except Exception as e:
                logger.warning("Enrichment failed for %s: %s", code, e)
