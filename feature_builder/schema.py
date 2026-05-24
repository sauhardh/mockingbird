"""Feature schema definitions for NepalForestHealthNet v1."""

FEATURE_SCHEMA_V1 = "v1"

FEATURE_NAMES_V1 = [
    # Species (4)
    "species_count",
    "max_confidence",
    "endemic_count",
    "altitude_match_score",
    # Soundscape (6)
    "aci",
    "bi",
    "h_temporal",
    "m_median",
    "ndsi_bio",
    "ndsi_anth",
    # Context (5)
    "altitude_zone_encoded",
    "season_encoded",
    "month_sin",
    "month_cos",
    "gbif_match_score",
]

ALTITUDE_ZONE_ENCODING = {
    "terai": 0.0,
    "hills": 0.33,
    "subalpine": 0.66,
    "himalayan": 1.0,
}

SEASON_ENCODING = {
    "winter": 0.0,
    "pre_monsoon": 0.25,
    "monsoon": 0.5,
    "post_monsoon": 0.75,
    "resident": 1.0,
}
