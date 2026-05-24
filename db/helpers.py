import uuid
from datetime import datetime
import json

def classify_altitude(altitude_m: float) -> str:
    if altitude_m < 500:
        return 'terai'
    elif altitude_m < 2000:
        return 'hills'
    elif altitude_m < 3500:
        return 'subalpine'
    else:
        return 'himalayan'

async def insert_recording(db, payload: dict) -> str:
    zone = classify_altitude(payload['altitude_m'])
    recorded_at = payload['recorded_at']
    if isinstance(recorded_at, str):
        recorded_at = datetime.fromisoformat(recorded_at.replace('Z', '+00:00'))
    
    user_id = payload.get('user_id')
    if isinstance(user_id, str):
        user_id = uuid.UUID(user_id)
    elif user_id is None:
        # Default fallback user
        user_id = uuid.UUID('00000000-0000-0000-0000-000000000000')
    
    query = """
        INSERT INTO recordings (user_id, latitude, longitude, altitude_m,
          altitude_zone, duration_sec, file_path, recorded_at, processing_status)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'pending')
        RETURNING id
    """
    rec_id = await db.fetchval(
        query,
        user_id,
        float(payload['lat']),
        float(payload['lon']),
        float(payload['altitude_m']),
        zone,
        int(payload['duration_sec']),
        payload['file_path'],
        recorded_at
    )
    return str(rec_id)

async def save_detections(db, recording_id: str, detections: list[dict]):
    rec_uuid = uuid.UUID(recording_id) if isinstance(recording_id, str) else recording_id
    query = """
        INSERT INTO species_detections (
            recording_id, species_code, common_name, scientific_name,
            confidence_raw, confidence_cal, start_sec, end_sec,
            is_endemic, is_threatened, threat_category
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
    """
    for d in detections:
        await db.execute(
            query,
            rec_uuid,
            d['species_code'],
            d['common_name'],
            d['scientific_name'],
            float(d['confidence_raw']),
            float(d.get('confidence_cal', d['confidence_raw'])),
            float(d['start_sec']),
            float(d['end_sec']),
            bool(d.get('is_endemic', False)),
            bool(d.get('is_threatened', False)),
            d.get('threat_category')
        )

async def save_indices(db, recording_id: str, indices: dict):
    rec_uuid = uuid.UUID(recording_id) if isinstance(recording_id, str) else recording_id
    query = """
        INSERT INTO soundscape_indices (
            recording_id, aci, bi, ndsi_bio, ndsi_anth, h_temporal, h_spectral, m_median, adi
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
    """
    await db.execute(
        query,
        rec_uuid,
        indices.get('aci'),
        indices.get('bi'),
        indices.get('ndsi_bio'),
        indices.get('ndsi_anth'),
        indices.get('h_temporal'),
        indices.get('h_spectral'),
        indices.get('m_median'),
        indices.get('adi')
    )

async def save_health_score(db, recording_id: str, score_result: dict):
    rec_uuid = uuid.UUID(recording_id) if isinstance(recording_id, str) else recording_id
    comp = score_result['components']
    explanation_json = json.dumps(score_result['explanation'])
    
    query = """
        INSERT INTO health_score_components (
            recording_id, species_score, endemic_bonus, aci_score, ndsi_score,
            disturbance_pen, seasonal_adj, w_species, w_aci, w_ndsi,
            w_disturbance, w_seasonal, explanation
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
    """
    await db.execute(
        query,
        rec_uuid,
        int(comp['species_score']),
        int(comp['endemic_bonus']),
        int(comp['aci_score']),
        int(comp['ndsi_score']),
        int(comp['disturbance_penalty']),
        int(comp['seasonal_score']),
        0.35, 0.25, 0.20, 0.15, 0.05,
        explanation_json
    )

async def mark_complete(db, recording_id: str, health_score: int):
    rec_uuid = uuid.UUID(recording_id) if isinstance(recording_id, str) else recording_id
    await db.execute("""
        UPDATE recordings
        SET health_score = $1, processing_status = 'complete', quality_pass = TRUE
        WHERE id = $2
    """, int(health_score), rec_uuid)

async def get_map_pins(db) -> list[dict]:
    query = """
        SELECT
          r.id, r.latitude, r.longitude, r.health_score,
          EXISTS (
            SELECT 1 FROM species_detections sd
            WHERE sd.recording_id = r.id AND sd.is_endemic = TRUE
          ) AS has_endemic
        FROM recordings r
        WHERE r.quality_pass = TRUE
          AND r.health_score IS NOT NULL
        ORDER BY r.created_at DESC
        LIMIT 500;
    """
    rows = await db.fetch(query)
    return [
        {
            "id": str(row['id']),
            "latitude": row['latitude'],
            "longitude": row['longitude'],
            "health_score": row['health_score'],
            "has_endemic": row['has_endemic']
        }
        for row in rows
    ]

async def get_nepal_species_reference(db) -> dict:
    query = """
        SELECT species_code, common_name, scientific_name, is_endemic,
               is_threatened, threat_category, altitude_min_m, altitude_max_m, season_present
          FROM nepal_species_reference
    """
    rows = await db.fetch(query)
    ref = {}
    for r in rows:
        ref[r['species_code']] = {
            "species_code": r['species_code'],
            "common_name": r['common_name'],
            "scientific_name": r['scientific_name'],
            "is_endemic": r['is_endemic'],
            "is_threatened": r['is_threatened'],
            "threat_category": r['threat_category'],
            "altitude_min_m": r['altitude_min_m'],
            "altitude_max_m": r['altitude_max_m'],
            "season_present": r['season_present']
        }
    return ref
