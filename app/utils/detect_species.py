from pathlib import Path
import birdnet


def detect_species(audio_path: str | Path):
    if isinstance(audio_path, str):
        audio_path = Path(audio_path)

    model = birdnet.load("acoustic", "2.4", "tf")
    predictions = model.predict(audio_path)

    structured = predictions.to_structured_array()
    return structured.tolist()
