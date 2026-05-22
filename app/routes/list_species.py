from fastapi import UploadFile, File
import tempfile
import logging
from pathlib import Path

from app.utils import detect_species
from . import router


logger = logging.getLogger(__name__)


@router.post("/species")
async def species(audio: UploadFile = File(...)):
    audio_data = await audio.read()

    extension = Path(audio.filename).suffix if audio.filename else ".MP3"
    logger.info("Audio has extension %s", extension)

    # create temp File
    temp_path = None
    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=extension,
    ) as temp_audio:
        temp_audio.write(audio_data)
        temp_path = temp_audio.name

    logger.info(f"Audio is stored in {temp_path} temporarily")

    try:
        species_data = detect_species(temp_path)
    except Exception as e:
        logger.error("Failed to detect species %s", e)
        return {"status": "failed", "data": e}

    return {"status": "success", "data": species_data}
    # TODO: CLEANUP tempfile
