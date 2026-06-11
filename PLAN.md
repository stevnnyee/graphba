# GraphBA — Execution Plan

Living roadmap and progress tracker. For architecture decisions and the "why," see [CLAUDE.md](./CLAUDE.md). This file tracks *what's done and what's next*.

Status legend: `[ ]` todo · `[~]` in progress · `[x]` done

---

## Phase 1 — Data Layer  `[~]`

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

### Task 4 — Ingest teams  `[ ]`
Populate `teams`. Smallest real ingestion — the end-to-end pipeline test (wrapper → parse → upsert → DB).
**Done when:** `teams` populated; counts/abbreviations match reality; re-run is idempotent.

### Task 5 — Ingest the player universe  `[ ]`
Populate `players` from `CommonAllPlayers`, including active-season ranges.
**Done when:** expected player count for scope; spot-checks correct; idempotent.

### Task 6 — Ingest roster memberships (core crawl)  `[ ]`
For each team × season in scope, fetch roster → `roster_memberships`. Heavy, rate-limited, **resumable** (track completed (team, season) pairs, skip on restart). Keep raw data permanently.
**Done when:** every in-scope (team, season) fetched; mid-run kill + restart resumes cleanly; a known roster spot-checks correct.

### Task 7 — Derive edges from roster memberships  `[ ]`
Separate pass (no API): for each roster, emit every player pair (`a < b`), aggregating `shared_seasons` + connecting seasons/teams.
**Done when:** `edges` populated; known teammates have an edge with correct seasons; non-overlapping players have none; re-run is deterministic.

### Task 8 — Index + data-quality validation  `[ ]`
Add indexes (name search; season-range/GIN on edges; join indexes on memberships). Run validation: edge counts, orphans, zero-edge players, mid-season-trade players under multiple teams.
**Done when:** target queries are fast; validation numbers sane with no unexplained gaps.

---

## Phase 2 — Backend / API Layer  `[ ]`
FastAPI endpoints: `GET /players?q=` (typeahead), `GET /players/{id}`, `GET /players/{id}/connections?depth=` (capped ego network), `GET /path?from=&to=` (ordered nodes + team/season per hop). Optional `season_from`/`season_to` on relevant endpoints. Cache deterministic results. Lock JSON contract: `{nodes: [{id, name, …}], links: [{source, target, seasons}]}`.
**Decision to finalize first:** year-filter semantics — strict (both in-range) vs cumulative. Leaning strict.

## Phase 3 — Graph / Algorithm Layer  `[ ]`
Full graph in memory. BFS → bidirectional BFS. Path reconstruction with hop metadata. Year filter applied at traversal time (skip out-of-range edges; no pre-built snapshots). Handle disconnected/unreachable pairs explicitly.

## Phase 4 — Frontend Layer  `[ ]`
Next.js App Router. Graph canvas (client component) + search/command bar + path panel. Default to a featured player's ego network. Click node → fetch connections, merge, highlight/dim. Path mode → `/path`, render only the chain, animate (Framer Motion), label links with team/season. 2D over 3D. Year range slider. Light state.

## Phase 5 — Polish + Deployment  `[ ]`
Loading/empty/error states, node sizing by degree, color/legend, mobile fallback, "how it works" explainer. Frontend → Vercel; backend+DB → Railway/Render/Fly (watch cold starts on first `/path`). One-time seed vs scheduled refresh. Lock CORS; never hardcode the API URL.
