// Typed client for the GraphBA backend. Shapes mirror the locked server
// contracts (Node / Link / PlayerSearchResult / PlayerProfile / PathResponse).

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface PlayerSearchResult {
  id: number;
  name: string;
  active_years: string;
}

export interface GraphNode {
  id: number;
  name: string;
  // react-force-graph adds x/y/vx/vy at runtime.
  [key: string]: unknown;
}

export interface GraphLink {
  // The server sends ids; the force sim later swaps them for node objects.
  source: number | GraphNode;
  target: number | GraphNode;
  seasons: number[];
}

export interface Graph {
  nodes: GraphNode[];
  links: GraphLink[];
}

export interface TeamRef {
  id: number;
  abbreviation: string;
  name: string;
}

export interface PlayerProfile {
  id: number;
  name: string;
  active_years: string;
  teams: TeamRef[];
  connection_count: number;
}

export interface PathResponse {
  found: boolean;
  nodes: GraphNode[];
  links: GraphLink[];
}

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`API ${res.status} for ${path}`);
  return (await res.json()) as T;
}

export function searchPlayers(q: string, limit = 8) {
  return getJSON<PlayerSearchResult[]>(
    `/players?q=${encodeURIComponent(q)}&limit=${limit}`,
  );
}

export function getProfile(id: number) {
  return getJSON<PlayerProfile>(`/players/${id}`);
}

export function getConnections(
  id: number,
  opts: { limit?: number; from?: number; to?: number } = {},
) {
  const p = new URLSearchParams();
  if (opts.limit) p.set("limit", String(opts.limit));
  if (opts.from != null) p.set("season_from", String(opts.from));
  if (opts.to != null) p.set("season_to", String(opts.to));
  const qs = p.toString();
  return getJSON<Graph>(`/players/${id}/connections${qs ? `?${qs}` : ""}`);
}

export function getPath(
  from: number,
  to: number,
  opts: { from?: number; to?: number } = {},
) {
  const p = new URLSearchParams({ from: String(from), to: String(to) });
  if (opts.from != null) p.set("season_from", String(opts.from));
  if (opts.to != null) p.set("season_to", String(opts.to));
  return getJSON<PathResponse>(`/path?${p.toString()}`);
}

// Season start-years -> a compact human span. 2015 -> "2015–16";
// [2011, 2012, 2013] -> "2011–14".
export function seasonSpan(seasons: number[]): string {
  if (!seasons.length) return "";
  const first = seasons[0];
  const last = seasons[seasons.length - 1];
  return `${first}–${String(last + 1).slice(2)}`;
}
