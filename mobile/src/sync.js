import { mergeManifests } from "./domain.js";

export const DEFAULT_INDEX_URL = "paczki/index.json";

export function absoluteIndexUrl(indexUrl, base = globalThis.location?.href) {
  return new URL(indexUrl || DEFAULT_INDEX_URL, base).href;
}

export async function fetchIndexAndManifests(indexUrl, brand, fetcher = fetch) {
  if (!indexUrl) throw new Error("Ustaw adres index.json z paczkami");
  indexUrl = absoluteIndexUrl(indexUrl);
  const indexResponse = await fetcher(indexUrl, { cache: "no-store" });
  if (!indexResponse.ok) throw new Error(`Indeks: HTTP ${indexResponse.status}`);
  const index = await indexResponse.json();
  if (!Array.isArray(index.packages)) throw new Error("Indeks nie zawiera tablicy packages");
  const entries = index.packages.filter(x => !x.brand || x.brand === brand);
  const manifests = await Promise.all(entries.map(async entry => {
    const url = new URL(entry.manifest_url || entry.url, indexUrl).href;
    const response = await fetcher(url, { cache: "no-store" });
    if (!response.ok) throw new Error(`Manifest: HTTP ${response.status}`);
    const manifest = await response.json();
    return { ...manifest, _manifest_url: url };
  }));
  return manifests;
}

export async function refreshPackages({ indexUrl, brand, existing, fetcher = fetch }) {
  const incoming = await fetchIndexAndManifests(indexUrl, brand, fetcher);
  return mergeManifests(existing, incoming, brand);
}
