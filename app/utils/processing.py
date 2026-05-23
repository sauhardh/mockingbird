from collections import defaultdict

"""
species:
[
[ "/tmp/tmp1dyb0aq_.mp3", 0, 3, "Lophophorus impejanus_Himalayan Monal", 0.8378916382789612 ],
[ "/tmp/tmp1dyb0aq_.mp3", 0, 3, "Numenius arquata_Eurasian Curlew", 0.4291985034942627 ]
[ "/tmp/tmp1dyb0aq_.mp3", 4, 5, "Lophophorus impejanus_Himalayan Monal", 0.7378916382789612 ],
[ "audio_path", "start_time", "end_time", "species_label","confidence"],
]
"""


def preprocess_species(predictions: list, threshold=0.6):
    filtered = []

    for row in predictions:
        (audio_path, start_time, end_time, species_label, confidence) = row

        if confidence < threshold:
            continue

        (scientic_name, common_name) = (
            species_label.split("_", 1)
            if "_" in species_label
            else (species_label, species_label)
        )

        filtered.append(
            {
                "scientific_name": scientic_name,
                "common_name": common_name,
                "confidence": confidence,
                "start_time": start_time,
                "end_time": end_time,
                "audio_path": audio_path,
            }
        )

    return filtered


def merge_species(predictions: list):
    species_map = defaultdict(list)

    for pred in predictions:
        species_id = pred["scientic_name"]
        species_map[species_id].append(pred)

    merged = []

    for species_id, detections in species_map.items():
        count = len(detections)

        avg_confidence = sum(d["confidence"] for d in detections) / count

        merged.append(
            {
                "scientific_name": species_id,
                "common_name": detections[0]["common_name"],
                "count": count,
                "avg_confidence": round(avg_confidence, 3),
                "timestamps": [
                    {
                        "start": d["start_time"],
                        "end": d["end_time"],
                    }
                    for d in detections
                ],
            }
        )

    return merged
