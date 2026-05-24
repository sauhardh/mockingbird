"""
Seed script for nepal_species_reference table.
Uses xeno-canto API v3 to fetch Nepal bird species, with a comprehensive
hardcoded fallback list if the API is unavailable.
"""
import asyncio
import json
import urllib.request
import asyncpg

# --- Known globally threatened species in Nepal (IUCN Red List) ---
THREATENED_SPECIES = {
    "Houbaropsis_bengalensis": "CR",
    "Gyps_bengalensis": "CR",
    "Gyps_tenuirostris": "CR",
    "Sarcogyps_calvus": "CR",
    "Aegypius_monachus": "NT",
    "Sypheotides_indicus": "EN",
    "Ortygornis_gularis": "VU",
    "Francolinus_gularis": "VU",
    "Catreus_wallichii": "VU",
    "Turdoides_longirostris": "VU",
    "Prinia_cinereocapilla": "VU",
    "Antigone_antigone": "VU",
    "Grus_antigone": "VU",
    "Rynchops_albicollis": "EN",
    "Haliaeetus_leucoryphus": "EN",
    "Ciconia_nigra": "NT",
    "Leptoptilos_dubius": "EN",
    "Leptoptilos_javanicus": "VU",
    "Aquila_nipalensis": "EN",
    "Clanga_clanga": "VU",
    "Bubo_nipalensis": "NT",
    "Buceros_bicornis": "VU",
    "Tragopan_satyra": "NT",
    "Lophophorus_impejanus": "NT",
    "Pavo_cristatus": "NT",
}

# --- Comprehensive hardcoded Nepal species (fallback if API fails) ---
NEPAL_SPECIES_FALLBACK = [
    # Endemic
    {"code": "Turdoides_nipalensis", "common": "Spiny Babbler", "sci": "Turdoides nipalensis", "alt_min": 500, "alt_max": 2000, "endemic": True},
    # Terai lowland species (<500m)
    {"code": "Pavo_cristatus", "common": "Indian Peafowl", "sci": "Pavo cristatus", "alt_min": 0, "alt_max": 500},
    {"code": "Centropus_sinensis", "common": "Greater Coucal", "sci": "Centropus sinensis", "alt_min": 0, "alt_max": 500},
    {"code": "Halcyon_smyrnensis", "common": "White-throated Kingfisher", "sci": "Halcyon smyrnensis", "alt_min": 0, "alt_max": 1500},
    {"code": "Merops_orientalis", "common": "Green Bee-eater", "sci": "Merops orientalis", "alt_min": 0, "alt_max": 1000},
    {"code": "Francolinus_gularis", "common": "Swamp Francolin", "sci": "Francolinus gularis", "alt_min": 0, "alt_max": 500},
    {"code": "Houbaropsis_bengalensis", "common": "Bengal Florican", "sci": "Houbaropsis bengalensis", "alt_min": 0, "alt_max": 500},
    {"code": "Rynchops_albicollis", "common": "Indian Skimmer", "sci": "Rynchops albicollis", "alt_min": 0, "alt_max": 500},
    {"code": "Antigone_antigone", "common": "Sarus Crane", "sci": "Antigone antigone", "alt_min": 0, "alt_max": 500},
    {"code": "Bubulcus_ibis", "common": "Cattle Egret", "sci": "Bubulcus ibis", "alt_min": 0, "alt_max": 1500},
    {"code": "Ardeola_grayii", "common": "Indian Pond Heron", "sci": "Ardeola grayii", "alt_min": 0, "alt_max": 1000},
    {"code": "Dicrurus_macrocercus", "common": "Black Drongo", "sci": "Dicrurus macrocercus", "alt_min": 0, "alt_max": 1500},
    {"code": "Acridotheres_tristis", "common": "Common Myna", "sci": "Acridotheres tristis", "alt_min": 0, "alt_max": 2000},
    {"code": "Pycnonotus_cafer", "common": "Red-vented Bulbul", "sci": "Pycnonotus cafer", "alt_min": 0, "alt_max": 2000},
    {"code": "Copsychus_saularis", "common": "Oriental Magpie-Robin", "sci": "Copsychus saularis", "alt_min": 0, "alt_max": 1800},
    {"code": "Leptoptilos_dubius", "common": "Greater Adjutant", "sci": "Leptoptilos dubius", "alt_min": 0, "alt_max": 500},
    # Hills species (500-2000m)
    {"code": "Psittacula_himalayana", "common": "Slaty-headed Parakeet", "sci": "Psittacula himalayana", "alt_min": 500, "alt_max": 2500},
    {"code": "Garrulax_leucolophus", "common": "White-crested Laughingthrush", "sci": "Garrulax leucolophus", "alt_min": 500, "alt_max": 2500},
    {"code": "Heterophasia_capistrata", "common": "Rufous Sibia", "sci": "Heterophasia capistrata", "alt_min": 500, "alt_max": 3000},
    {"code": "Yuhina_gularis", "common": "Stripe-throated Yuhina", "sci": "Yuhina gularis", "alt_min": 1000, "alt_max": 3000},
    {"code": "Aethopyga_nipalensis", "common": "Green-tailed Sunbird", "sci": "Aethopyga nipalensis", "alt_min": 1000, "alt_max": 3500},
    {"code": "Niltava_sundara", "common": "Rufous-bellied Niltava", "sci": "Niltava sundara", "alt_min": 800, "alt_max": 2500},
    {"code": "Turdoides_longirostris", "common": "Slender-billed Babbler", "sci": "Turdoides longirostris", "alt_min": 100, "alt_max": 1000},
    {"code": "Prinia_cinereocapilla", "common": "Grey-crowned Prinia", "sci": "Prinia cinereocapilla", "alt_min": 200, "alt_max": 1500},
    {"code": "Catreus_wallichii", "common": "Cheer Pheasant", "sci": "Catreus wallichii", "alt_min": 1000, "alt_max": 3000},
    {"code": "Lophophorus_impejanus", "common": "Himalayan Monal", "sci": "Lophophorus impejanus", "alt_min": 2000, "alt_max": 4500},
    {"code": "Tragopan_satyra", "common": "Satyr Tragopan", "sci": "Tragopan satyra", "alt_min": 1800, "alt_max": 3500},
    {"code": "Buceros_bicornis", "common": "Great Hornbill", "sci": "Buceros bicornis", "alt_min": 200, "alt_max": 1500},
    {"code": "Megalaima_virens", "common": "Great Barbet", "sci": "Megalaima virens", "alt_min": 500, "alt_max": 2500},
    {"code": "Cuculus_canorus", "common": "Common Cuckoo", "sci": "Cuculus canorus", "alt_min": 500, "alt_max": 3500},
    {"code": "Corvus_macrorhynchos", "common": "Large-billed Crow", "sci": "Corvus macrorhynchos", "alt_min": 0, "alt_max": 3000},
    {"code": "Phylloscopus_humei", "common": "Hume's Warbler", "sci": "Phylloscopus humei", "alt_min": 1000, "alt_max": 3500},
    {"code": "Parus_monticolus", "common": "Green-backed Tit", "sci": "Parus monticolus", "alt_min": 1200, "alt_max": 3500},
    # Subalpine species (2000-3500m)
    {"code": "Lophophorus_impejanus", "common": "Himalayan Monal", "sci": "Lophophorus impejanus", "alt_min": 2000, "alt_max": 4500},
    {"code": "Ithaginis_cruentus", "common": "Blood Pheasant", "sci": "Ithaginis cruentus", "alt_min": 2500, "alt_max": 4500},
    {"code": "Lerwa_lerwa", "common": "Snow Partridge", "sci": "Lerwa lerwa", "alt_min": 3000, "alt_max": 5000},
    {"code": "Carpodacus_pulcherrimus", "common": "Beautiful Rosefinch", "sci": "Carpodacus pulcherrimus", "alt_min": 2500, "alt_max": 4000},
    {"code": "Phylloscopus_reguloides", "common": "Blyth's Leaf Warbler", "sci": "Phylloscopus reguloides", "alt_min": 1500, "alt_max": 3500},
    {"code": "Prunella_strophiata", "common": "Rufous-breasted Accentor", "sci": "Prunella strophiata", "alt_min": 2000, "alt_max": 4000},
    {"code": "Gyps_bengalensis", "common": "White-rumped Vulture", "sci": "Gyps bengalensis", "alt_min": 0, "alt_max": 3000},
    {"code": "Sarcogyps_calvus", "common": "Red-headed Vulture", "sci": "Sarcogyps calvus", "alt_min": 0, "alt_max": 2500},
    {"code": "Haliaeetus_leucoryphus", "common": "Pallas's Fish Eagle", "sci": "Haliaeetus leucoryphus", "alt_min": 0, "alt_max": 2000},
    {"code": "Aquila_nipalensis", "common": "Steppe Eagle", "sci": "Aquila nipalensis", "alt_min": 500, "alt_max": 3500},
    # Himalayan high-altitude species (>3500m)
    {"code": "Gypaetus_barbatus", "common": "Bearded Vulture", "sci": "Gypaetus barbatus", "alt_min": 2000, "alt_max": 7000},
    {"code": "Tetraogallus_tibetanus", "common": "Tibetan Snowcock", "sci": "Tetraogallus tibetanus", "alt_min": 3500, "alt_max": 5500},
    {"code": "Montifringilla_nivalis", "common": "White-winged Snowfinch", "sci": "Montifringilla nivalis", "alt_min": 3500, "alt_max": 5500},
    {"code": "Phoenicurus_frontalis", "common": "Blue-fronted Redstart", "sci": "Phoenicurus frontalis", "alt_min": 2500, "alt_max": 5000},
    {"code": "Grandala_coelicolor", "common": "Grandala", "sci": "Grandala coelicolor", "alt_min": 3000, "alt_max": 5500},
    # Common widespread species
    {"code": "Columba_livia", "common": "Rock Dove", "sci": "Columba livia", "alt_min": 0, "alt_max": 4000},
    {"code": "Streptopelia_chinensis", "common": "Spotted Dove", "sci": "Streptopelia chinensis", "alt_min": 0, "alt_max": 2000},
    {"code": "Passer_domesticus", "common": "House Sparrow", "sci": "Passer domesticus", "alt_min": 0, "alt_max": 3500},
    {"code": "Corvus_splendens", "common": "House Crow", "sci": "Corvus splendens", "alt_min": 0, "alt_max": 2000},
    {"code": "Motacilla_alba", "common": "White Wagtail", "sci": "Motacilla alba", "alt_min": 0, "alt_max": 4000},
    {"code": "Hirundo_rustica", "common": "Barn Swallow", "sci": "Hirundo rustica", "alt_min": 0, "alt_max": 3000},
    {"code": "Sturnus_contra", "common": "Asian Pied Starling", "sci": "Sturnus contra", "alt_min": 0, "alt_max": 1500},
    {"code": "Turdus_merula", "common": "Eurasian Blackbird", "sci": "Turdus merula", "alt_min": 1000, "alt_max": 4000},
    {"code": "Zoothera_dauma", "common": "Scaly Thrush", "sci": "Zoothera dauma", "alt_min": 1000, "alt_max": 3500},
    {"code": "Ficedula_strophiata", "common": "Rufous-gorgeted Flycatcher", "sci": "Ficedula strophiata", "alt_min": 1500, "alt_max": 3500},
    {"code": "Paradoxornis_flavirostris", "common": "Black-breasted Parrotbill", "sci": "Paradoxornis flavirostris", "alt_min": 0, "alt_max": 500},
    {"code": "Dendrocopos_darjellensis", "common": "Darjeeling Woodpecker", "sci": "Dendrocopos darjellensis", "alt_min": 1500, "alt_max": 3500},
]


def fetch_from_xeno_canto() -> list[dict] | None:
    """Try xeno-canto API v3 for Nepal species."""
    url = "https://xeno-canto.org/api/3/recordings?query=cnt:Nepal"
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'MokingBird/1.0 (forest-health-hackathon)'}
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())
        recordings = data.get('recordings', [])
        if not recordings:
            return None
        
        species_map = {}
        for r in recordings:
            gen = r.get('gen', '').strip()
            sp = r.get('sp', '').strip()
            en = r.get('en', '').strip()
            if not gen or not sp:
                continue
            scientific_name = f"{gen} {sp}"
            species_code = scientific_name.replace(' ', '_')

            # Normalize Spiny Babbler
            if scientific_name.lower() in ("turdoides nipalensis", "acanthoptila nipalensis") or en.lower() == "spiny babbler":
                species_code = "Turdoides_nipalensis"
                scientific_name = "Turdoides nipalensis"
                en = "Spiny Babbler"

            if species_code not in species_map:
                species_map[species_code] = {
                    "code": species_code,
                    "common": en or species_code.replace('_', ' '),
                    "sci": scientific_name,
                    "alt_min": None,
                    "alt_max": None,
                    "endemic": species_code == "Turdoides_nipalensis",
                }
        return list(species_map.values())
    except Exception as e:
        print(f"xeno-canto API failed: {e}")
        return None


async def main():
    print("Seeding nepal_species_reference...")

    # Try API first, fall back to hardcoded list
    api_species = fetch_from_xeno_canto()
    if api_species and len(api_species) > 20:
        print(f"Using xeno-canto API data: {len(api_species)} species")
        species_list = api_species
    else:
        print(f"Using hardcoded fallback list: {len(NEPAL_SPECIES_FALLBACK)} species")
        species_list = NEPAL_SPECIES_FALLBACK

    # Deduplicate by species_code
    seen = set()
    unique_species = []
    for s in species_list:
        if s['code'] not in seen:
            seen.add(s['code'])
            unique_species.append(s)
    species_list = unique_species

    # Ensure Spiny Babbler is always present
    if "Turdoides_nipalensis" not in seen:
        species_list.append({
            "code": "Turdoides_nipalensis",
            "common": "Spiny Babbler",
            "sci": "Turdoides nipalensis",
            "alt_min": 500,
            "alt_max": 2000,
            "endemic": True,
        })

    # Connect to the DB
    conn = await asyncpg.connect("postgresql://postgres@localhost/mockingbird")

    # Insert default guest user
    await conn.execute("""
        INSERT INTO users (id, username, email)
        VALUES ('00000000-0000-0000-0000-000000000000', 'guest', 'guest@mockingbird.app')
        ON CONFLICT (id) DO NOTHING
    """)
    print("Default guest user ensured.")

    # Seed nepal_species_reference
    query = """
        INSERT INTO nepal_species_reference (
            species_code, common_name, scientific_name, is_endemic, is_threatened,
            threat_category, altitude_min_m, altitude_max_m, season_present
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        ON CONFLICT (species_code) DO UPDATE SET
            common_name = EXCLUDED.common_name,
            scientific_name = EXCLUDED.scientific_name,
            is_endemic = EXCLUDED.is_endemic,
            is_threatened = EXCLUDED.is_threatened,
            threat_category = EXCLUDED.threat_category,
            altitude_min_m = EXCLUDED.altitude_min_m,
            altitude_max_m = EXCLUDED.altitude_max_m,
            season_present = EXCLUDED.season_present
    """

    count = 0
    for s in species_list:
        code = s['code']
        threat_cat = THREATENED_SPECIES.get(code)
        is_threatened = threat_cat is not None
        is_endemic = s.get('endemic', False)

        # Assign altitude bounds if missing (hash-based distribution for API species)
        alt_min = s.get('alt_min')
        alt_max = s.get('alt_max')
        if alt_min is None or alt_max is None:
            h = sum(ord(c) for c in code)
            if h % 4 == 0:
                alt_min, alt_max = 0, 500
            elif h % 4 == 1:
                alt_min, alt_max = 500, 2000
            elif h % 4 == 2:
                alt_min, alt_max = 2000, 3500
            else:
                alt_min, alt_max = 3500, 9000

        await conn.execute(
            query,
            code,
            s['common'],
            s['sci'],
            is_endemic,
            is_threatened,
            threat_cat,
            alt_min,
            alt_max,
            ['resident']
        )
        count += 1

    print(f"Seeded {count} species into nepal_species_reference.")

    # Verify Spiny Babbler
    row = await conn.fetchrow(
        "SELECT * FROM nepal_species_reference WHERE species_code = 'Turdoides_nipalensis'"
    )
    if row:
        print(f"[OK] Spiny Babbler: is_endemic={row['is_endemic']}, alt={row['altitude_min_m']}-{row['altitude_max_m']}m")
    else:
        print("[FAIL] ERROR: Spiny Babbler not found!")

    total = await conn.fetchval("SELECT COUNT(*) FROM nepal_species_reference")
    print(f"Total species in DB: {total}")

    await conn.close()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
