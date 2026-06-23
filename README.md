# GraphBA — Six Degrees of NBA

An interactive graph of the NBA's teammate network. Every player is a node; two
players are connected if they shared a roster in the same season. Explore any
player's neighborhood, then find the shortest "six degrees" chain between any two
players in league history.

<!-- Add a screen recording here — it's the most important part of this README.
     Capture a ~10s GIF of searching a player + finding a path, save it to
     docs/demo.gif, and uncomment the line below. -->
<!-- ![GraphBA demo](docs/demo.gif) -->

> ~5,100 players · ~15,700 roster memberships · **79,488** derived teammate edges
> (seasons 1990–present).

---

## What it does

- **Explore** — start on a featured player and see their teammates as a
  force-directed graph; click any node to refocus on that player's network.
- **Find path** — pick two players and get the shortest teammate chain between
  them (e.g. *LeBron James → Richard Jefferson → Stephen Curry*), annotated with
  the seasons that connect each hop.
- **Era slider** — scope the graph and pathfinding to a year range. Connections
  only count if the players actually shared a roster *within* that window.

## Why it's interesting (the engineering)

- **Edges are derived, not fetched.** Rosters are the raw fact; every teammate
  edge is computed by self-joining roster memberships on `(team, season)` and
  aggregating which seasons created each connection. ~15.7k memberships expand to
  ~79.5k unique edges.
- **Resilient, resumable ingestion.** `nba_api` wraps `stats.nba.com`'s
  undocumented, aggressively rate-limited endpoints. The crawler uses exponential
  backoff + retries and a per-`(team, season)` ledger committed in the same
  transaction as its data, so a crash mid-crawl resumes exactly where it left off
  instead of restarting.
- **Shortest path = BFS on the full graph.** "Six degrees" is shortest path in an
  unweighted graph, so pathfinding runs breadth-first against the *complete*
  in-memory graph (loaded once at startup) — the renderer only ever draws a capped
  neighborhood, but the algorithm always sees everything, so chains stay optimal.
- **The era filter is a real semantic, not a display trick.** It's applied at
  traversal time via array-overlap on each edge's seasons, so narrowing the slider
  can genuinely change the shortest path.

## Tech stack

| Layer    | Tech |
|----------|------|
| Frontend | Next.js (App Router), TypeScript, Tailwind, `react-force-graph-2d`, Framer Motion |
| Backend  | FastAPI, Pydantic |
| Data     | PostgreSQL, `nba_api` |

## Architecture

```
nba_api ──► ingest/ (resilient crawler) ──► PostgreSQL
                                              │  rosters → derived edges
                                              ▼
                              FastAPI  (search · profile · ego-network · /path)
                                  │     full graph loaded in memory, BFS pathfinding
                                  ▼
                              Next.js  (force-graph canvas · search · era slider)
```

**API endpoints**

| Method | Route | Purpose |
|--------|-------|---------|
| `GET` | `/players?q=` | Typeahead search, ranked by prominence |
| `GET` | `/players/{id}` | Player profile (teams, connection count) |
| `GET` | `/players/{id}/connections` | Capped ego network `{nodes, links}` |
| `GET` | `/path?from=&to=` | Shortest teammate chain + per-hop seasons |

All graph endpoints share one contract: `{ nodes: [{id, name}], links: [{source, target, seasons}] }`.

## Running locally

**Prerequisites:** Docker, Python 3.9+, Node 18+.

### 1. Backend + data

```bash
cp .env.example .env          # sets DATABASE_URL
make up                       # start Postgres in Docker
pip install -r requirements.txt
make schema                   # create tables + indexes

# Build the dataset (the roster crawl is rate-limited and takes a while):
make ingest-teams
make ingest-players
make ingest-rosters           # resumable — safe to stop and re-run
make derive-edges             # compute the ~79k teammate edges
make validate                 # optional: data-quality report

make api                      # serve on http://localhost:8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev                   # http://localhost:3000
```

The frontend reads the API URL from `frontend/.env.local`
(`NEXT_PUBLIC_API_URL=http://localhost:8000`).

## Project layout

```
backend/    FastAPI app, queries, in-memory graph + BFS
ingest/     nba_api client + parsing/upsert for teams, players, rosters, edges
scripts/    runnable entry points (make targets call these)
db/          schema.sql (tables + indexes)
tests/       pytest unit tests (mocked) + opt-in live integration
frontend/    Next.js app (graph canvas, search, path panel, era slider)
```

## Testing

```bash
make test         # unit tests (mocked, no network/DB)
make test-live    # opt-in integration tests against the real NBA API
make lint         # ruff
```

## Notes

- Data starts at the 1990 season; the schema is designed to extend back to 1946.
- Seasons are stored as integer start-years (`2023` = the 2023–24 season).
- Roster data reflects season-end rosters, so some mid-season-trade connections
  are under-captured — a documented limitation of the upstream source.
