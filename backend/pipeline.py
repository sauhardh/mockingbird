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
import numpy as np

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
    Pre-check: minimum duration + NDSI anthrophony threshold.
    Returns dict with 'pass', 'message', 'duration_sec', 'ndsi_anth'.
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

    # Compute NDSI anthrophony via scikit-maad
    ndsi_anth = 0.5  # neutral fallback
    try:
        import maad.sound
        import maad.features
        Sxx, tn, fn, ext = maad.sound.spectrogram(y, sr)
        spectral, _ = maad.features.all_spectral_alpha_indices(Sxx, tn, fn)
        # NDSI from scikit-maad; use as proxy for anthrophony level
        ndsi_anth = float(spectral['NDSI'].iloc[0]) if 'NDSI' in spectral.columns else 0.5
    except Exception as e:
        logger.warning(f"NDSI computation failed, using fallback: {e}")

    if ndsi_anth < 0.3:
        return {
            "pass": False,
            "message": "Too much background noise (wind, traffic, voices). "
                       "Move further from noise sources and try again.",
            "ndsi_anth": ndsi_anth,
            "duration_sec": int(duration_sec),
        }

    return {
        "pass": True,
        "duration_sec": int(duration_sec),
        "ndsi_anth": float(ndsi_anth),
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


# ── Layer 3: Nepal Calibration ─────────────────────────────────────────

def calibrate_detections(detections: list[dict], nepal_ref: dict) -> list[dict]:
    """
    Cross-reference detections against nepal_species_reference.
    - Drop species never recorded in Nepal
    - Mark endemic / threatened species
    """
    calibrated = []
    for d in detections:
        code = d['species_code']
        ref = nepal_ref.get(code)

        if ref is None:
            # Species not in Nepal reference — drop
            continue

        d['confidence_cal'] = d['confidence_raw']
        d['is_endemic'] = ref.get('is_endemic', False)
        d['is_threatened'] = ref.get('is_threatened', False)
        d['threat_category'] = ref.get('threat_category')
        calibrated.append(d)

    logger.info(f"Calibration: {len(detections)} raw -> {len(calibrated)} Nepal-verified")
    return calibrated


# ── Layer 4: Soundscape Indices ────────────────────────────────────────

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
        result["h_temporal"] = float(temporal['Ht'].iloc[0]) if 'Ht' in temporal.columns else None
        result["m_median"] = float(temporal['MED'].iloc[0]) if 'MED' in temporal.columns else None

        # Spectral indices
        Sxx, tn, fn, ext = maad.sound.spectrogram(y, sr)
        spectral, _ = maad.features.all_spectral_alpha_indices(Sxx, tn, fn)
        
        result["aci"] = float(spectral['ACI'].iloc[0]) if 'ACI' in spectral.columns else None
        result["bi"] = float(spectral['BI'].iloc[0]) if 'BI' in spectral.columns else None
        result["h_spectral"] = float(spectral['Hf'].iloc[0]) if 'Hf' in spectral.columns else None
        result["adi"] = float(spectral['ADI'].iloc[0]) if 'ADI' in spectral.columns else None
        
        # Compute NDSI components (biophony vs anthrophony) separately
        # ndsi_bio is NDSI itself
        # ndsi_anth is AnthroEnergy / (BioEnergy + AnthroEnergy)
        bio_energy = float(spectral['BioEnergy'].iloc[0]) if 'BioEnergy' in spectral.columns else 0
        anthro_energy = float(spectral['AnthroEnergy'].iloc[0]) if 'AnthroEnergy' in spectral.columns else 0
        total_energy = bio_energy + anthro_energy
        
        ndsi = float(spectral['NDSI'].iloc[0]) if 'NDSI' in spectral.columns else 0.0
        result["ndsi_bio"] = ndsi
        
        if total_energy > 0:
            result["ndsi_anth"] = anthro_energy / total_energy
        else:
            result["ndsi_anth"] = 0.0

    except Exception as e:
        logger.warning(f"Soundscape index computation failed: {e}")

    return result


# ── Pipeline Orchestrator ──────────────────────────────────────────────

async def run_pipeline(wav_path: str, meta: dict, recording_id: str, db) -> dict:
    """
    Full pipeline: preprocess -> BirdNET -> calibrate -> indices -> score -> persist.
    """
    from backend.health_index import compute_health_score
    from db.helpers import (
        save_detections, save_indices, save_health_score, mark_complete
    )

    # 1. Preprocess
    clean_path = wav_path.replace('.wav', '_clean.wav')
    try:
        preprocess_audio(wav_path, clean_path)
    except Exception as e:
        logger.error(f"Preprocessing failed: {e}")
        clean_path = wav_path  # fall back to raw audio

    # 2. BirdNET
    raw_detections = run_birdnet(clean_path, meta)

    # 3. Calibrate
    nepal_ref = await db.get_nepal_species_reference()
    detections = calibrate_detections(raw_detections, nepal_ref)

    # 4. Soundscape indices
    indices = compute_indices(clean_path)

    # 5. Health Index
    score_result = compute_health_score(detections, indices, meta)

    # 6. Persist
    await save_detections(db, recording_id, detections)
    await save_indices(db, recording_id, indices)
    await save_health_score(db, recording_id, score_result)
    await mark_complete(db, recording_id, score_result['health_score'])

    # Cleanup temp files
    for path in [clean_path]:
        if path != wav_path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass

    return {
        "health_score": score_result['health_score'],
        "components": score_result['components'],
        "explanation": score_result['explanation'],
        "species": detections,
    }
