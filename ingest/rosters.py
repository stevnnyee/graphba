"""Crawl team rosters into `roster_memberships` — the core, resumable ingest.

For every (team, season) in scope we fetch the roster via `CommonTeamRoster`
and store one membership row per player. The crawl is ~1,000 live calls, so it
is built to survive interruption:

- **Resumable:** after each pair succeeds, a breadcrumb is written to
  `roster_fetch_log` in the SAME transaction as the memberships, then committed.
  A restart loads the completed set and skips it (see `crawl_rosters`).
- **Idempotent:** re-fetching a pair is harmless (composite-PK upsert).
- **Fault-tolerant:** a pair that fails after retries is logged and skipped; it
  isn't marked done, so a later run retries it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import psycopg
from nba_api.stats.endpoints import CommonTeamRoster

from ingest.exceptions import NBAFetchError
from ingest.nba_client import fetch

logger = logging.getLogger(__name__)

# Scope: 1990-91 through 2025-26. Designed to extend back toward 1946 later.
FIRST_SEASON = 1990
LAST_SEASON = 2025


@dataclass(frozen=True)
class RosterMembership:
    """One player on one team in one season — a row of `roster_memberships`."""

    player_id: int
    team_id: int
    season: int


def season_to_api_str(year: int) -> str:
    """Convert an INT start-year to the API's season string: 1990 -> '1990-91'."""
    return f"{year}-{(year + 1) % 100:02d}"


def fetch_roster(team_id: int, season: int) -> list[tuple[int, str]]:
    """Fetch one team-season roster; return (player_id, full_name) pairs.

    The name is carried so the crawl can backfill players that exist on rosters
    but are missing from CommonAllPlayers (the two endpoints disagree on a few
    obscure historical players). Goes through the resilient `fetch()` gateway,
    so it raises NBAFetchError if the API can't be reached after retries.
    """
    endpoint = fetch(
        CommonTeamRoster, team_id=team_id, season=season_to_api_str(season)
    )
    rows = endpoint.get_normalized_dict()["CommonTeamRoster"]
    return [(row["PLAYER_ID"], row["PLAYER"]) for row in rows]


# Composite PK (player_id, team_id, season) IS the whole row, so a conflict has
# nothing to update — DO NOTHING makes re-inserts idempotent no-ops.
_UPSERT_MEMBERSHIPS_SQL = """
    INSERT INTO roster_memberships (player_id, team_id, season)
    VALUES (%s, %s, %s)
    ON CONFLICT (player_id, team_id, season) DO NOTHING
"""

_RECORD_FETCH_SQL = """
    INSERT INTO roster_fetch_log (team_id, season, player_count)
    VALUES (%s, %s, %s)
    ON CONFLICT (team_id, season) DO UPDATE SET
        player_count = EXCLUDED.player_count,
        fetched_at = now()
"""

# Backfill players seen on a roster but missing from CommonAllPlayers, so the
# memberships FK always resolves. DO NOTHING preserves the richer season-range
# data of players we already have; new rows get name only (seasons stay NULL).
_BACKFILL_PLAYERS_SQL = """
    INSERT INTO players (id, full_name)
    VALUES (%s, %s)
    ON CONFLICT (id) DO NOTHING
"""


def upsert_memberships(
    conn: psycopg.Connection, memberships: list[RosterMembership]
) -> int:
    """Insert all membership rows for a roster. Idempotent. Returns the count."""
    rows = [(m.player_id, m.team_id, m.season) for m in memberships]
    with conn.cursor() as cur:
        cur.executemany(_UPSERT_MEMBERSHIPS_SQL, rows)
    return len(rows)


def backfill_players(conn: psycopg.Connection, roster: list[tuple[int, str]]) -> None:
    """Ensure every roster player exists in `players` (FK safety net)."""
    with conn.cursor() as cur:
        cur.executemany(_BACKFILL_PLAYERS_SQL, roster)


def record_fetch(
    conn: psycopg.Connection, team_id: int, season: int, player_count: int
) -> None:
    """Mark a (team, season) pair as fetched — the resumability breadcrumb."""
    with conn.cursor() as cur:
        cur.execute(_RECORD_FETCH_SQL, (team_id, season, player_count))


def completed_pairs(conn: psycopg.Connection) -> set[tuple[int, int]]:
    """Load every (team_id, season) already fetched, so the crawl can skip them."""
    with conn.cursor() as cur:
        cur.execute("SELECT team_id, season FROM roster_fetch_log")
        return {(team_id, season) for team_id, season in cur.fetchall()}


def _load_team_ids(conn: psycopg.Connection) -> list[int]:
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM teams ORDER BY id")
        return [row[0] for row in cur.fetchall()]


def crawl_rosters(
    conn: psycopg.Connection,
    first_season: int = FIRST_SEASON,
    last_season: int = LAST_SEASON,
) -> None:
    """Crawl every (team, season) not already done, committing after each.

    Skips pairs in `roster_fetch_log` (resume), and on a per-pair fetch failure
    logs and continues so one bad roster can't sink the whole run.
    """
    team_ids = _load_team_ids(conn)
    completed = completed_pairs(conn)
    seasons = range(first_season, last_season + 1)
    plan = [(team_id, season) for team_id in team_ids for season in seasons]
    remaining = [pair for pair in plan if pair not in completed]

    logger.info(
        "crawl plan: %d pairs total, %d already done, %d to fetch",
        len(plan),
        len(completed),
        len(remaining),
    )

    for team_id, season in remaining:
        try:
            roster = fetch_roster(team_id, season)
        except NBAFetchError:
            logger.warning(
                "skipping team %s season %s — failed after retries", team_id, season
            )
            continue

        memberships = [
            RosterMembership(player_id=pid, team_id=team_id, season=season)
            for pid, _name in roster
        ]
        # Backfill players → memberships → breadcrumb, all in one transaction:
        # the FK always resolves and we never "save but don't mark" (or vice versa).
        backfill_players(conn, roster)
        upsert_memberships(conn, memberships)
        record_fetch(conn, team_id, season, len(roster))
        conn.commit()

        logger.info("team %s season %s: %d players", team_id, season, len(roster))
