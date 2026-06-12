"""Ingest the NBA player universe into the `players` table.

Unlike teams (a static local list), players come from the live `CommonAllPlayers`
endpoint, so the fetch goes through the resilient `fetch()` wrapper. With
`is_only_current_season=0` it returns every player in NBA history (~5,100) in a
single call — full history, because pathfinding needs every node (CLAUDE.md #2).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import psycopg
from nba_api.stats.endpoints import CommonAllPlayers

from ingest.nba_client import fetch

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Player:
    """A player row, shaped exactly to the `players` table.

    Season fields are INT start-years (1990 == the 1990-91 season) and may be
    None for the rare player whose source year is blank.
    """

    id: int
    full_name: str
    first_active_season: int | None
    last_active_season: int | None


def _to_year(value: str | None) -> int | None:
    """Convert a 4-digit year string ('1990') to an int; blank/missing -> None.

    A handful of obscure players have an empty FROM_YEAR/TO_YEAR; guarding here
    keeps one bad row from crashing the whole ingest.
    """
    return int(value) if value else None


def _parse_player(row: dict) -> Player:
    # Bind by field name (not row position): stats.nba.com is undocumented and
    # may reorder columns. get_normalized_dict() already keys values by header.
    return Player(
        id=row["PERSON_ID"],
        full_name=row["DISPLAY_FIRST_LAST"],
        first_active_season=_to_year(row["FROM_YEAR"]),
        last_active_season=_to_year(row["TO_YEAR"]),
    )


def fetch_players() -> list[Player]:
    """Fetch and parse every player in NBA history.

    One atomic call: it either returns everyone or raises NBAFetchError — there
    are no partial rows to salvage, so the caller should let failures surface.
    The `season` param is required by the endpoint but ignored when
    is_only_current_season=0, so we rely on nba_api's default.
    """
    endpoint = fetch(CommonAllPlayers, league_id="00", is_only_current_season=0)
    rows = endpoint.get_normalized_dict()["CommonAllPlayers"]
    return [_parse_player(row) for row in rows]


# Idempotent upsert: identify by id, refresh attributes if the player exists.
_UPSERT_SQL = """
    INSERT INTO players (id, full_name, first_active_season, last_active_season)
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (id) DO UPDATE SET
        full_name = EXCLUDED.full_name,
        first_active_season = EXCLUDED.first_active_season,
        last_active_season = EXCLUDED.last_active_season
"""


def upsert_players(conn: psycopg.Connection, players: list[Player]) -> int:
    """Insert or update every player. Safe to run repeatedly. Returns the count."""
    rows = [
        (p.id, p.full_name, p.first_active_season, p.last_active_season)
        for p in players
    ]
    with conn.cursor() as cur:
        cur.executemany(_UPSERT_SQL, rows)
    logger.info("Upserted %d players", len(rows))
    return len(rows)
