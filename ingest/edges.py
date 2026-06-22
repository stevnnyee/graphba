"""Derive the player-connection graph (`edges`) from `roster_memberships`.

Pure SQL, no API. For each (team, season) roster, every pair of players is an
edge (self-join on team+season). Pairs sharing multiple rosters collapse into
one row carrying the count and sorted list of shared seasons (GROUP BY +
aggregation). The `a.player_id < b.player_id` condition drops self-pairs and
mirror duplicates, yielding one canonical row per pair — matching the
`edges` CHECK (player_a_id < player_b_id).

`edges` is a fully derived cache, so we rebuild it from scratch (TRUNCATE +
INSERT). That also removes any edge that should no longer exist if memberships
change — something an in-place upsert couldn't do.
"""

import logging

import psycopg

logger = logging.getLogger(__name__)

_DERIVE_SQL = """
    INSERT INTO edges (player_a_id, player_b_id, shared_seasons, seasons)
    SELECT
        a.player_id,
        b.player_id,
        count(DISTINCT a.season),
        array_agg(DISTINCT a.season ORDER BY a.season)
    FROM roster_memberships a
    JOIN roster_memberships b
      ON a.team_id = b.team_id
     AND a.season = b.season
     AND a.player_id < b.player_id
    GROUP BY a.player_id, b.player_id
"""


def derive_edges(conn: psycopg.Connection) -> int:
    """Rebuild `edges` from `roster_memberships`. Returns the edge count.

    TRUNCATE + INSERT run in one transaction (committed by the caller), so the
    rebuild is atomic — readers never see a half-built or empty `edges`.
    """
    with conn.cursor() as cur:
        cur.execute("TRUNCATE edges")
        cur.execute(_DERIVE_SQL)
        cur.execute("SELECT count(*) FROM edges")
        (count,) = cur.fetchone()
    logger.info("Derived %d edges", count)
    return count
