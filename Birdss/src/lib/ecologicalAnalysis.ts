import type { ForestMetrics } from "@/lib/forestApi";
import { chatCompletion } from "@/lib/llmClient";

export interface EcologicalAnalysisInput {
  location: string;
  species: string[];
  metrics: ForestMetrics;
  retrievedChunks: Array<{
    species: string;
    chunks: Array<Record<string, unknown>>;
  }>;
}

/**
 * Attempt to repair broken JSON strings using multiple strategies.
 * Returns the parsed object or null.
 */
function repairAndParse(raw: string): { parsed: Record<string, unknown> | null; repaired: boolean; issues: string[] } {
  const issues: string[] = [];
  let repaired = false;
  let clean = raw.trim();

  // Strategy 1: Remove markdown code fences
  if (clean.includes("```")) {
    const match = clean.match(/```(?:json)?\s*([\s\S]*?)```/);
    if (match?.[1]) {
      clean = match[1].trim();
      repaired = true;
      issues.push("Removed markdown code block formatting");
    }
  }

  // Strategy 2: Direct parse
  try {
    return { parsed: JSON.parse(clean), repaired, issues };
  } catch (e: any) {
    issues.push(`Direct parse failed: ${e.message}`);
  }

  // Strategy 3: Remove trailing commas before ] or }
  try {
    const noTrailing = clean.replace(/,\s*([}\]])/g, "$1");
    repaired = true;
    issues.push("Removed trailing commas");
    return { parsed: JSON.parse(noTrailing), repaired, issues };
  } catch (e: any) {
    issues.push(`Trailing comma repair failed: ${e.message}`);
  }

  // Strategy 4: Extract largest bounding braces
  const firstBrace = clean.indexOf("{");
  const lastBrace = clean.lastIndexOf("}");
  if (firstBrace !== -1 && lastBrace > firstBrace) {
    try {
      const substring = clean.substring(firstBrace, lastBrace + 1);
      repaired = true;
      issues.push("Extracted bounding braces substring");
      return { parsed: JSON.parse(substring), repaired, issues };
    } catch (e: any) {
      issues.push(`Brace extraction failed: ${e.message}`);
    }

    // Strategy 5: Brace extraction + trailing comma removal
    try {
      const substring = clean.substring(firstBrace, lastBrace + 1).replace(/,\s*([}\]])/g, "$1");
      repaired = true;
      issues.push("Combined brace extraction + trailing comma removal");
      return { parsed: JSON.parse(substring), repaired, issues };
    } catch (e: any) {
      issues.push(`Combined repair failed: ${e.message}`);
    }
  }

  return { parsed: null, repaired, issues };
}

export async function generateEcologicalAnalysis(input: EcologicalAnalysisInput): Promise<string | null> {

  // Groq free tier caps at 6000 tokens/minute. Full RAG chunks (index, distance, full text)
  // blow past that quickly with >3 species. Trim to the essentials: top 2 chunks per species,
  // only the `text` field, truncated to ~280 chars. Keeps signal, drops noise.
  const MAX_CHUNKS_PER_SPECIES = 2;
  const MAX_CHARS_PER_CHUNK = 280;
  const trimmedChunks = input.retrievedChunks.map(({ species, chunks }) => ({
    species,
    chunks: chunks.slice(0, MAX_CHUNKS_PER_SPECIES).map((c) => {
      const raw = typeof (c as any).text === "string" ? (c as any).text : JSON.stringify(c);
      return raw.length > MAX_CHARS_PER_CHUNK ? raw.slice(0, MAX_CHARS_PER_CHUNK) + "…" : raw;
    }),
  }));
  const chunkText = JSON.stringify(trimmedChunks, null, 2);

  const systemPrompt = `You are an expert ecological analysis assistant specializing in Nepalese bird biodiversity and forest ecosystem health.
Your task is to analyze the observed species, computed ecological metrics, and RAG-retrieved ecological knowledge, then compile a structured analysis.

CRITICAL INSTRUCTIONS:
1. Return strictly a single, valid JSON object following the schema below.
2. DO NOT output placeholder brackets like "[Dominant habitat]" or "[Critical — must align...]". Replace EVERY bracketed description with real, plain-English text or reasonable ecological values.
3. For "health_label", output ONLY ONE WORD from: "Excellent", "Good", "Fair", "Poor", "Critical" (no brackets, no explanation).
4. For "expected_trees", output 3-6 individual tree names as separate strings in the array (e.g. ["Shorea robusta", "Rhododendron arboreum", "Schima wallichii", "Castanopsis indica", "Pinus roxburghii"]).
5. For "expected_food_sources", output 3-6 individual food items as separate simple nouns in the array (e.g. ["wild figs", "seeds", "caterpillars", "flower nectar", "insects"]). DO NOT lump them into a single string.
6. For "ecology_type", output a clean phrase without brackets (e.g. "subtropical mixed broadleaf forest", "temperate pine-oak woodland", "degraded forest edge").
7. If 0 or few species are detected, infer expected trees and food sources typical of the region (${input.location || "Nepal forest"}).

JSON SCHEMA TO CONFORM TO:
{
  "query_metadata": {
    "query": "Ecological analysis for ${input.location}",
    "top_k": ${input.retrievedChunks.length},
    "bird_type": "forest and woodland birds",
    "schema_version": "1.0"
  },
  "results": [
    {
      "species_id": "Scientific name",
      "common_name": "Common name",
      "family": "Family name",
      "order": "Order name",
      "habitat_profile": {
        "type_of_forest": "Specific forest habitat in Nepal",
        "habitat_density": {
          "level": 2,
          "label": "semi-open"
        },
        "tree_preference": "Preferred tree type or null",
        "environment_type": "terrestrial",
        "elevation_range": {
          "min_m": 1200,
          "max_m": 2400,
          "note": "Subtropical to temperate zone"
        }
      },
      "diet": {
        "trophic_niche": "omnivore",
        "primary_food": ["seeds", "fruits", "insects"],
        "feeding_style": "canopy foraging"
      },
      "seasonal_presence": {
        "resident_type": "year-round resident",
        "months_observed": ["January", "April", "July", "October"],
        "peak_season": "Spring"
      },
      "climate_profile": {
        "climate_zone": "subtropical",
        "migration_strategy": "sedentary",
        "migration_score": 1.0
      },
      "distribution": {
        "country": "Nepal",
        "provinces": ["Bagmati", "Gandaki"],
        "total_localities": 15,
        "bounding_box": {
          "lat_min": 27.5,
          "lat_max": 28.2,
          "lon_min": 85.1,
          "lon_max": 85.9
        }
      },
      "observation_stats": {
        "total_sightings": 45,
        "total_individuals": 78,
        "unique_observers": 12,
        "first_recorded": 2018,
        "last_recorded": 2024
      },
      "physical": {
        "body_mass_grams": 45.0,
        "lifestyle": "arboreal"
      },
      "source_file": "Ecosystem Assessment",
      "confidence_score": 0.85
    }
  ],
  "summary": {
    "total_species_found": ${input.species.length},
    "common_habitat": "Mixed broadleaf forest",
    "common_diet": ["seeds", "wild berries", "insects"],
    "common_season": "Year-round",
    "common_climate": "Subtropical montane",
    "density_range": {
      "min_level": 1,
      "max_level": 3,
      "label": "semi-open to dense canopy"
    }
  },
  "forest_health_assessment": {
    "health_label": "${input.metrics.composite_health.label || 'Critical'}",
    "verdict": "Plain-English assessment of the forest ecosystem based on the detected species and computed metrics.",
    "expected_trees": ["Shorea robusta", "Rhododendron arboreum", "Schima wallichii", "Castanopsis indica"],
    "expected_food_sources": ["wild fruits", "insects", "seeds", "nectar"],
    "ecology_type": "Subtropical mixed broadleaf forest",
    "key_strengths": ["Presence of native vegetation indicators"],
    "key_concerns": ["Low overall species diversity observed"]
  },
  "json_repair_flags": {
    "repaired": false,
    "issues_found": [],
    "strategy_used": null
  }
}`;

  const userPrompt = `
Location: ${input.location}

Observed Species list:
${input.species.map((s) => `* ${s}`).join("\n")}

Computed Ecological Metrics:
* Unique Species Count: ${input.metrics.unique_species}
* Shannon Diversity Index: ${input.metrics.shannon_idx}
* Dominance Score: ${input.metrics.dominance.dominance_score} (Dominant Species: ${input.metrics.dominance.dominant_species ?? "None"})
* Native Species Ratio: ${(input.metrics.native_ratio * 100).toFixed(1)}%
* Average Forest Dependency: ${input.metrics.forest_dependency}
* Average Rarity: ${input.metrics.rarity_score}
* Composite Forest Health Index: ${input.metrics.composite_health.score} (${input.metrics.composite_health.label})

Retrieved RAG Ecological Knowledge Chunks:
${chunkText}
`;

  try {
    const answer = await chatCompletion({
      messages: [
        { role: "system", content: systemPrompt },
        { role: "user", content: userPrompt },
      ],
      temperature: 0.1,
      max_tokens: 4096,
      json_mode: true,
    });

    if (!answer) {
      throw new Error("LLM returned an empty response (no message content).");
    }

    // Multi-strategy repair pipeline
    const { parsed, repaired, issues } = repairAndParse(answer);

    if (parsed) {
      // Inject repair metadata into the JSON
      if (repaired || issues.length > 0) {
        (parsed as any).json_repair_flags = {
          repaired,
          issues_found: issues,
          strategy_used: repaired ? "client-side multi-strategy repair" : null,
        };
      }
      return JSON.stringify(parsed);
    }

    // Last resort: return raw answer for the frontend fallback renderer
    console.warn("All JSON repair strategies failed, returning raw answer. Issues:", issues);
    return answer;
  } catch (error) {
    console.error("Failed to call Groq API:", error);
    // Re-throw so the UI surfaces the actual reason instead of a silent "No analysis available".
    throw error;
  }
}
