"""
MokingBird — ML Pipeline
4-layer audio intelligence pipeline running on CPU.

Layer 0: Quality Gate (NDSI anthrophony pre-check)
Layer 1: Audio Preprocessing (noise reduction + bandpass)
Layer 2: BirdNET Inference (species identification + altitude filter)
Layer 3: Nepal Calibration (cross-reference nepal_species_reference)
Layer 4: Soundscape Indices (ACI, BI, NDSI, H, M via scikit-maad)
"""

import os
import logging
import math
import numpy as np
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Lazy-loaded globals ────────────────────────────────────────────────

_birdnet_model = None


def _get_birdnet_model():
    """Load BirdNET model once (lazy singleton)."""
    global _birdnet_model
    if _birdnet_model is None:
        import birdnet
        logger.info("Loading BirdNET acoustic model v2.4 ...")
        _birdnet_model = birdnet.load("acoustic", "2.4", "tf")
        logger.info("BirdNET model loaded.")
    return _birdnet_model


# ── Altitude zone helpers ──────────────────────────────────────────────

ALTITUDE_ZONES = {
    'terai':     (0,    500),
    'hills':     (500,  2000),
    'subalpine': (2000, 3500),
    'himalayan': (3500, 9000),
}


def classify_altitude(altitude_m: float) -> str:
    if altitude_m < 500:
        return 'terai'
    elif altitude_m < 2000:
        return 'hills'
    elif altitude_m < 3500:
        return 'subalpine'
    else:
        return 'himalayan'


# ── Layer 0: Quality Gate ──────────────────────────────────────────────

def quality_gate(wav_path: str) -> dict:
    """
    Pre-check: minimum duration + anthrophony threshold.
    Uses anthro_energy ratio (not NDSI biophony) — long sparse bird recordings
    can have low average NDSI but still be valid field audio.
    Returns dict with 'pass', 'message', 'duration_sec', 'ndsi_anth', 'ndsi_bio'.
    """
    import librosa

    try:
        y, sr = librosa.load(wav_path, sr=None, mono=True)
    except Exception as e:
        return {"pass": False, "message": f"Could not read audio file: {e}"}

    duration_sec = len(y) / sr

    if duration_sec < 3:
        return {
            "pass": False,
            "message": "Recording too short. Please record at least 3 seconds.",
            "duration_sec": int(duration_sec),
        }

    ndsi_bio = 0.0
    ndsi_anth = 0.5
    try:
        import maad.sound
        import maad.features
        Sxx, tn, fn, ext = maad.sound.spectrogram(y, sr)
        spectral, _ = maad.features.all_spectral_alpha_indices(Sxx, tn, fn)

        ndsi_bio = float(spectral["NDSI"].iloc[0]) if "NDSI" in spectral.columns else 0.0
        bio_energy = float(spectral["BioEnergy"].iloc[0]) if "BioEnergy" in spectral.columns else 0.0
        anthro_energy = float(spectral["AnthroEnergy"].iloc[0]) if "AnthroEnergy" in spectral.columns else 0.0
        total_energy = bio_energy + anthro_energy
        if total_energy > 0:
            ndsi_anth = anthro_energy / total_energy
        else:
            ndsi_anth = 0.5
    except Exception as e:
        logger.warning(f"NDSI computation failed, using fallback: {e}")

    # Reject when human/anthrophony dominates (high ndsi_anth), not when biophony is sparse
    ANTHRO_REJECT_THRESHOLD = 0.65
    if ndsi_anth > ANTHRO_REJECT_THRESHOLD:
        return {
            "pass": False,
            "message": "Too much background noise (wind, traffic, voices). "
                       "Move further from noise sources and try again.",
            "ndsi_anth": ndsi_anth,
            "ndsi_bio": ndsi_bio,
            "duration_sec": int(duration_sec),
        }

    return {
        "pass": True,
        "duration_sec": int(duration_sec),
        "ndsi_anth": float(ndsi_anth),
        "ndsi_bio": float(ndsi_bio),
    }


# ── Layer 1: Audio Preprocessing ──────────────────────────────────────

def preprocess_audio(wav_path: str, out_path: str) -> str:
    """
    Noise reduction + bandpass filter (150 Hz – 12 kHz).
    Returns path to cleaned WAV.
    """
    import librosa
    import soundfile as sf

    y, sr = librosa.load(wav_path, sr=None, mono=True)

    # Step 1: spectral noise subtraction
    try:
        import noisereduce as nr
        y_denoised = nr.reduce_noise(y=y, sr=sr, stationary=False)
    except Exception as e:
        logger.warning(f"Noise reduction failed, using raw audio: {e}")
        y_denoised = y

    # Step 2: bandpass filter 150 Hz – 12 kHz
    try:
        from scipy.signal import butter, sosfilt
        nyquist = sr / 2
        low = 150 / nyquist
        high = min(12000 / nyquist, 0.99)
        sos = butter(5, [low, high], btype='band', output='sos')
        y_filtered = sosfilt(sos, y_denoised)
    except Exception as e:
        logger.warning(f"Bandpass filter failed, using denoised audio: {e}")
        y_filtered = y_denoised

    # Clip to valid range
    y_filtered = np.clip(y_filtered, -1.0, 1.0)

    sf.write(out_path, y_filtered, sr)
    return out_path


# ── Layer 2: BirdNET Inference ─────────────────────────────────────────

def run_birdnet(wav_path: str, meta: dict) -> list[dict]:
    """
    Run BirdNET on a cleaned WAV file.
    Uses the `birdnet` Python package (not birdnetlib).
    """
    model = _get_birdnet_model()

    predictions = model.predict(
        wav_path,
        default_confidence_threshold=0.1,
        bandpass_fmin=150,
        bandpass_fmax=12000,
    )

    # Convert predictions to structured list
    detections = []
    try:
        structured = predictions.to_structured_array()
        for row in structured:
            # structured array fields: file_path, start_s, end_s, species_id, confidence
            if len(row) < 5:
                continue
            start_s = float(row[1])
            end_s = float(row[2])
            species_id = str(row[3])
            confidence = float(row[4])

            if '_' in species_id:
                sci_name, common_name = species_id.split('_', 1)
            else:
                sci_name = species_id
                common_name = species_id

            if confidence >= 0.25:  # low threshold, calibration handles the rest
                detections.append({
                    "species_code": sci_name.replace(' ', '_'),
                    "common_name": common_name,
                    "scientific_name": sci_name,
                    "confidence_raw": confidence,
                    "start_sec": start_s,
                    "end_sec": end_s,
                })
    except Exception as e:
        logger.warning(f"Failed to parse BirdNET predictions: {e}")
        # Fallback: try to_csv approach
        try:
            csv_data = predictions.to_csv()
            logger.info(f"BirdNET returned CSV data of length {len(csv_data) if csv_data else 0}")
        except Exception:
            pass

    logger.info(f"BirdNET detected {len(detections)} species (conf >= 0.25)")
    return detections


# ── Layer 3 helpers ────────────────────────────────────────────────────

def _parse_month(recorded_at) -> int | None:
    if recorded_at is None:
        return None
    try:
        if isinstance(recorded_at, str):
            return datetime.fromisoformat(recorded_at.replace("Z", "+00:00")).month
        return recorded_at.month
    except (ValueError, AttributeError):
        return None


def _month_in_season(month: int | None, season_present: list | None) -> bool:
    if month is None or not season_present:
        return True
    month_map = {
        12: "winter", 1: "winter", 2: "winter",
        3: "pre_monsoon", 4: "pre_monsoon", 5: "pre_monsoon",
        6: "monsoon", 7: "monsoon", 8: "monsoon", 9: "monsoon",
        10: "post_monsoon", 11: "post_monsoon",
    }
    bucket = month_map.get(month, "resident")
    normalized = {s.lower() for s in season_present}
    return bucket in normalized or "resident" in normalized or "all" in normalized


def _altitude_plausible(altitude_m: float, ref: dict) -> bool:
    alt_min = ref.get("altitude_min_m")
    alt_max = ref.get("altitude_max_m")
    if alt_min is None and alt_max is None:
        return True
    lo = float(alt_min if alt_min is not None else 0)
    hi = float(alt_max if alt_max is not None else 9000)
    return lo <= altitude_m <= hi


# ── Layer 3: Nepal Calibration ─────────────────────────────────────────

def calibrate_detections(
    detections: list[dict],
    nepal_ref: dict,
    altitude_m: float | None = None,
    recorded_at=None,
) -> list[dict]:
    """
    Cross-reference detections against nepal_species_reference.
    - Drop species never recorded in Nepal
    - Drop altitude-implausible species
    - Penalize confidence when season mismatch
    """
    month = _parse_month(recorded_at)
    calibrated = []
    dropped = {"not_in_ref": 0, "altitude": 0, "low_conf": 0}

    for d in detections:
        code = d["species_code"]
        ref = nepal_ref.get(code)

        if ref is None:
            dropped["not_in_ref"] += 1
            continue

        altitude_match = True
        if altitude_m is not None and not _altitude_plausible(altitude_m, ref):
            dropped["altitude"] += 1
            continue

        conf = float(d["confidence_raw"])
        season_ok = _month_in_season(month, ref.get("season_present"))
        if not season_ok:
            conf *= 0.85

        if conf < 0.25:
            dropped["low_conf"] += 1
            continue

        d = dict(d)
        d["confidence_cal"] = conf
        d["altitude_match"] = altitude_match
        d["is_endemic"] = ref.get("is_endemic", False)
        d["is_threatened"] = ref.get("is_threatened", False)
        d["threat_category"] = ref.get("threat_category")
        calibrated.append(d)

    logger.info(
        "Calibration: %d raw -> %d Nepal-verified (dropped ref=%d alt=%d conf=%d)",
        len(detections), len(calibrated),
        dropped["not_in_ref"], dropped["altitude"], dropped["low_conf"],
    )
    return calibrated


# ── Layer 4: Soundscape Indices ────────────────────────────────────────

def _clean_index(val):
    if val is None:
        return None
    try:
        f = float(val)
        return None if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return None


def compute_indices(wav_path: str) -> dict:
    """
    Compute bioacoustic indices using scikit-maad.
    Returns dict with aci, bi, ndsi_bio, ndsi_anth, h_temporal, h_spectral, m_median.
    """
    import librosa

    y, sr = librosa.load(wav_path, sr=None, mono=True)

    result = {
        "aci": None,
        "bi": None,
        "ndsi_bio": None,
        "ndsi_anth": None,
        "h_temporal": None,
        "h_spectral": None,
        "m_median": None,
        "adi": None,
    }

    try:
        import maad.sound
        import maad.features

        # Temporal indices
        temporal = maad.features.all_temporal_alpha_indices(y, sr)
        result["h_temporal"] = _clean_index(temporal['Ht'].iloc[0]) if 'Ht' in temporal.columns else None
        result["m_median"] = _clean_index(temporal['MED'].iloc[0]) if 'MED' in temporal.columns else None

        # Spectral indices
        Sxx, tn, fn, ext = maad.sound.spectrogram(y, sr)
        spectral, _ = maad.features.all_spectral_alpha_indices(Sxx, tn, fn)

        result["aci"] = _clean_index(spectral['ACI'].iloc[0]) if 'ACI' in spectral.columns else None
        result["bi"] = _clean_index(spectral['BI'].iloc[0]) if 'BI' in spectral.columns else None
        result["h_spectral"] = _clean_index(spectral['Hf'].iloc[0]) if 'Hf' in spectral.columns else None
        result["adi"] = _clean_index(spectral['ADI'].iloc[0]) if 'ADI' in spectral.columns else None

        # Compute NDSI components (biophony vs anthrophony) separately
        # ndsi_bio is NDSI itself
        # ndsi_anth is AnthroEnergy / (BioEnergy + AnthroEnergy)
        bio_energy = float(spectral['BioEnergy'].iloc[0]) if 'BioEnergy' in spectral.columns else 0
        anthro_energy = float(spectral['AnthroEnergy'].iloc[0]) if 'AnthroEnergy' in spectral.columns else 0
        total_energy = bio_energy + anthro_energy
        
        ndsi = _clean_index(spectral['NDSI'].iloc[0]) if 'NDSI' in spectral.columns else 0.0
        result["ndsi_bio"] = ndsi if ndsi is not None else 0.0
        
        if total_energy > 0:
            result["ndsi_anth"] = anthro_energy / total_energy
        else:
            result["ndsi_anth"] = 0.0

    except Exception as e:
        logger.warning(f"Soundscape index computation failed: {e}")

    return result


def process_audio(wav_path: str, meta: dict, nepal_ref: dict) -> dict:
    """
    Run Layers 1–4 and return flat dict for Feature Builder.
    Does not score or persist.
    """
    clean_path = wav_path.replace(".wav", "_clean.wav").replace(".mp3", "_clean.wav")
    if not clean_path.endswith("_clean.wav"):
        clean_path = wav_path + "_clean.wav"

    try:
        preprocess_audio(wav_path, clean_path)
    except Exception as e:
        logger.error("Preprocessing failed: %s", e)
        clean_path = wav_path

    raw_detections = run_birdnet(clean_path, meta)
    detections = calibrate_detections(
        raw_detections,
        nepal_ref,
        altitude_m=meta.get("altitude_m"),
        recorded_at=meta.get("recorded_at"),
    )
    indices = compute_indices(clean_path)

    if clean_path != wav_path and os.path.exists(clean_path):
        try:
            os.remove(clean_path)
        except OSError:
            pass

    enriched_meta = dict(meta)
    if "altitude_zone" not in enriched_meta and meta.get("altitude_m") is not None:
        enriched_meta["altitude_zone"] = classify_altitude(float(meta["altitude_m"]))

    return {
        "species": detections,
        "indices": indices,
        "meta": enriched_meta,
    }


# ── Pipeline Orchestrator ──────────────────────────────────────────────

async def run_pipeline(wav_path: str, meta: dict, recording_id: str, db) -> dict:
    """
    Full pipeline: process_audio -> feature_builder -> MLP score -> persist.
    """
    from feature_builder import build_features
    from MLP_PIPELINE.scoring_service import score, score_result_to_dict
    from db.helpers import (
        save_detections, save_indices, save_health_score, mark_complete
    )

    nepal_ref = await db.get_nepal_species_reference()
    pipeline_out = process_audio(wav_path, meta, nepal_ref)

    detections = pipeline_out["species"]
    indices = pipeline_out["indices"]
    enriched_meta = pipeline_out["meta"]

    features = build_features(pipeline_out, enriched_meta, nepal_ref)
    score_result = score(features, detections, indices, enriched_meta)
    score_dict = score_result_to_dict(score_result)

    await save_detections(db, recording_id, detections)
    await save_indices(db, recording_id, indices)
    await save_health_score(db, recording_id, score_dict)
    await mark_complete(db, recording_id, score_dict["health_score"], extra={
        "feature_vector": features.to_dict(),
        "feature_schema_v": features.schema_version,
        "model_version": score_dict["model_version"],
        "confidence_margin": score_dict["confidence_margin"],
    })

    return {
        **score_dict,
        "species": detections,
        "feature_vector": features.to_dict(),
    }
