"""
MokingBird — FastAPI Backend
Main application with routes for recording upload, map pins, and recording detail.
"""

import json
import uuid
import os
import tempfile
import logging
import asyncio
from functools import lru_cache

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

import asyncpg

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="    [%(levelname)s]: %(name)s -> %(message)s"
)

# ── Database connection ────────────────────────────────────────────────

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres@localhost/mockingbird"
)

_db_pool = None


async def get_db():
    return _db_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle for DB pool and BirdNET model."""
    global _db_pool
    logger.info("Connecting to database...")
    _db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    logger.info("Database pool created.")

    # Pre-load BirdNET model at startup (lazy load on first request if this fails)
    try:
        from backend.pipeline import _get_birdnet_model
        _get_birdnet_model()
    except Exception as e:
        logger.warning(f"BirdNET pre-load skipped (will load on first request): {e}")

    yield

    # Shutdown
    if _db_pool:
        await _db_pool.close()
        logger.info("Database pool closed.")


# ── App ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="MokingBird API",
    description="Citizen-science forest health monitoring via audio analysis",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── RAG proxy models (no changes to RAG service itself) ─────────────────

class RagQueryRequest(BaseModel):
    query: str
    top_k: int = 5


RAG_BASE_URL = os.environ.get("RAG_BASE_URL", "http://127.0.0.1:8005")


# ── Routes ─────────────────────────────────────────────────────────────

@app.get("/")
async def health_check():
    return {"status": "healthy", "service": "MokingBird API"}


@app.post("/recordings/upload")
async def upload_recording(
    audio: UploadFile = File(...),
    metadata: str = Form(
        ...,
        description='JSON string, e.g. {"lat":27.7172,"lon":85.3240,"altitude_m":1400,"recorded_at":"2026-05-24T08:00:00Z","user_id":"00000000-0000-0000-0000-000000000000"}',
        json_schema_extra={
            "example": '{"lat": 27.7172, "lon": 85.3240, "altitude_m": 1400, "recorded_at": "2026-05-24T08:00:00Z", "user_id": "00000000-0000-0000-0000-000000000000"}',
        },
    ),
):
    """
    Upload a WAV recording + GPS metadata.
    Runs the full ML pipeline and returns the health score.

    Body: multipart/form-data
      - audio: WAV file
      - metadata: JSON string { lat, lon, altitude_m, recorded_at, user_id }

    Response 200: { recording_id, health_score, components, explanation, species }
    Response 422: { error: "low_quality", message: "..." }
    """
    # Parse metadata
    try:
        meta = json.loads(metadata)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400,
            detail='Invalid metadata JSON. Required format: {"lat": 27.7, "lon": 85.3, "altitude_m": 1400, "recorded_at": "2026-05-24T08:00:00Z"}',
        )

    # Validate required fields
    required = ['lat', 'lon', 'altitude_m', 'recorded_at']
    for field in required:
        if field not in meta:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

    # Save WAV to temp file
    suffix = ".wav"
    if audio.filename and audio.filename.lower().endswith('.mp3'):
        suffix = ".mp3"

    tmp_dir = os.path.join(tempfile.gettempdir(), "mockingbird")
    os.makedirs(tmp_dir, exist_ok=True)
    tmp_path = os.path.join(tmp_dir, f"{uuid.uuid4()}{suffix}")

    try:
        content = await audio.read()
        with open(tmp_path, "wb") as f:
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save audio: {e}")

    # Layer 0: Quality gate
    from backend.pipeline import quality_gate
    quality = quality_gate(tmp_path)

    if not quality['pass']:
        # Clean up temp file
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        return JSONResponse(
            status_code=422,
            content={
                "error": "low_quality",
                "message": quality['message'],
            }
        )

    # Insert recording stub into DB
    from db.helpers import insert_recording
    pool = await get_db()
    async with pool.acquire() as conn:
        recording_id = await insert_recording(conn, {
            **meta,
            "file_path": tmp_path,
            "duration_sec": quality['duration_sec'],
        })

    # Run full pipeline
    from backend.pipeline import run_pipeline
    from db import helpers as db_helpers

    # Create a DB-like wrapper that uses the pool
    class DBWrapper:
        def __init__(self, pool):
            self._pool = pool

        async def get_nepal_species_reference(self):
            async with self._pool.acquire() as conn:
                return await db_helpers.get_nepal_species_reference(conn)

    db = DBWrapper(pool)

    # Patch the helpers module temporarily for this request
    import db.helpers as _h
    orig_save_det = _h.save_detections
    orig_save_idx = _h.save_indices
    orig_save_hs = _h.save_health_score
    orig_mark = _h.mark_complete

    # Monkey-patch save functions to use pool, calling original functions!
    async def _save_detections(db_obj, rec_id, detections):
        async with pool.acquire() as conn:
            await orig_save_det(conn, rec_id, detections)

    async def _save_indices(db_obj, rec_id, indices):
        async with pool.acquire() as conn:
            await orig_save_idx(conn, rec_id, indices)

    async def _save_health_score(db_obj, rec_id, score_result):
        async with pool.acquire() as conn:
            await orig_save_hs(conn, rec_id, score_result)

    async def _mark_complete(db_obj, rec_id, health_score, extra=None):
        async with pool.acquire() as conn:
            await orig_mark(conn, rec_id, health_score, extra=extra)

    _h.save_detections = lambda conn, rid, d: _save_detections(None, rid, d)
    _h.save_indices = lambda conn, rid, i: _save_indices(None, rid, i)
    _h.save_health_score = lambda conn, rid, s: _save_health_score(None, rid, s)
    _h.mark_complete = lambda conn, rid, s, extra=None: _mark_complete(None, rid, s, extra)

    try:
        result = await run_pipeline(tmp_path, meta, recording_id, db)
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        # Mark as failed
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE recordings SET processing_status = 'failed' WHERE id = $1",
                uuid.UUID(recording_id)
            )
        raise HTTPException(status_code=500, detail=f"Processing failed: {e}")
    finally:
        # Restore original functions
        _h.save_detections = orig_save_det
        _h.save_indices = orig_save_idx
        _h.save_health_score = orig_save_hs
        _h.mark_complete = orig_mark

        # Cleanup temp file
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass

    # Async RAG enrichment — never blocks response
    from backend.enrichment import enrich_species
    asyncio.create_task(enrich_species(recording_id, result.get("species", []), pool))

    return {
        "recording_id": recording_id,
        "health_score": result["health_score"],
        "confidence_interval": result.get("confidence_interval"),
        "health_category": result.get("health_category"),
        "model_version": result.get("model_version"),
        "components": result["components"],
        "explanation": result["explanation"],
        "species": result["species"],
    }


@app.post("/rag/query")
async def rag_query_proxy(req: RagQueryRequest):
    """Proxy to RAG service — POST /rag/query on port 8005."""
    from feature_builder.rag_client import query_rag_async
    result = await query_rag_async(req.query, req.top_k)
    if not result:
        raise HTTPException(status_code=503, detail="RAG service unavailable at " + RAG_BASE_URL)
    return result


@lru_cache(maxsize=500)
def _cached_species_context(species_code: str, common_name: str) -> str:
    from feature_builder.rag_client import query_rag, species_context_query
    q = species_context_query(species_code, common_name)
    result = query_rag(q, top_k=3)
    return json.dumps(result) if result else "{}"


@app.get("/species/{species_code}/context")
async def get_species_context(species_code: str, common_name: str = Query(default="")):
    """Species habitat/conservation context via RAG query (cached)."""
    name = common_name or species_code.replace("_", " ")
    raw = _cached_species_context(species_code, name)
    data = json.loads(raw)
    if not data:
        pool = await get_db()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT common_name, is_endemic, is_threatened, threat_category, "
                "altitude_min_m, altitude_max_m FROM nepal_species_reference WHERE species_code = $1",
                species_code,
            )
        if row:
            return {
                "species_code": species_code,
                "common_name": row["common_name"],
                "is_endemic": row["is_endemic"],
                "is_threatened": row["is_threatened"],
                "threat_category": row["threat_category"],
                "altitude_min_m": row["altitude_min_m"],
                "altitude_max_m": row["altitude_max_m"],
                "source": "database",
            }
        raise HTTPException(status_code=404, detail="Species not found")
    return {"species_code": species_code, "common_name": name, "rag": data, "source": "rag"}


@app.get("/recordings/{recording_id}/enrichment")
async def get_recording_enrichment(recording_id: str):
    """Poll async RAG enrichment results for a recording."""
    from db.helpers import get_species_enrichment
    pool = await get_db()
    try:
        rec_uuid = uuid.UUID(recording_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid recording ID")

    async with pool.acquire() as conn:
        rows = await get_species_enrichment(conn, recording_id)
    return {"recording_id": recording_id, "enrichment": rows, "ready": len(rows) > 0}


@app.get("/map/pins")
async def get_map_pins():
    """
    Returns all quality-passed recordings for the national map.
    Response: { pins: [{ id, latitude, longitude, health_score, has_endemic }] }
    """
    from db.helpers import get_map_pins
    pool = await get_db()
    async with pool.acquire() as conn:
        pins = await get_map_pins(conn)
    return {"pins": pins}


@app.get("/recordings/{recording_id}")
async def get_recording_detail(recording_id: str):
    """
    Returns full detail for one recording including species list and breakdown.
    """
    pool = await get_db()
    async with pool.acquire() as conn:
        try:
            rec_uuid = uuid.UUID(recording_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid recording ID")

        # Get recording
        recording = await conn.fetchrow(
            "SELECT * FROM recordings WHERE id = $1", rec_uuid
        )
        if not recording:
            raise HTTPException(status_code=404, detail="Recording not found")

        # Get species detections
        detections = await conn.fetch(
            "SELECT * FROM species_detections WHERE recording_id = $1 ORDER BY confidence_raw DESC",
            rec_uuid
        )

        # Get soundscape indices
        indices = await conn.fetchrow(
            "SELECT * FROM soundscape_indices WHERE recording_id = $1",
            rec_uuid
        )

        # Get health score components
        components = await conn.fetchrow(
            "SELECT * FROM health_score_components WHERE recording_id = $1",
            rec_uuid
        )

    return {
        "recording": {
            "id": str(recording['id']),
            "latitude": recording['latitude'],
            "longitude": recording['longitude'],
            "altitude_m": recording['altitude_m'],
            "altitude_zone": recording['altitude_zone'],
            "duration_sec": recording['duration_sec'],
            "recorded_at": recording['recorded_at'].isoformat() if recording['recorded_at'] else None,
            "health_score": recording['health_score'],
            "processing_status": recording['processing_status'],
            "model_version": recording["model_version"] if "model_version" in recording else None,
            "confidence_margin": recording["confidence_margin"] if "confidence_margin" in recording else None,
        },
        "species": [
            {
                "species_code": d['species_code'],
                "common_name": d['common_name'],
                "scientific_name": d['scientific_name'],
                "confidence_raw": d['confidence_raw'],
                "confidence_cal": d['confidence_cal'],
                "start_sec": d['start_sec'],
                "end_sec": d['end_sec'],
                "is_endemic": d['is_endemic'],
                "is_threatened": d['is_threatened'],
                "threat_category": d['threat_category'],
            }
            for d in detections
        ],
        "indices": {
            "aci": indices['aci'] if indices else None,
            "bi": indices['bi'] if indices else None,
            "ndsi_bio": indices['ndsi_bio'] if indices else None,
            "ndsi_anth": indices['ndsi_anth'] if indices else None,
            "h_temporal": indices['h_temporal'] if indices else None,
            "h_spectral": indices['h_spectral'] if indices else None,
            "m_median": indices['m_median'] if indices else None,
        } if indices else None,
        "components": {
            "species_score": components['species_score'] if components else None,
            "aci_score": components['aci_score'] if components else None,
            "ndsi_score": components['ndsi_score'] if components else None,
            "disturbance_score": components['disturbance_pen'] if components else None,
            "seasonal_score": components['seasonal_adj'] if components else None,
            "endemic_bonus": components['endemic_bonus'] if components else None,
            "disturbance_penalty": components['disturbance_pen'] if components else None,
            "explanation": json.loads(components['explanation']) if components and components['explanation'] else None,
        } if components else None,
    }
