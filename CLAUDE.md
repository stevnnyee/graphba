# GraphBA

Interactive NBA player connection graph — "Six Degrees of NBA separation." Every NBA player is a node; two players are connected if they were teammates on the same roster in the same season. Users explore the network, click a player to highlight connections, and find the shortest path between any two players.

## Tech Stack

- **Frontend:** Next.js (App Router), Tailwind, React Force Graph (force-directed viz), Framer Motion
- **Backend:** FastAPI, PostgreSQL
- **Data:** NBA API via the `nba_api` Python library
- **Deploy (planned):** frontend on Vercel; backend + Postgres on Railway/Render/Fly

## Core Concept & Edge Definition

- **Node** = an NBA player.
- **Edge** = two players shared a roster in the same season. Edges are *derived* from rosters, not fetched directly. For each team-season roster, every pair of players on it is an edge.
- Edges carry metadata: which seasons/teams created the connection (`shared_seasons`, `seasons`). This metadata is what powers the year filter and the per-hop story in pathfinding.
- A player can be on multiple teams in one season (mid-season trades) — player↔season↔team is many-to-many.

## Architecture Decisions (settled)

### 1. Chosen product direction: Option 2 — "Era Slider"

We evaluated three coherent products for taming the "full graph is too big to render" problem (~5,000 players, hundreds of thousands of edges; React Force Graph degrades past a few thousand nodes):

- **Option 1 — Ego Explorer:** start on one player, click to expand their neighborhood; plus a two-player path finder. Full history. Lowest cost. No "whole league" wow moment.
- **Option 2 — Era Slider (CHOSEN):** Option 1 plus a year-range filter that scopes the graph. UI defaults to the current season; widening the range unlocks cross-era connections. Full history, user-constrained. Low–medium cost. The slider is the single best interaction and the marquee feature.
- **Option 3 — Full Hairball:** render the whole league at once via WebGL with aggressive node culling. Highest cost, and culling deletes the journeyman role-players who bridge eras — which *breaks pathfinding*. Rejected as a starting architecture; only viable later as an optional, clearly-labeled gimmick mode.

**Why Option 2:** it's Option 1 with the one feature that makes GraphBA memorable, at marginal extra cost — because the season metadata needed for the filter is already stored on each edge. Build approach: implement Option 1's core, design the data model so the year filter is a drop-in, ship Option 2.

### 2. Full-graph-in-memory rule for pathfinding (NON-NEGOTIABLE)

Pathfinding ALWAYS runs against the **complete** graph (every node, every edge), loaded into memory. The renderer never draws the whole graph — but the algorithm must see all of it, or six-degrees chains become wrong/suboptimal. **Filter aggressively for *display*, never for *computation*.** The view is an ego network; the computation is the full graph.

### 3. Distinction between three strategies (don't conflate)

- **Ego network** = navigation strategy (show only the neighborhood around a focus player).
- **Year filter** = semantic strategy (constrain which connections count).
- **Aggressive filtering** = rendering strategy (cull nodes so the renderer survives). Reserved for an optional hairball mode only; never applied to pathfinding.

### 4. Shortest path = BFS

Six degrees is shortest path in an **unweighted** graph — every teammate hop costs the same. Use BFS (not Dijkstra). Optimize to **bidirectional BFS** for dense graphs once basic BFS is correct. Track predecessors to reconstruct the path, then annotate each hop with the connecting team+season.

### 5. Year-filter semantics (to finalize before Phase 2)

Decide whether the filter means "teammates *within* this window" (strict — both players in-range) or "any connection that existed by this year" (cumulative). Strict is more intuitive for a slider. Leaning strict; confirm before building the API.

## Biggest Risk: nba_api rate limiting

`nba_api` is a thin wrapper over `stats.nba.com`'s undocumented, **aggressively rate-limited and flaky** endpoints. This — not data modeling — is the primary engineering risk in the data layer. Mitigations: exponential backoff, retries, custom headers, polite delays (~0.6s+) between calls, and **idempotent, resumable ingestion** so a crash mid-run doesn't restart from scratch. Keep raw roster data so edges can be re-derived without re-fetching.

## Data Model (draft schema)

- `players(id, full_name, first_active_season, last_active_season, …)`
- `teams(id, abbreviation, name)`
- `roster_memberships(player_id, team_id, season)` — the raw fact, fetched from the API
- `edges(player_a_id, player_b_id, shared_seasons int, seasons jsonb)` — derived; store with `a < b` to dedupe. Season metadata must be queryable (range column or GIN index), not buried in unindexed JSON.

Generate edges in a separate pass *after* all rosters are ingested — not during fetch.

## Historical Scope

Full history is the data-model target. Start ingestion with a smaller window (e.g. 1990+) to iterate fast, with the schema designed to extend backward to 1946. Default UI view is the current season.

## Phase Breakdown

Detailed tasks, sub-steps, and live progress live in **[PLAN.md](./PLAN.md)** — the execution tracker. Summary:

1. **Data Layer** — fetch, model, store every player + teammate relationship from nba_api. *(Current focus.)*
2. **Backend/API Layer** — FastAPI endpoints for search, profile, capped ego networks, and pathfinding; optional `season_from`/`season_to`; cached; locked node/edge JSON contract.
3. **Graph/Algorithm Layer** — full graph in memory; BFS → bidirectional BFS; path reconstruction with hop metadata; year filter at traversal time; explicit unreachable handling.
4. **Frontend Layer** — Next.js App Router; graph canvas + search bar + path panel; ego-network default; click-to-expand; animated path mode; 2D; year slider.
5. **Polish + Deployment** — UX states, mobile fallback, explainer; frontend on Vercel, backend+DB on Railway/Render/Fly; CORS + env hygiene.

CLAUDE.md holds the durable "what & why"; PLAN.md holds the evolving "what's done & next." Keep this section a summary — update PLAN.md, not here, as tasks progress.

## Conventions

- Production-grade code, no toy examples; follow language/framework conventions; types/interfaces where supported; small single-purpose functions; comments only where intent isn't obvious.
- Git: the user handles commits/pushes manually — do not commit without being asked.
