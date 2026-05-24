import os
import json
import csv
import re

# Directory where reference data will live
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Local CSV source of truth
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
NEPAL_SPECIES_CSV = os.path.join(SCRIPT_DIR, "Nepal-Species.csv")

# Introduced species to exclude from native list
INTRODUCED_BIRDS = {
    "Acridotheres tristis",
    "Columba livia",
    "Corvus splendens",
    "Passer domesticus",
    "Psittacula eupatria",
    "Psittacula krameri"
}

FAMILY_HABITATS = {
    "pheasant": ["forest", "shrubland"],
    "partridge": ["forest", "shrubland"],
    "turkey": ["forest", "woodland"],
    "grouse": ["forest", "shrubland"],
    "duck": ["wetland", "freshwater"],
    "goose": ["wetland", "freshwater"],
    "swan": ["wetland", "freshwater"],
    "grebe": ["wetland", "freshwater"],
    "flamingo": ["wetland", "saltwater"],
    "pigeon": ["forest", "woodland", "agricultural", "urban"],
    "dove": ["forest", "woodland", "agricultural", "urban"],
    "nightjar": ["forest", "shrubland"],
    "treeswift": ["forest", "woodland"],
    "swift": ["aerial", "forest", "urban"],
    "cuckoo": ["forest", "woodland", "shrubland"],
    "rail": ["wetland", "freshwater"],
    "gallinule": ["wetland", "freshwater"],
    "coot": ["wetland", "freshwater"],
    "crane": ["wetland", "grassland"],
    "bustard": ["grassland", "savanna"],
    "stork": ["wetland", "freshwater"],
    "ibis": ["wetland", "freshwater"],
    "spoonbill": ["wetland", "freshwater"],
    "bittern": ["wetland", "freshwater"],
    "heron": ["wetland", "freshwater"],
    "egret": ["wetland", "freshwater"],
    "pelican": ["wetland", "freshwater"],
    "cormorant": ["wetland", "freshwater"],
    "darter": ["wetland", "freshwater"],
    "thick-knee": ["grassland", "shrubland"],
    "ibisbill": ["stony riverbed", "freshwater"],
    "stilt": ["wetland", "freshwater"],
    "avocet": ["wetland", "freshwater"],
    "plover": ["wetland", "grassland"],
    "lapwing": ["wetland", "grassland"],
    "painted-snipe": ["wetland", "freshwater"],
    "jacana": ["wetland", "freshwater"],
    "sandpiper": ["wetland", "freshwater"],
    "snipe": ["wetland", "freshwater"],
    "phalarope": ["wetland", "freshwater"],
    "buttonquail": ["grassland", "shrubland"],
    "courser": ["grassland", "desert"],
    "pratincole": ["wetland", "grassland"],
    "gull": ["wetland", "marine"],
    "tern": ["wetland", "marine"],
    "skimmer": ["wetland", "freshwater"],
    "barn-owl": ["forest", "woodland", "urban"],
    "owl": ["forest", "woodland", "shrubland"],
    "boobook": ["forest", "woodland"],
    "owlet": ["forest", "woodland"],
    "osprey": ["wetland", "freshwater"],
    "kite": ["forest", "woodland", "urban"],
    "honey-buzzard": ["forest", "woodland"],
    "baza": ["forest", "woodland"],
    "vulture": ["grassland", "forest", "mountain"],
    "harrier": ["grassland", "wetland"],
    "goshawk": ["forest", "woodland"],
    "sparrowhawk": ["forest", "woodland"],
    "eagle": ["forest", "woodland", "mountain"],
    "hawk": ["forest", "woodland"],
    "buzzard": ["forest", "woodland", "grassland"],
    "trogon": ["forest"],
    "hornbill": ["forest", "woodland"],
    "hoopoe": ["woodland", "pasture", "urban"],
    "bee-eater": ["forest", "woodland", "shrubland"],
    "roller": ["woodland", "savanna"],
    "dollarbird": ["forest", "woodland"],
    "kingfisher": ["wetland", "forest", "freshwater"],
    "barbet": ["forest", "woodland"],
    "honeyguide": ["forest", "woodland"],
    "woodpecker": ["forest", "woodland"],
    "wryneck": ["woodland", "shrubland"],
    "piculet": ["forest", "woodland"],
    "flameback": ["forest", "woodland"],
    "yellownape": ["forest", "woodland"],
    "falconet": ["forest", "woodland"],
    "kestrel": ["grassland", "shrubland", "rocky"],
    "falcon": ["forest", "woodland", "mountain", "grassland"],
    "hobby": ["forest", "woodland"],
    "merlin": ["grassland", "shrubland"],
    "hanging-parrot": ["forest", "woodland"],
    "parakeet": ["forest", "woodland", "agricultural", "urban"],
    "parrot": ["forest", "woodland"],
    "pitta": ["forest"],
    "broadbill": ["forest"],
    "oriole": ["forest", "woodland"],
    "shrike-babbler": ["forest", "woodland"],
    "erpornis": ["forest", "woodland"],
    "vireo": ["forest", "woodland"],
    "minivet": ["forest", "woodland"],
    "cuckooshrikes": ["forest", "woodland"],
    "woodswallow": ["woodland", "savanna"],
    "flycatcher-shrike": ["forest", "woodland"],
    "woodshrike": ["forest", "woodland"],
    "iora": ["forest", "woodland", "shrubland"],
    "fantail": ["forest", "woodland", "shrubland"],
    "drongo": ["forest", "woodland", "agricultural"],
    "monarch": ["forest", "woodland"],
    "paradise-flycatcher": ["forest", "woodland"],
    "shrike": ["shrubland", "grassland"],
    "treepie": ["forest", "woodland", "agricultural"],
    "chough": ["mountain", "grassland", "rocky"],
    "magpie": ["forest", "woodland", "shrubland"],
    "jay": ["forest", "woodland"],
    "nutcracker": ["forest", "woodland"],
    "raven": ["mountain", "grassland", "urban"],
    "crow": ["urban", "agricultural", "forest"],
    "canary-flycatcher": ["forest", "woodland"],
    "fairy-fantail": ["forest", "woodland"],
    "tit": ["forest", "woodland"],
    "chickadee": ["forest", "woodland"],
    "lark": ["grassland", "agricultural"],
    "cisticola": ["grassland", "wetland"],
    "prinia": ["grassland", "shrubland"],
    "tailorbird": ["forest", "shrubland", "urban"],
    "warbler": ["forest", "woodland", "shrubland"],
    "reed-warbler": ["wetland", "reedbeds"],
    "cupwing": ["forest", "shrubland"],
    "grassbird": ["grassland", "wetland"],
    "martin": ["aerial", "urban", "rocky"],
    "swallow": ["aerial", "agricultural", "urban"],
    "bulbul": ["forest", "woodland", "shrubland", "agricultural"],
    "tesia": ["forest", "shrubland"],
    "bush-warbler": ["forest", "shrubland"],
    "tit-warbler": ["forest", "shrubland"],
    "whitethroat": ["shrubland", "woodland"],
    "myzornis": ["forest", "shrubland"],
    "fulvetta": ["forest", "shrubland"],
    "babbler": ["forest", "woodland", "shrubland"],
    "parrotbill": ["bamboo", "shrubland"],
    "yuhina": ["forest", "woodland"],
    "white-eye": ["forest", "woodland", "shrubland"],
    "wren-babbler": ["forest", "shrubland"],
    "scimitar-babbler": ["forest", "woodland", "shrubland"],
    "tit-babbler": ["forest", "shrubland"],
    "grass-babbler": ["grassland", "shrubland"],
    "laughingthrush": ["forest", "woodland", "shrubland"],
    "cutia": ["forest"],
    "sibia": ["forest", "woodland"],
    "mesia": ["forest", "shrubland"],
    "leiothrix": ["forest", "shrubland"],
}

def get_habitats(common_name: str, family_name: str, scientific_name: str) -> list[str]:
    c_low = common_name.lower()
    f_low = family_name.lower()
    s_low = scientific_name.lower()
    
    matched_habitats = set()
    for key, habitats in FAMILY_HABITATS.items():
        if key in c_low or key in f_low or key in s_low:
            for h in habitats:
                matched_habitats.add(h)
    
    if not matched_habitats:
        return ["forest"]
    return sorted(list(matched_habitats))

def build_native_json(csv_path: str, out_path: str):
    """Create mapping countryCode -> list of native species (scientific names)."""
    mapping: dict[str, set[str]] = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            country = row.get("country_code") or row.get("CountryCode")
            if not country:
                continue
            sci_name = row.get("scientific_name") or row.get("ScientificName")
            if not sci_name:
                continue
            mapping.setdefault(country, set()).add(sci_name)
    json_obj = {k: sorted(v) for k, v in mapping.items()}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(json_obj, f, ensure_ascii=False, indent=2)
    print(f"[ok] Native species JSON written to {out_path}")

def build_habitat_json(csv_path: str, out_path: str):
    """Create mapping species scientific name -> list of habitat strings."""
    mapping: dict[str, set[str]] = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sci_name = row.get("scientific_name") or row.get("ScientificName")
            habitat = row.get("habitat") or row.get("Habitat")
            if not sci_name or not habitat:
                continue
            for h in re.split(r"[;,]", habitat):
                h = h.strip()
                if h:
                    mapping.setdefault(sci_name, set()).add(h)
    json_obj = {k: sorted(v) for k, v in mapping.items()}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(json_obj, f, ensure_ascii=False, indent=2)
    print(f"[ok] Habitat JSON written to {out_path}")

def build_rarity_json(csv_path: str, out_path: str):
    """Create mapping species -> rarity score (0-1) based on IUCN Red-List category."""
    category_score = {
        "CR": 1.0,
        "EN": 0.8,
        "VU": 0.6,
        "NT": 0.4,
        "LC": 0.2,
        "DD": 0.0,
    }
    mapping: dict[str, float] = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sci_name = row.get("scientific_name") or row.get("ScientificName")
            cat = (row.get("category") or row.get("Category") or "").upper().strip()
            if not sci_name:
                continue
            score = category_score.get(cat, 0.0)
            mapping[sci_name] = score
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
    print(f"[ok] Rarity JSON written to {out_path}")

def main():
    if not os.path.exists(NEPAL_SPECIES_CSV):
        print(f"[error] Nepal species CSV not found at {NEPAL_SPECIES_CSV}")
        return

    print(f"[info] Reading from local {NEPAL_SPECIES_CSV}...")
    
    country_rows = []
    habitat_rows = []
    redlist_rows = []
    
    category_map = {
        "least concern": "LC",
        "near threatened": "NT",
        "vulnerable": "VU",
        "endangered": "EN",
        "critically endangered": "CR",
        "extinct": "EX",
        "data deficient": "DD"
    }

    with open(NEPAL_SPECIES_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sci_name = row.get("ScientificName")
            if not sci_name:
                continue
            sci_name = sci_name.strip()
            
            # 1. Native / country distribution
            if sci_name not in INTRODUCED_BIRDS:
                country_rows.append({"country_code": "NP", "scientific_name": sci_name})
            
            # 2. Habitats
            common_name = row.get("CommonName", "")
            family_name = row.get("FamilyName", "")
            habs = get_habitats(common_name, family_name, sci_name)
            habitat_rows.append({"scientific_name": sci_name, "habitat": ";".join(habs)})
            
            # 3. IUCN Red List Category
            raw_cat = (row.get("IUCNRedListCategory") or "").lower().strip()
            cat_code = category_map.get(raw_cat, "LC")
            redlist_rows.append({"scientific_name": sci_name, "category": cat_code})

    # Write target files
    country_csv = os.path.join(DATA_DIR, "country_distribution.csv")
    habitat_csv = os.path.join(DATA_DIR, "habitat_classification.csv")
    redlist_csv = os.path.join(DATA_DIR, "species_redlist.csv")

    with open(country_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["country_code", "scientific_name"])
        writer.writeheader()
        writer.writerows(country_rows)
    print(f"[ok] Wrote {country_csv} ({len(country_rows)} records)")

    with open(habitat_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["scientific_name", "habitat"])
        writer.writeheader()
        writer.writerows(habitat_rows)
    print(f"[ok] Wrote {habitat_csv} ({len(habitat_rows)} records)")

    with open(redlist_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["scientific_name", "category"])
        writer.writeheader()
        writer.writerows(redlist_rows)
    print(f"[ok] Wrote {redlist_csv} ({len(redlist_rows)} records)")

    # Build JSON files
    native_json_path = os.path.join(DATA_DIR, "native_species.json")
    habitat_json_path = os.path.join(DATA_DIR, "habitat_traits.json")
    rarity_json_path = os.path.join(DATA_DIR, "rarity_scores.json")

    build_native_json(country_csv, native_json_path)
    build_habitat_json(habitat_csv, habitat_json_path)
    build_rarity_json(redlist_csv, rarity_json_path)

if __name__ == "__main__":
    main()
