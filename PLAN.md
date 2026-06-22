# GraphBA — Execution Plan

Living roadmap and progress tracker. For architecture decisions and the "why," see [CLAUDE.md](./CLAUDE.md). This file tracks *what's done and what's next*.

Status legend: `[ ]` todo · `[~]` in progress · `[x]` done

---

## Phase 1 — Data Layer  `[x]`  ✅ COMPLETE

Fetch, model, and store every player + teammate relationship from nba_api.

### Task 1 — Stand up Postgres + connection config  `[x]`
Postgres running locally + an env-driven Python connection + a script that proves it with `SELECT 1`.

- `[x]` 1.1 Run Postgres in Docker (via `docker-compose.yml` → `docker compose up -d`)
- `[x]` 1.2 Verify the DB is alive — connect with `psql` inside the container
- `[x]` 1.3 Install Python deps into `.venv` (`psycopg`, `python-dotenv`)
- `[x]` 1.4 Env config — `.env` (gitignored) + `.env.example` (committed) with `DATABASE_URL`
- `[x]` 1.5 Connection module — `backend/database.py` reads env and hands out a connection
- `[x]` 1.6 Healthcheck script — `scripts/healthcheck.py`, run via `make healthcheck`

**Done when:** a Python script connects using only env-driven credentials and returns `SELECT 1`. Nothing hardcoded. ✅ **DONE**

Common commands are in the `Makefile` — run `make help`.

### Task 2 — Lock the schema and create the tables  `[x]`  ✅ DONE
Create `players`, `teams`, `roster_memberships`, `edges`. Still structure only — no data.
Schema in `db/schema.sql`, applied via `make schema`. Season = INT start-year.

**Gating decision — season representation:** store as **integer start-year** (`2023` = the 2023–24 season), *not* the `"2023-24"` string. The era slider does numeric range filters constantly (`WHERE season BETWEEN x AND y`), which is clean/indexable on an int; the pretty `"2023-24"` is derived at display time.

- `[x]` 2.1 Confirm season representation (int start-year) — gating decision
- `[x]` 2.2 Write `db/schema.sql` — the four tables:
  - `teams(id PK, abbreviation, name)` — `id` is the NBA team id
  - `players(id PK, full_name, first_active_season, last_active_season)` — `id` is the NBA player id
  - `roster_memberships(player_id, team_id, season)` — **composite PK** on all three (makes ingestion idempotent); FKs to players/teams
  - `edges(player_a_id, player_b_id, shared_seasons, seasons INT[])` — PK `(player_a_id, player_b_id)`, `CHECK (player_a_id < player_b_id)` to enforce dedupe; `seasons` as `INT[]` of start-years (GIN-indexable later, not JSON)
- `[x]` 2.3 Add a `make schema` target — pipes `db/schema.sql` into the container's `psql` (repeatable, version-controlled schema)
- `[x]` 2.4 Apply & verify — `\dt` lists the tables; dummy inserts confirmed FKs + `a<b` CHECK fire; dummies deleted

**Done when:** all four tables exist with chosen types + keys; a dummy row inserts/queries in each; re-applying the schema is safe. (Indexes deferred to Task 8.)

### Task 3 — nba_api spike + resilient request wrapper  `[x]`  ✅ DONE
Confirm nba_api access and build the one wrapper every later fetch goes through. This is the project's biggest risk (CLAUDE.md), de-risked early on a tiny scale before the Task 6 crawl. All fetch logic lives in an `ingest/` package.

- `[x]` 3.1 Install `nba_api` into `.venv`; snapshot to requirements.txt
- `[x]` 3.2 Spike — confirmed access (Lakers 2023-24 → 18 players); raw row shape observed
- `[x]` 3.3 Build the resilient wrapper (`ingest/nba_client.py`) — polite delay (~0.6s), retry with exponential backoff, explicit timeout. **Headers: do NOT override nba_api's defaults** — overriding them caused read-timeouts; nba_api already sends correct browser headers.
- `[x]` 3.4 Stress-test — live integration test (`make test-live`, opt-in) fetches 5 real rosters through the wrapper; passes.
- `[x]` 3.5 Unit tests (`tests/test_nba_client.py`, pytest) — mocked: returns on success, retries transient errors, backs off exponentially (0.5→1→2→4→8s), raises after MAX_RETRIES, doesn't retry non-network errors. `make test` (unit) / `make test-live` (integration).

**Done when:** ✅ 5 mocked unit tests + 5 live integration tests pass (`make test`, `make test-live`). Wrapper survives real flaky API via retry/backoff.

### Task 4 — Ingest teams  `[x]`  ✅ DONE
Populate `teams`. Smallest real ingestion — first parse → upsert → DB pipeline.

**Source decision:** use nba_api's **static** team table (`nba_api.stats.static.teams`) — a local list, no HTTP call, so the resilient wrapper isn't used here. Covers the 30 current franchises. Defunct/relocated teams referenced by older rosters are backfilled during the Task 6 crawl (they'd otherwise fail `roster_memberships`' FK to `teams`).

- `[x]` 4.1 Decide source (static list — gating decision above)
- `[x]` 4.2 `ingest/teams.py` — `fetch_teams()` parses static rows into `Team(id, abbreviation, name)`; maps source `full_name` → `name`
- `[x]` 4.3 `upsert_teams(conn, teams)` — idempotent `INSERT … ON CONFLICT (id) DO UPDATE`, batched via `executemany`
- `[x]` 4.4 Runner `scripts/ingest_teams.py` + `make ingest-teams`; logging level/format configured at the entry point
- `[x]` 4.5 Verified: `count(*)` == 30; abbreviations match; ran twice, count stayed 30, no error
- `[x]` 4.6 Unit tests (`tests/test_teams.py`) — parse mapping + batched upsert (mocked, no DB/network)

**Done when:** `teams` populated; counts/abbreviations match reality; re-run is idempotent.

### Task 5 — Ingest the player universe  `[x]`  ✅ DONE
Populate `players` from `CommonAllPlayers`, including active-season ranges. First ingest that hits the **live API through the resilient wrapper**.

**Decisions (settled):** ingest **all ~5,100 players** (`is_only_current_season=0`) — full history, no scope filter; players is one cheap call and pathfinding needs every node (scope limiting is a Task 6 / roster concern). `FROM_YEAR`/`TO_YEAR` are plain 4-digit year strings (`'1990'`) → `int()`, blank → `None`. Parse via `get_normalized_dict()` (bind by field name, not position). Single atomic fetch → on `NBAFetchError`, let the runner crash (no partial rows to salvage).

- `[x]` 5.1 Spike `CommonAllPlayers` — confirmed 5,126 rows, field names, year format (plain 4-digit strings)
- `[x]` 5.2 `ingest/players.py` — `Player` dataclass + `fetch_players()` through the wrapper; year→int with blank→None guard
- `[x]` 5.3 `upsert_players(conn, players)` — idempotent `ON CONFLICT (id) DO UPDATE`, batched
- `[x]` 5.4 Runner `scripts/ingest_players.py` + `make ingest-players`
- `[x]` 5.5 Verified: 5,126 players; LeBron 2544 = 2003→2025; 0 NULL years; ran twice, count stayed 5,126
- `[x]` 5.6 Unit tests (`tests/test_players.py`) — parse + year conversion (incl. blank→None) + batched upsert

**Done when:** expected player count for scope; spot-checks correct; idempotent.

### Task 6 — Ingest roster memberships (core crawl)  `[x]`  ✅ DONE
For each team × season in scope, fetch roster → `roster_memberships`. Heavy, rate-limited, **resumable**. Keep raw data permanently.

**Design (settled):** crawl the 30 current franchise ids × seasons 1990–2025 (ids persist across relocations → covers franchise history, no FK gap in scope). **Resumability = idempotency + a done-set:** a `roster_fetch_log(team_id, season, player_count, fetched_at)` ledger, written one row per success **in the same transaction** as the memberships and committed per-pair. Restart loads the set and skips done pairs (`remaining = plan - completed`); a pair that fails after retries is logged + skipped (not recorded → retried later). `player_count` distinguishes "done but empty" (expansion team pre-founding) from "never attempted".

- `[x]` 6.1 Scope + season format — 1990–2025; `season_to_api_str` (1990→"1990-91", century rollover handled)
- `[x]` 6.2 Resumability design — `roster_fetch_log` ledger + per-pair commit (gating, settled)
- `[x]` 6.3 `fetch_roster(team_id, season)` — through `fetch()`, parses `PLAYER_ID`s
- `[x]` 6.4 `upsert_memberships` — composite-PK `ON CONFLICT DO NOTHING`; `record_fetch` breadcrumb; `completed_pairs` loader
- `[x]` 6.5 `crawl_rosters` loop — skip done, fetch→upsert→record→commit, skip-and-continue on `NBAFetchError`
- `[x]` 6.6 Runner `scripts/ingest_rosters.py` + `make ingest-rosters`
- `[x]` 6.7 Ran crawl to completion: 1080/1080 pairs, 15,655 memberships; mid-run kill twice (Ctrl-C + FK crash) both resumed cleanly; 24 empty pairs (pre-founding expansion seasons)
- `[x]` 6.8 Unit tests (`tests/test_rosters.py`) — season format, parse, batch upsert, skip-completed + error-continue, backfill-on-success

**Note — data-quality finding:** `CommonAllPlayers` is not exhaustive; 4 players appeared on rosters but were missing from it. The `roster_memberships` → `players` FK *caught* this (loud crash, not silent corruption). Fixed with `backfill_players` (upsert id+name from the roster, `ON CONFLICT DO NOTHING` to preserve existing season data). Players grew 5,126 → 5,130.

**Done when:** every in-scope (team, season) fetched; mid-run kill + restart resumes cleanly; a known roster spot-checks correct.

### Task 7 — Derive edges from roster memberships  `[x]`  ✅ DONE
Separate pass (no API): self-join `roster_memberships` on (team_id, season), emit every player pair, aggregate into `edges`.

**Design (settled):** one `INSERT … SELECT` — self-join on `team_id` AND `season` (= teammates); `a.player_id < b.player_id` drops self-pairs + mirror dupes (canonical order, matches the CHECK); `GROUP BY (a,b)` with `count(DISTINCT season)` → `shared_seasons` and `array_agg(DISTINCT season ORDER BY season)` → `seasons`. `edges` is a fully derived cache → **rebuild via TRUNCATE + INSERT** (atomic, drops stale edges).

- `[x]` 7.1 Query design (self-join + `a<b` dedupe + GROUP BY aggregation)
- `[x]` 7.2 `ingest/edges.py` — `derive_edges(conn)` rebuilds + returns count
- `[x]` 7.3 Runner `scripts/derive_edges.py` + `make derive-edges`
- `[x]` 7.4 Verified: 79,488 edges; Curry↔Thompson = 13 seasons (2011–2023); Curry's top teammate Green = 14 seasons; 0 rows violate `a<b` ordering
- `[x]` 7.5 Unit test (`tests/test_edges.py`) — TRUNCATE-before-INSERT contract + count (SQL correctness proven by 7.4 spot-checks)

**Done when:** `edges` populated; known teammates have an edge with correct seasons; non-overlapping players have none; re-run is deterministic.

### Task 8 — Index + data-quality validation  `[x]`  ✅ DONE
Add indexes for known queries; run a read-only data-quality audit.

**Indexes (in `schema.sql`, applied via `make schema`):** `pg_trgm` GIN on `players.full_name` (typeahead substring search); `edges(player_b_id)` (PK only covers the leading `player_a_id`, so this makes "all edges touching X" fast in both directions); `roster_memberships(team_id, season)` (speeds the Task 7 self-join + roster lookups). **Deferred:** GIN on `edges.seasons` — pathfinding loads the graph in memory and no season-filter query exists yet; add it in Phase 2 when one does (don't build unused indexes).

- `[x]` 8.1 Decide index set (above); defer `edges.seasons` GIN
- `[x]` 8.2 Add indexes + `pg_trgm` extension to `schema.sql` (CREATE … IF NOT EXISTS, re-runnable)
- `[x]` 8.3 `scripts/validate_data.py` + `make validate` — counts, zero-edge players (split in-scope vs pre-1990), mid-season trades, edge stats
- `[x]` 8.4 Applied + validated. Numbers sane; both surprises explained (below). No unexplained gaps.

**Done when:** target queries are fast; validation numbers sane with no unexplained gaps. ✅

**Validation findings (documented, both = data-source characteristics, not bugs):**
- **2,131 zero-edge players total** — pre-1990 retirees (in `players` from full history, never on a 1990+ roster). Expected.
- **233 zero-edge players active ≥ 1990** — all have **0 memberships**; all fringe/two-way/recent players (e.g. Kennedy Chandler) in `CommonAllPlayers` but never on a standard `CommonTeamRoster`. Harmless isolated nodes; hide at display time.
- **Only 1 mid-season-trade player-season** — `CommonTeamRoster` returns **season-end rosters**, so traded players appear once (final team). The schema/derivation handle multi-team correctly, but the source under-reports trades → graph **misses some trade-driven teammate edges**. *Possible future enhancement:* derive per-season team affiliations from game logs to recover them. Out of scope for Phase 1.

---

## ✅ Phase 1 COMPLETE — final data: 30 teams · 5,130 players · 15,655 memberships · 79,488 edges. Indexed + validated.

---

## Phase 2 — Backend / API Layer  `[~]`
FastAPI endpoints: `GET /players?q=` (typeahead), `GET /players/{id}`, `GET /players/{id}/connections?depth=` (capped ego network), `GET /path?from=&to=` (ordered nodes + team/season per hop). Optional `season_from`/`season_to` on relevant endpoints. Cache deterministic results. Lock JSON contract: `{nodes: [{id, name, …}], links: [{source, target, seasons}]}`.
**Decision to finalize first:** year-filter semantics — strict (both in-range) vs cumulative. Leaning strict. *Does not block search or the contract shape — only `/connections` + `/path` traversal. Resolve before building those.*

### Task 1 — JSON contract + player search endpoint  `[x]`
Lock the wire shapes, then ship the first (cheapest, foundational) endpoint.

**Design decisions (settled):**
- **Graph contract** uses `links: [{source, target, seasons}]` — generic graph-theory terms (also what React Force Graph consumes), not the DB's `player_a_id`/`player_b_id`. Wire format is shaped for the consumer; column names stay internal. The `player_a_id → source` mapping happens once, in the serializer.
- **Search result is its own lightweight shape**, NOT the graph node: `{id, name, active_years}`. Decoupled (a node-shape change must not bloat the typeahead), and cheap (fires per keystroke).
- **Disambiguator = era**, formatted `active_years` ("1990–2007", "2016–present"). Distinguishes same-named players (Gary Payton vs Gary Payton II). Seasons are INT start-years in the DB → formatted to a display string in the backend serializer (`CURRENT_SEASON` → "present").
- **Matching** = substring `ILIKE '%q%'` (accelerated by the Phase 1 `pg_trgm` GIN index) for "match-anywhere, Google-like" feel; **ranked** by `similarity(full_name, q) DESC` so the best match leads. LIKE wildcards in user input are escaped.
- **Guards:** `q` min length 2 (no match-everything on one keystroke); server-side `limit` (default 8, cap 25) — the cap is the API's call, not the client's.

- `[x]` 1.1 Lock graph contract — `Node`/`Link`/`Graph` (`backend/schemas.py`)
- `[x]` 1.2 Lock search result shape — `PlayerSearchResult` (`backend/schemas.py`)
- `[x]` 1.3 FastAPI app skeleton — `backend/main.py` (app, CORS placeholder, `/health`), `make api`
- `[x]` 1.4 Query layer — `search_players()` + `_format_active_years()` (`backend/queries.py`)
- `[x]` 1.5 `GET /players?q=&limit=` route — validation + dependency-injected DB connection
- `[x]` 1.6 Tests — `tests/test_queries.py` (mapping + formatting + wildcard escape) and `tests/test_api.py` (routing, validation, serialization)
- `[x]` 1.7 Installed deps (`fastapi`, `uvicorn[standard]`, `httpx`) → `make freeze`; `make test`/`lint` green; live smoke `GET /players?q=curry` returns prominence-ranked rows (Stephen Curry #1)

**Done when:** `make test` green; `make api` serves `GET /players?q=curry` returning ranked `{id, name, active_years}` rows from the real DB. ✅

**Ranking note (settled):** filter = substring `ILIKE` (pg_trgm-accelerated); rank = **weighted degree** = `sum(shared_seasons)` over a player's edges (teammate-seasons), tie-broken by trigram `similarity` then name. Plain `count(*)` degree was rejected — it rewards journeymen (Seth Curry > Stephen Curry); the weighted sum favors tenure. Computed per-request (ILIKE filters to a handful first). *Future optimization if typeahead slows: materialize as a `players.weighted_degree` column refreshed by `derive_edges`.*

### Task 2 — Player profile endpoint  `[~]`
`GET /players/{id}` — the detail-panel view of one player. 404 on unknown id.

**Design decisions (settled):**
- **Profile gets its own richer shape** (`PlayerProfile`), NOT the graph `Node`: the panel renders one player and has room for attributes + summary scalars.
- **Boundary — profile vs `/connections`:** profile answers *"who is this player?"* → attributes + scalars (`id`, `name`, `active_years`, `teams`, `connection_count`). The teammate *list* (and its graph payload) is `/connections`' job — different question, different size class, different shape. "Top teammates" deferred to `/connections?limit=N` to avoid overlap.
- `connection_count` = plain distinct-teammate count (incident edges), the panel's "N connections" scalar — distinct from search's *weighted* degree (a ranking signal, not a displayed number).
- `teams` = `TeamRef{id, abbreviation, name}` deduped from `roster_memberships`.

- `[x]` 2.1 `PlayerProfile` + `TeamRef` schemas (`backend/schemas.py`)
- `[x]` 2.2 Query layer — `get_player_profile()` returns `PlayerProfile | None` (`backend/queries.py`)
- `[x]` 2.3 `GET /players/{player_id}` route — 404 via `HTTPException` when None
- `[x]` 2.4 Tests — query (assembly + None-on-missing) and route (serialization, 404, non-int id → 422)
- `[ ]` 2.5 Run `make test`/`format`/`lint`; live smoke `GET /players/201939` (Stephen Curry)

**Done when:** `make test` green; `make api` serves `GET /players/{id}` returning the profile, 404 on unknown id.

### Task 3 — Capped ego-network endpoint  `[ ]`  *(needs year-filter semantics finalized)*
`GET /players/{id}/connections` — returns the graph contract `{nodes, links}` for the player's neighborhood, capped for display.

### Task 4 — Pathfinding endpoint  `[ ]`
`GET /path?from=&to=` — ordered nodes + per-hop team/season. Thin wrapper over Phase 3's BFS.

## Phase 3 — Graph / Algorithm Layer  `[ ]`
Full graph in memory. BFS → bidirectional BFS. Path reconstruction with hop metadata. Year filter applied at traversal time (skip out-of-range edges; no pre-built snapshots). Handle disconnected/unreachable pairs explicitly.

## Phase 4 — Frontend Layer  `[ ]`
Next.js App Router. Graph canvas (client component) + search/command bar + path panel. Default to a featured player's ego network. Click node → fetch connections, merge, highlight/dim. Path mode → `/path`, render only the chain, animate (Framer Motion), label links with team/season. 2D over 3D. Year range slider. Light state.

## Phase 5 — Polish + Deployment  `[ ]`
Loading/empty/error states, node sizing by degree, color/legend, mobile fallback, "how it works" explainer. Frontend → Vercel; backend+DB → Railway/Render/Fly (watch cold starts on first `/path`). One-time seed vs scheduled refresh. Lock CORS; never hardcode the API URL.
