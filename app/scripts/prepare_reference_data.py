import os
import json
import csv
import re

def _to_binomial(name: str) -> str:
    """Strip authorship — return only 'Genus species' from any scientific name."""
    parts = (name or "").strip().split()
    if len(parts) >= 2:
        return f"{parts[0]} {parts[1]}"
    return name.strip()
    
# Directory where reference data will live
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)

SCRIPT_DIR        = os.path.dirname(os.path.abspath(__file__))
NEPAL_SPECIES_CSV = os.path.join(SCRIPT_DIR, "Nepal-Species.csv")
IUCN_CACHE_PATH   = os.path.join(DATA_DIR, "iucn_cache.json")

# ── Fallback data (used only when IUCN cache is absent) ──────────────────────

INTRODUCED_BIRDS_FALLBACK = {
    "Acridotheres tristis",
    "Columba livia",
    "Corvus splendens",
    "Passer domesticus",
    "Psittacula eupatria",
    "Psittacula krameri",
}

FAMILY_HABITATS = {
    "pheasant":           ["forest", "shrubland"],
    "partridge":          ["forest", "shrubland"],
    "turkey":             ["forest", "woodland"],
    "grouse":             ["forest", "shrubland"],
    "duck":               ["wetland", "freshwater"],
    "goose":              ["wetland", "freshwater"],
    "swan":               ["wetland", "freshwater"],
    "grebe":              ["wetland", "freshwater"],
    "flamingo":           ["wetland", "saltwater"],
    "pigeon":             ["forest", "woodland", "agricultural", "urban"],
    "dove":               ["forest", "woodland", "agricultural", "urban"],
    "nightjar":           ["forest", "shrubland"],
    "treeswift":          ["forest", "woodland"],
    "swift":              ["aerial", "forest", "urban"],
    "cuckoo":             ["forest", "woodland", "shrubland"],
    "rail":               ["wetland", "freshwater"],
    "gallinule":          ["wetland", "freshwater"],
    "coot":               ["wetland", "freshwater"],
    "crane":              ["wetland", "grassland"],
    "bustard":            ["grassland", "savanna"],
    "stork":              ["wetland", "freshwater"],
    "ibis":               ["wetland", "freshwater"],
    "spoonbill":          ["wetland", "freshwater"],
    "bittern":            ["wetland", "freshwater"],
    "heron":              ["wetland", "freshwater"],
    "egret":              ["wetland", "freshwater"],
    "pelican":            ["wetland", "freshwater"],
    "cormorant":          ["wetland", "freshwater"],
    "darter":             ["wetland", "freshwater"],
    "thick-knee":         ["grassland", "shrubland"],
    "ibisbill":           ["stony riverbed", "freshwater"],
    "stilt":              ["wetland", "freshwater"],
    "avocet":             ["wetland", "freshwater"],
    "plover":             ["wetland", "grassland"],
    "lapwing":            ["wetland", "grassland"],
    "painted-snipe":      ["wetland", "freshwater"],
    "jacana":             ["wetland", "freshwater"],
    "sandpiper":          ["wetland", "freshwater"],
    "snipe":              ["wetland", "freshwater"],
    "phalarope":          ["wetland", "freshwater"],
    "buttonquail":        ["grassland", "shrubland"],
    "courser":            ["grassland", "desert"],
    "pratincole":         ["wetland", "grassland"],
    "gull":               ["wetland", "marine"],
    "tern":               ["wetland", "marine"],
    "skimmer":            ["wetland", "freshwater"],
    "barn-owl":           ["forest", "woodland", "urban"],
    "owl":                ["forest", "woodland", "shrubland"],
    "boobook":            ["forest", "woodland"],
    "owlet":              ["forest", "woodland"],
    "osprey":             ["wetland", "freshwater"],
    "kite":               ["forest", "woodland", "urban"],
    "honey-buzzard":      ["forest", "woodland"],
    "baza":               ["forest", "woodland"],
    "vulture":            ["grassland", "forest", "mountain"],
    "harrier":            ["grassland", "wetland"],
    "goshawk":            ["forest", "woodland"],
    "sparrowhawk":        ["forest", "woodland"],
    "eagle":              ["forest", "woodland", "mountain"],
    "hawk":               ["forest", "woodland"],
    "buzzard":            ["forest", "woodland", "grassland"],
    "trogon":             ["forest"],
    "hornbill":           ["forest", "woodland"],
    "hoopoe":             ["woodland", "pasture", "urban"],
    "bee-eater":          ["forest", "woodland", "shrubland"],
    "roller":             ["woodland", "savanna"],
    "dollarbird":         ["forest", "woodland"],
    "kingfisher":         ["wetland", "forest", "freshwater"],
    "barbet":             ["forest", "woodland"],
    "honeyguide":         ["forest", "woodland"],
    "woodpecker":         ["forest", "woodland"],
    "wryneck":            ["woodland", "shrubland"],
    "piculet":            ["forest", "woodland"],
    "flameback":          ["forest", "woodland"],
    "yellownape":         ["forest", "woodland"],
    "falconet":           ["forest", "woodland"],
    "kestrel":            ["grassland", "shrubland", "rocky"],
    "falcon":             ["forest", "woodland", "mountain", "grassland"],
    "hobby":              ["forest", "woodland"],
    "merlin":             ["grassland", "shrubland"],
    "hanging-parrot":     ["forest", "woodland"],
    "parakeet":           ["forest", "woodland", "agricultural", "urban"],
    "parrot":             ["forest", "woodland"],
    "pitta":              ["forest"],
    "broadbill":          ["forest"],
    "oriole":             ["forest", "woodland"],
    "shrike-babbler":     ["forest", "woodland"],
    "erpornis":           ["forest", "woodland"],
    "vireo":              ["forest", "woodland"],
    "minivet":            ["forest", "woodland"],
    "cuckooshrikes":      ["forest", "woodland"],
    "woodswallow":        ["woodland", "savanna"],
    "flycatcher-shrike":  ["forest", "woodland"],
    "woodshrike":         ["forest", "woodland"],
    "iora":               ["forest", "woodland", "shrubland"],
    "fantail":            ["forest", "woodland", "shrubland"],
    "drongo":             ["forest", "woodland", "agricultural"],
    "monarch":            ["forest", "woodland"],
    "paradise-flycatcher":["forest", "woodland"],
    "shrike":             ["shrubland", "grassland"],
    "treepie":            ["forest", "woodland", "agricultural"],
    "chough":             ["mountain", "grassland", "rocky"],
    "magpie":             ["forest", "woodland", "shrubland"],
    "jay":                ["forest", "woodland"],
    "nutcracker":         ["forest", "woodland"],
    "raven":              ["mountain", "grassland", "urban"],
    "crow":               ["urban", "agricultural", "forest"],
    "canary-flycatcher":  ["forest", "woodland"],
    "fairy-fantail":      ["forest", "woodland"],
    "tit":                ["forest", "woodland"],
    "chickadee":          ["forest", "woodland"],
    "lark":               ["grassland", "agricultural"],
    "cisticola":          ["grassland", "wetland"],
    "prinia":             ["grassland", "shrubland"],
    "tailorbird":         ["forest", "shrubland", "urban"],
    "warbler":            ["forest", "woodland", "shrubland"],
    "reed-warbler":       ["wetland", "reedbeds"],
    "cupwing":            ["forest", "shrubland"],
    "grassbird":          ["grassland", "wetland"],
    "martin":             ["aerial", "urban", "rocky"],
    "swallow":            ["aerial", "agricultural", "urban"],
    "bulbul":             ["forest", "woodland", "shrubland", "agricultural"],
    "tesia":              ["forest", "shrubland"],
    "bush-warbler":       ["forest", "shrubland"],
    "tit-warbler":        ["forest", "shrubland"],
    "whitethroat":        ["shrubland", "woodland"],
    "myzornis":           ["forest", "shrubland"],
    "fulvetta":           ["forest", "shrubland"],
    "babbler":            ["forest", "woodland", "shrubland"],
    "parrotbill":         ["bamboo", "shrubland"],
    "yuhina":             ["forest", "woodland"],
    "white-eye":          ["forest", "woodland", "shrubland"],
    "wren-babbler":       ["forest", "shrubland"],
    "scimitar-babbler":   ["forest", "woodland", "shrubland"],
    "tit-babbler":        ["forest", "shrubland"],
    "grass-babbler":      ["grassland", "shrubland"],
    "laughingthrush":     ["forest", "woodland", "shrubland"],
    "cutia":              ["forest"],
    "sibia":              ["forest", "woodland"],
    "mesia":              ["forest", "shrubland"],
    "leiothrix":          ["forest", "shrubland"],
}

CATEGORY_SCORE_FALLBACK = {
    "least concern":       0.2,
    "near threatened":     0.4,
    "vulnerable":          0.6,
    "endangered":          0.8,
    "critically endangered": 1.0,
    "extinct":             1.0,
    "data deficient":      0.0,
}

# ── IUCN cache loader ─────────────────────────────────────────────────────────

def load_iucn_cache() -> dict | None:
    if not os.path.exists(IUCN_CACHE_PATH):
        return None
    with open(IUCN_CACHE_PATH, encoding="utf-8") as f:
        data = json.load(f)
    print(f"[info] Loaded IUCN cache: {len(data)} species from {IUCN_CACHE_PATH}")
    return data


# ── Habitat helpers ───────────────────────────────────────────────────────────

def get_habitats_from_iucn(iucn_habitats: list[dict]) -> list[str]:
    """Extract habitat label strings from IUCN habitat list (skip Marginal)."""
    labels = sorted({
        h["habitat"] for h in iucn_habitats
        if h.get("habitat") and h.get("suitability") != "Marginal"
    })
    return labels if labels else ["forest"]


def get_habitats_fallback(common_name: str, family_name: str, scientific_name: str) -> list[str]:
    """Keyword-match fallback when no IUCN cache exists."""
    c_low = common_name.lower()
    f_low = family_name.lower()
    s_low = scientific_name.lower()
    matched: set[str] = set()
    for key, habitats in FAMILY_HABITATS.items():
        if key in c_low or key in f_low or key in s_low:
            matched.update(habitats)
    return sorted(matched) if matched else ["forest"]


# ── JSON builders ─────────────────────────────────────────────────────────────

def build_native_json(rows: list[dict], out_path: str) -> None:
    mapping: dict[str, set[str]] = {}
    for row in rows:
        country  = row.get("country_code")
        sci_name = row.get("scientific_name")
        if country and sci_name:
            mapping.setdefault(country, set()).add(sci_name)
    json_obj = {k: sorted(v) for k, v in mapping.items()}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(json_obj, f, ensure_ascii=False, indent=2)
    total = sum(len(v) for v in json_obj.values())
    print(f"[ok] Native species JSON written to {out_path} ({total} entries)")


def build_habitat_json(rows: list[dict], out_path: str) -> None:
    mapping: dict[str, set[str]] = {}
    for row in rows:
        sci_name = row.get("scientific_name")
        habitat  = row.get("habitat")
        if not sci_name or not habitat:
            continue
        for h in re.split(r"[;,]", habitat):
            h = h.strip()
            if h:
                mapping.setdefault(sci_name, set()).add(h)
    json_obj = {k: sorted(v) for k, v in mapping.items()}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(json_obj, f, ensure_ascii=False, indent=2)
    print(f"[ok] Habitat JSON written to {out_path} ({len(json_obj)} species)")


def build_rarity_json(rows: list[dict], out_path: str) -> None:
    mapping: dict[str, float] = {}
    unknown: list[str] = []
    for row in rows:
        sci_name = row.get("scientific_name")
        score    = row.get("score")
        if not sci_name:
            continue
        if score is None:
            unknown.append(sci_name)
            continue                     # omit — don't silently default to LC
        mapping[sci_name] = score
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
    print(f"[ok] Rarity JSON written to {out_path} ({len(mapping)} scored, {len(unknown)} omitted as unknown)")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    if not os.path.exists(NEPAL_SPECIES_CSV):
        print(f"[error] Nepal species CSV not found at {NEPAL_SPECIES_CSV}")
        return

    iucn = load_iucn_cache()
    using_iucn = iucn is not None

    if using_iucn:
        print("[info] Using IUCN Red List cache for native status, habitats, and rarity")
    else:
        print("[warn] IUCN cache not found — using CSV-based fallback logic")
        print("       Run build_iucn_data.py --token YOUR_TOKEN to improve accuracy")

    country_rows: list[dict] = []
    habitat_rows: list[dict] = []
    redlist_rows: list[dict] = []

    with open(NEPAL_SPECIES_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sci_name = (row.get("ScientificName") or "").strip()
            if not sci_name:
                continue
            sci_name_full = sci_name
            # Use binomial everywhere in generated JSONs
            sci_name = _to_binomial(sci_name)

            common_name = row.get("CommonName", "")
            family_name = row.get("FamilyName", "")

            iucn_entry = (
                (iucn or {}).get(sci_name_full)
                or (iucn or {}).get(sci_name, {})
            )

            # ── 1. Native / country distribution ────────────────────────────
            if using_iucn:
                native_countries     = iucn_entry.get("native_countries", [])
                introduced_countries = iucn_entry.get("introduced_countries", [])
                is_native = "NP" in native_countries and "NP" not in introduced_countries

                if not native_countries and not introduced_countries:
                    # IUCN has no range data — fall back to introduced-bird exclusion list
                    is_native = sci_name not in INTRODUCED_BIRDS_FALLBACK
            else:
                is_native = sci_name not in INTRODUCED_BIRDS_FALLBACK

            if is_native:
                country_rows.append({"country_code": "NP", "scientific_name": sci_name})

            # ── 2. Habitats ─────────────────────────────────────────────────
            if using_iucn and iucn_entry.get("habitats"):
                habs = get_habitats_from_iucn(iucn_entry["habitats"])
            else:
                habs = get_habitats_fallback(common_name, family_name, sci_name)

            habitat_rows.append({"scientific_name": sci_name, "habitat": ";".join(habs)})

            # ── 3. Rarity score ─────────────────────────────────────────────
            if using_iucn:
                cat = (iucn_entry.get("category") or "").upper()
                from build_iucn_data import CATEGORY_SCORE
                score = CATEGORY_SCORE.get(cat)
                # DD and NE → None (omitted from rarity_scores.json)
                if cat in ("DD", "NE", ""):
                    score = None
            else:
                raw_cat = (row.get("IUCNRedListCategory") or "").lower().strip()
                score = CATEGORY_SCORE_FALLBACK.get(raw_cat)  # None if blank/unknown

            redlist_rows.append({"scientific_name": sci_name, "score": score})

    # ── Write intermediate CSVs ──────────────────────────────────────────────
    country_csv = os.path.join(DATA_DIR, "country_distribution.csv")
    habitat_csv = os.path.join(DATA_DIR, "habitat_classification.csv")
    redlist_csv = os.path.join(DATA_DIR, "species_redlist.csv")

    for path, fieldnames, rows in [
        (country_csv, ["country_code", "scientific_name"], country_rows),
        (habitat_csv, ["scientific_name", "habitat"],      habitat_rows),
        (redlist_csv, ["scientific_name", "score"],        redlist_rows),
    ]:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"[ok] Wrote {path} ({len(rows)} records)")

    # ── Write final JSON files ───────────────────────────────────────────────
    build_native_json(country_rows,  os.path.join(DATA_DIR, "native_species.json"))
    build_habitat_json(habitat_rows, os.path.join(DATA_DIR, "habitat_traits.json"))
    build_rarity_json(redlist_rows,  os.path.join(DATA_DIR, "rarity_scores.json"))

    source = "IUCN Red List API" if using_iucn else "CSV fallback"
    print(f"\n[done] All reference files rebuilt using: {source}")
    print(
        "\nNext step:\n"
        "  uv run scripts/build_forest_json.py \\\n"
        "    --locality Kathmandu --country NP --latest-year \\\n"
        "    --native-data .\\data\\native_species.json \\\n"
        "    --habitat-data .\\data\\habitat_traits.json \\\n"
        "    --rarity-data .\\data\\rarity_scores.json"
    )


if __name__ == "__main__":
    main()