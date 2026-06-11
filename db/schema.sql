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

-- Derived from roster_memberships. CHECK + PK enforce one canonical row per pair.
CREATE TABLE IF NOT EXISTS edges (
    player_a_id    BIGINT NOT NULL REFERENCES players(id),
    player_b_id    BIGINT NOT NULL REFERENCES players(id),
    shared_seasons INT    NOT NULL,
    seasons        INT[]  NOT NULL,
    PRIMARY KEY (player_a_id, player_b_id),
    CHECK (player_a_id < player_b_id)
);
