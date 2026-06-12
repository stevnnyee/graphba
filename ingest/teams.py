"""Ingest NBA teams into the `teams` table.

Teams come from nba_api's *static* table (`nba_api.stats.static.teams`), a list
bundled with the library — no HTTP call, so the resilient `fetch()` wrapper
isn't needed here. This covers the 30 current franchises; defunct/relocated
teams referenced by older rosters are backfilled during the roster crawl.
"""

import logging
from dataclasses import dataclass

import psycopg
from nba_api.stats.static import teams as static_teams

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Team:
    """A team row, shaped exactly to the `teams` table."""

    id: int
    abbreviation: str
    name: str


def fetch_teams() -> list[Team]:
    """Return all current NBA teams parsed into `Team` records.

    The static source exposes `full_name`; our schema calls that column `name`.
    """
    return [
        Team(
            id=row["id"],
            abbreviation=row["abbreviation"],
            name=row["full_name"],
        )
        for row in static_teams.get_teams()
    ]


# Idempotent upsert: identify by id (the primary key), and refresh the
# attributes if the team already exists — so a rebrand self-heals on re-run.
_UPSERT_SQL = """
    INSERT INTO teams (id, abbreviation, name)
    VALUES (%s, %s, %s)
    ON CONFLICT (id) DO UPDATE SET
        abbreviation = EXCLUDED.abbreviation,
        name = EXCLUDED.name
"""


def upsert_teams(conn: psycopg.Connection, teams: list[Team]) -> int:
    """Insert or update every team. Safe to run repeatedly. Returns the count."""
    rows = [(t.id, t.abbreviation, t.name) for t in teams]
    with conn.cursor() as cur:
        cur.executemany(_UPSERT_SQL, rows)
    logger.info("Upserted %d teams", len(rows))
    return len(rows)
