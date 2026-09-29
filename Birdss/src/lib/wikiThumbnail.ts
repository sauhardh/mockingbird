// Wikipedia summary fetcher used by multiple components for thumbnail/extract/url.
// Pulled out of BirdSpeciesGallery so trees, food sources, etc. can reuse the same path.

export interface WikiInfo {
  thumb?: string;
  extract?: string;
  url?: string;
}

const cache = new Map<string, WikiInfo>();

export async function fetchWikiInfo(title: string): Promise<WikiInfo> {
  const key = title.trim();
  if (!key) return {};
  if (cache.has(key)) return cache.get(key)!;
  try {
    const res = await fetch(
      `https://en.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(key)}?redirect=true`,
    );
    if (!res.ok) {
      const empty: WikiInfo = {};
      cache.set(key, empty);
      return empty;
    }
    const data = await res.json();
    const info: WikiInfo = {
      thumb: data.thumbnail?.source,
      extract: data.extract,
      url: data.content_urls?.desktop?.page,
    };
    cache.set(key, info);
    return info;
  } catch {
    const empty: WikiInfo = {};
    cache.set(key, empty);
    return empty;
  }
}

// Take a string like "Shorea robusta (sal)" or "fruits, seeds, insects" or "seeds"
// and produce candidate Wikipedia titles in priority order.
export function wikiCandidatesFromLabel(label: string): string[] {
  // Strip outer quotes, brackets, bullets
  let trimmed = label.replace(/^[\s*•\-[\]()"'`]+|[\s*•\-[\]()"'`]+$/g, "").trim();
  if (!trimmed) return [];

  const candidates: string[] = [];

  // If there are parens like "Shorea robusta (sal tree)"
  const parenMatch = trimmed.match(/^([^(]+?)\s*\(([^)]+)\)\s*$/);
  if (parenMatch) {
    candidates.push(parenMatch[1].trim()); // e.g. "Shorea robusta"
    candidates.push(parenMatch[2].trim()); // e.g. "sal tree"
  }

  // Raw cleaned title
  candidates.push(trimmed);

  // If plural ending in 's', try singular (e.g. "fruits" -> "fruit", "berries" -> "berry", "insects" -> "insect")
  if (trimmed.endsWith("ies") && trimmed.length > 4) {
    candidates.push(trimmed.slice(0, -3) + "y");
  } else if (trimmed.endsWith("s") && !trimmed.endsWith("ss") && trimmed.length > 3) {
    candidates.push(trimmed.slice(0, -1));
  }

  // Capitalize first letter (Wikipedia page titles are case-sensitive on first letter)
  const capitalized = trimmed.charAt(0).toUpperCase() + trimmed.slice(1);
  candidates.push(capitalized);

  // If it's a tree name without "tree", also try adding "tree" (e.g. "Sal" -> "Sal tree")
  if (!trimmed.toLowerCase().includes("tree") && trimmed.split(" ").length <= 2) {
    candidates.push(`${capitalized} tree`);
  }

  // Dedupe while preserving order
  return Array.from(new Set(candidates.filter(Boolean)));
}

export async function fetchBestWikiInfo(label: string): Promise<WikiInfo> {
  const candidates = wikiCandidatesFromLabel(label);
  for (const candidate of candidates) {
    const info = await fetchWikiInfo(candidate);
    if (info.thumb) return info;
  }
  // No thumbnail found — return first with extract or URL
  for (const candidate of candidates) {
    const info = await fetchWikiInfo(candidate);
    if (info.url || info.extract) return info;
  }
  return {};
}
