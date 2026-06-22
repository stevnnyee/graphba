-- GraphBA schema. Re-runnable (IF NOT EXISTS). Season = INT start-year (2023 == 2023-24).

CREATE TABLE IF NOT EXISTS teams (
    id           BIGINT PRIMARY KEY,
    abbreviation TEXT,
    name         TEXT
);

CREATE TABLE IF NOT EXISTS players (
    id                   BIGINT PRIMARY KEY,
    full_name            TEXT NOT NULL,
    first_active_season  INT,
    last_active_season   INT
);

-- Many-to-many bridge; composite PK makes ingestion idempotent.
CREATE TABLE IF NOT EXISTS roster_memberships (
    player_id  BIGINT NOT NULL REFERENCES players(id),
    team_id    BIGINT NOT NULL REFERENCES teams(id),
    season     INT    NOT NULL,
    PRIMARY KEY (player_id, team_id, season)
);

-- Resumability ledger for the roster crawl: one row per (team, season) that
-- has been successfully fetched, written in the SAME transaction as its
-- memberships. On restart the crawl loads this set and skips what's done.
-- player_count records the result (incl. 0 for teams that didn't exist yet),
-- so "done but empty" is distinguishable from "never attempted".
CREATE TABLE IF NOT EXISTS roster_fetch_log (
    team_id      BIGINT      NOT NULL REFERENCES teams(id),
    season       INT         NOT NULL,
    player_count INT         NOT NULL,
    fetched_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (team_id, season)
);

-- Derived from roster_memberships. CHECK + PK enforce one canonical row per pair.
CREATE TABLE IF NOT EXISTS edges (
    player_a_id    BIGINT NOT NULL REFERENCES players(id),
    player_b_id    BIGINT NOT NULL REFERENCES players(id),
    shared_seasons INT    NOT NULL,
    seasons        INT[]  NOT NULL,
    PRIMARY KEY (player_a_id, player_b_id),
    CHECK (player_a_id < player_b_id)
);

-- Indexes (Task 8). Added after bulk load so ingestion isn't slowed by them.
-- Each serves a known query; the GIN on edges.seasons is deferred until a
-- season-filter query actually exists (Phase 2).

-- Typeahead search: case-insensitive substring match on player names.
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS idx_players_full_name_trgm
    ON players USING gin (full_name gin_trgm_ops);

-- Edges PK indexes player_a_id (leading col) only; this covers the other half
-- so "all edges touching player X" is fast in both directions.
CREATE INDEX IF NOT EXISTS idx_edges_player_b
    ON edges (player_b_id);

-- Speeds the Task 7 self-join (matched on team+season) and team-roster lookups.
CREATE INDEX IF NOT EXISTS idx_roster_memberships_team_season
    ON roster_memberships (team_id, season);
