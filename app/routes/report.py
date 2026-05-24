from fastapi import APIRouter
from pydantic import BaseModel
import logging
import ollama

from app.utils.rag import retrieve_context
from . import router

logger = logging.getLogger(__name__)

LLM_MODEL = "huihui_ai/qwen2.5-abliterate:7b"

PROMPT_TEMPLATE = """You are an ecological analysis assistant specializing in bird biodiversity and forest ecosystem health.

USER:

Location: {location}

Observed Species:
{species_list}

Computed Ecological Metrics:
* Unique Species: {unique_species}
* Shannon Diversity Index: {shannon_idx}
* Dominance Score: {dominance_score}
* Native Species Ratio: {native_ratio}%
* Average Forest Dependency: {forest_dependency}
* Average Rarity: {rarity_score}
* Forest Health Index: {forest_health_index}

Retrieved Ecological Knowledge:
{retrieved_chunks}

Task:
1. Explain the ecological condition of this environment.
2. Interpret whether biodiversity appears healthy.
3. Explain what the dominance of certain species implies.
4. Mention ecological concerns if present.
5. Explain how native ratio and forest dependency affect ecosystem health.
6. Keep the explanation scientifically grounded and concise."""

class DominanceInfo(BaseModel):
    dominance_score: float
    dominant_species: str | None

class ReportRequest(BaseModel):
    loc: str = ""
    unique_species: int
    shannon_idx: float
    dominance: DominanceInfo
    norm_unique: float
    norm_shannon: float
    norm_dominance: float
    native_ratio: float
    forest_dependency: float
    rarity_score: float
    forest_health_index: float
    species_list: list[str]          # filtered (confidence >= 0.6) — used for metrics
    all_species_list: list[str] = [] # all detected species — used for RAG

@router.post("/report")
async def generate_report(req: ReportRequest):
    # 1. Retrieve Context via RAG
    # Use all detected species (pre-filter) for richer context, fall back to filtered list
    rag_species = req.all_species_list if req.all_species_list else req.species_list
    retrieved_chunks = retrieve_context(rag_species, req.loc)

    # 2. Construct Prompt
    species_list_str = "\n".join([f"* {name}" for name in req.species_list])
    native_ratio_pct = round(req.native_ratio * 100, 1)

    prompt = PROMPT_TEMPLATE.format(
        location=req.loc,
        species_list=species_list_str,
        unique_species=req.unique_species,
        shannon_idx=req.shannon_idx,
        dominance_score=req.dominance.dominance_score,
        native_ratio=native_ratio_pct,
        forest_dependency=req.forest_dependency,
        rarity_score=req.rarity_score,
        forest_health_index=req.forest_health_index,
        retrieved_chunks=retrieved_chunks
    )

    # 3. Call local Ollama
    try:
        response = ollama.chat(model=LLM_MODEL, messages=[
            {
                'role': 'user',
                'content': prompt
            }
        ])
        report = response['message']['content']
    except Exception as e:
        logger.exception("Failed to generate report with Ollama")
        report = f"LLM Generation failed: {str(e)}"

    return {
        "status": "success",
        "prompt_sent_to_llm": prompt,
        "report": report
    }

