import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, ExternalLink, Loader2, Trees, Utensils, Layers, Sparkles } from "lucide-react";
import type { ForestMetrics } from "@/lib/forestApi";
import { cn } from "@/lib/utils";
import { fetchBestWikiInfo, type WikiInfo } from "@/lib/wikiThumbnail";

interface ForestHealthAssessment {
  health_label: string;
  verdict: string;
  expected_trees: string[];
  expected_food_sources: string[];
  ecology_type: string;
  key_strengths: string[];
  key_concerns: string[];
}

interface Props {
  analysis: string | null;
  metrics: ForestMetrics | null;
  loading: boolean;
  error: string | null;
}

const labelTone: Record<string, string> = {
  Excellent: "bg-emerald-500/15 text-emerald-600 border-emerald-500/30",
  Good: "bg-health-good/15 text-health-good border-health-good/30",
  Fair: "bg-health-mid/15 text-amber-bird border-health-mid/30",
  Poor: "bg-health-bad/15 text-health-bad border-health-bad/30",
  Critical: "bg-health-bad/25 text-health-bad border-health-bad/50",
  Unknown: "bg-muted text-muted-foreground border-border",
};

function tryParse(raw: string | null): { assessment: ForestHealthAssessment | null } {
  if (!raw) return { assessment: null };
  let clean = raw.trim();
  if (clean.includes("```")) {
    const match = clean.match(/```(?:json)?\s*([\s\S]*?)```/);
    if (match?.[1]) clean = match[1].trim();
  }
  const candidates = [
    () => JSON.parse(clean),
    () => JSON.parse(clean.replace(/,\s*([}\]])/g, "$1")),
    () => {
      const first = clean.indexOf("{");
      const last = clean.lastIndexOf("}");
      if (first === -1 || last <= first) throw new Error("no braces");
      return JSON.parse(clean.substring(first, last + 1).replace(/,\s*([}\]])/g, "$1"));
    },
  ];
  for (const fn of candidates) {
    try {
      const parsed = fn();
      const assessment = parsed?.forest_health_assessment ?? null;
      if (assessment && typeof assessment === "object") {
        // Sanitize health_label: extract pure status (Excellent, Good, Fair, Poor, Critical)
        // or discard placeholder prompt brackets.
        let rawLabel = String(assessment.health_label ?? "").trim();
        let cleanLabel = "";
        for (const candidate of ["Excellent", "Good", "Fair", "Poor", "Critical"]) {
          if (new RegExp(`\\b${candidate}\\b`, "i").test(rawLabel)) {
            cleanLabel = candidate;
            break;
          }
        }

        // Sanitize ecology_type: remove prompt brackets like '[dense broadleaf canopy]'
        let cleanEcology = String(assessment.ecology_type ?? "")
          .replace(/^[\s*•\-[\]()"'`]+|[\s*•\-[\]()"'`]+$/g, "")
          .trim();
        if (cleanEcology.toLowerCase().includes("one short phrase describing")) {
          cleanEcology = "";
        }

        // Helper to flatten arrays and split comma-joined items (e.g. "fruits, seeds, insects")
        const sanitizeItems = (raw: unknown): string[] => {
          if (!Array.isArray(raw)) return [];
          const list: string[] = [];
          for (const item of raw) {
            const str = String(item ?? "").replace(/^[\s*•\-[\]()"'`]+|[\s*•\-[\]()"'`]+$/g, "").trim();
            if (!str || str.toLowerCase().includes("list 3-6") || str.toLowerCase().includes("tree species")) continue;
            // Split comma lists if model grouped them into a single string
            if (str.includes(",") && !str.includes("(") && !str.includes(")")) {
              for (const part of str.split(",")) {
                const sub = part.replace(/^[\s*•\-[\]()"'`]+|[\s*•\-[\]()"'`]+$/g, "").trim();
                if (sub) list.push(sub);
              }
            } else {
              list.push(str);
            }
          }
          return Array.from(new Set(list));
        };

        const parsedTrees = sanitizeItems(assessment.expected_trees);
        const parsedFood = sanitizeItems(assessment.expected_food_sources);

        return {
          assessment: {
            health_label: cleanLabel || "Unknown",
            verdict: String(assessment.verdict ?? "")
              .replace(/^[\s*•\-[\]()"'`]+|[\s*•\-[\]()"'`]+$/g, "")
              .trim(),
            expected_trees: parsedTrees,
            expected_food_sources: parsedFood,
            ecology_type: cleanEcology,
            key_strengths: Array.isArray(assessment.key_strengths) ? assessment.key_strengths.map(String) : [],
            key_concerns: Array.isArray(assessment.key_concerns) ? assessment.key_concerns.map(String) : [],
          },
        };
      }
    } catch {
      // try next strategy
    }
  }
  return { assessment: null };
}

function fallbackVerdict(metrics: ForestMetrics): string {
  const score = metrics.composite_health.score;
  const label = metrics.composite_health.label;
  if (metrics.unique_species <= 1) {
    return `Only ${metrics.unique_species} species was detected. With a composite score of ${(score * 100).toFixed(0)}/100 (${label}), the audio sample suggests either a very short recording or a heavily degraded ecosystem dominated by generalist species.`;
  }
  if (score < 0.35) {
    return `Composite score ${(score * 100).toFixed(0)}/100 — ${label}. Low diversity and high dominance suggest a disturbed or edge habitat rather than an intact forest.`;
  }
  if (score < 0.55) {
    return `Composite score ${(score * 100).toFixed(0)}/100 — ${label}. The bird community has moderate diversity; some forest-dependent species are present but generalists may still dominate.`;
  }
  return `Composite score ${(score * 100).toFixed(0)}/100 — ${label}. A diverse community with multiple forest-dependent species indicates a structurally healthy ecosystem.`;
}

export function ForestHealthVerdict({ analysis, metrics, loading, error }: Props) {
  const { assessment } = tryParse(analysis);

  if (loading && !assessment) {
    return (
      <div className="rounded-3xl bg-card border border-border p-6 shadow-soft flex items-center gap-3 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin text-primary" />
        Synthesizing forest health verdict from metrics + RAG…
      </div>
    );
  }

  if (error && !assessment) {
    return (
      <div className="rounded-3xl bg-card border border-destructive/30 p-6 shadow-soft text-sm text-destructive">
        Verdict unavailable: {error}
      </div>
    );
  }

  if (!metrics) return null;

  const compositePct = Math.round(Math.max(0, Math.min(1, metrics.composite_health.score)) * 100);
  const label = assessment?.health_label || metrics.composite_health.label || "Unknown";
  const verdictText = assessment?.verdict || fallbackVerdict(metrics);
  const ecologyType = assessment?.ecology_type || "";
  const trees = assessment?.expected_trees ?? [];
  const food = assessment?.expected_food_sources ?? [];
  const strengths = assessment?.key_strengths ?? [];
  const concerns = assessment?.key_concerns ?? [];

  return (
    <div className="rounded-3xl bg-card border border-border p-6 shadow-soft space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-gradient-forest text-primary-foreground flex items-center justify-center shadow-md">
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <h3 className="font-display text-2xl font-bold">Forest health verdict</h3>
            <p className="text-xs text-muted-foreground">
              Synthesized from `/forest` metrics + RAG ecological knowledge
            </p>
          </div>
        </div>
        <span
          className={cn(
            "text-base md:text-lg font-display font-bold uppercase tracking-wider px-4 py-2 md:px-5 md:py-2.5 rounded-2xl border-2 shadow-md max-w-full break-words text-center",
            labelTone[label] ?? labelTone.Unknown,
          )}
        >
          {label}
        </span>
      </div>

      <div className="rounded-2xl bg-gradient-forest text-primary-foreground p-6 relative overflow-hidden">
        <div className="absolute inset-0 opacity-10 bg-[radial-gradient(circle_at_20%_20%,white,transparent_50%)]" />
        <div className="relative grid md:grid-cols-[auto_1fr] gap-6 items-center">
          <div>
            <p className="text-xs uppercase tracking-widest opacity-70">Forest Health Index</p>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="font-display text-6xl font-light tabular-nums">{compositePct}</span>
              <span className="text-xl opacity-60">/100</span>
            </div>
            {ecologyType && (
              <p className="mt-2 text-sm opacity-90">
                <Layers className="inline h-3.5 w-3.5 mr-1 -mt-0.5" />
                {ecologyType}
              </p>
            )}
          </div>
          <p className="text-sm leading-relaxed opacity-95">{verdictText}</p>
        </div>
      </div>

      <div className="space-y-4">
        <div className="rounded-2xl border border-border bg-secondary/10 p-4 space-y-3">
          <div className="flex items-center gap-2 text-muted-foreground">
            <Trees className="h-4 w-4 text-emerald-600" />
            <span className="text-[10px] font-bold uppercase tracking-wider">Trees expected in this forest</span>
          </div>
          {trees.length > 0 ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
              {trees.map((t) => (
                <WikiImageCard key={t} label={t} accent="emerald" fallbackIcon="tree" />
              ))}
            </div>
          ) : (
            <p className="text-xs text-muted-foreground italic">
              No tree suggestions available — try a sample with more species.
            </p>
          )}
        </div>

        <div className="rounded-2xl border border-border bg-secondary/10 p-4 space-y-3">
          <div className="flex items-center gap-2 text-muted-foreground">
            <Utensils className="h-4 w-4 text-amber-bird" />
            <span className="text-[10px] font-bold uppercase tracking-wider">Food sources the birds need</span>
          </div>
          {food.length > 0 ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
              {food.map((f) => (
                <WikiImageCard key={f} label={f} accent="amber" fallbackIcon="food" />
              ))}
            </div>
          ) : (
            <p className="text-xs text-muted-foreground italic">
              No food data available — try a sample with more species.
            </p>
          )}
        </div>
      </div>

      {/* strengths & concerns below */}
      {(strengths.length > 0 || concerns.length > 0) && (
        <div className="grid md:grid-cols-2 gap-4">
          {strengths.length > 0 && (
            <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/5 p-4 space-y-2">
              <div className="flex items-center gap-2 text-emerald-700">
                <CheckCircle2 className="h-4 w-4" />
                <span className="text-[10px] font-bold uppercase tracking-wider">Key strengths</span>
              </div>
              <ul className="space-y-1 text-xs text-foreground/85">
                {strengths.map((s) => (
                  <li key={s} className="flex items-start gap-2">
                    <span className="mt-1 h-1 w-1 rounded-full bg-emerald-600 shrink-0" />
                    <span>{s}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {concerns.length > 0 && (
            <div className="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-4 space-y-2">
              <div className="flex items-center gap-2 text-amber-600">
                <AlertTriangle className="h-4 w-4" />
                <span className="text-[10px] font-bold uppercase tracking-wider">Key concerns</span>
              </div>
              <ul className="space-y-1 text-xs text-foreground/85">
                {concerns.map((c) => (
                  <li key={c} className="flex items-start gap-2">
                    <span className="mt-1 h-1 w-1 rounded-full bg-amber-500 shrink-0" />
                    <span>{c}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

interface WikiImageCardProps {
  label: string;
  accent: "emerald" | "amber";
  fallbackIcon: "tree" | "food";
}

function WikiImageCard({ label, accent, fallbackIcon }: WikiImageCardProps) {
  const [info, setInfo] = useState<WikiInfo | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchBestWikiInfo(label).then((res) => {
      if (!cancelled) {
        setInfo(res);
        setLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [label]);

  const FallbackIcon = fallbackIcon === "tree" ? Trees : Utensils;
  const accentClasses =
    accent === "emerald"
      ? "from-emerald-500/20 to-green-500/10 text-emerald-700"
      : "from-amber-500/20 to-orange-400/10 text-amber-700";

  const card = (
    <div className="group rounded-xl overflow-hidden border border-border bg-background hover:shadow-soft hover:-translate-y-0.5 transition-all duration-300 h-full flex flex-col">
      <div className={cn("aspect-[4/3] bg-gradient-to-br relative overflow-hidden", accentClasses)}>
        {loading ? (
          <div className="absolute inset-0 animate-pulse bg-muted/40" />
        ) : info?.thumb ? (
          <img
            src={info.thumb}
            alt={label}
            loading="lazy"
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700"
          />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center">
            <FallbackIcon className="h-10 w-10 opacity-40" />
          </div>
        )}
        {info?.url && (
          <span className="absolute top-1.5 right-1.5 rounded-full bg-black/40 backdrop-blur-sm p-1 text-white opacity-0 group-hover:opacity-100 transition-opacity">
            <ExternalLink className="h-3 w-3" />
          </span>
        )}
      </div>
      <div className="p-2 flex-1 flex items-center">
        <p className="text-xs font-medium leading-tight line-clamp-2">{label}</p>
      </div>
    </div>
  );

  return info?.url ? (
    <a
      href={info.url}
      target="_blank"
      rel="noopener noreferrer"
      className="block"
      aria-label={`Open Wikipedia article for ${label}`}
    >
      {card}
    </a>
  ) : (
    card
  );
}
