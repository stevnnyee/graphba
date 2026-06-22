"""Validate the ingested data before building the API on it.

Run from the project root:
    python -m scripts.validate_data

Read-only. Runs a battery of audit queries and prints a report so we can
confirm the graph has no *unexplained* gaps. Expected, explainable gaps (e.g.
players who retired before the 1990 roster scope have no edges) are surfaced
and separated from the ones that would signal a real problem.
"""

from backend.database import get_connection

# Roster crawl scope (CLAUDE.md): edges only exist for players active here.
FIRST_SCOPE_SEASON = 1990

_COUNT_CHECKS = [
    ("teams", "SELECT count(*) FROM teams"),
    ("players", "SELECT count(*) FROM players"),
    ("roster_memberships", "SELECT count(*) FROM roster_memberships"),
    ("edges", "SELECT count(*) FROM edges"),
    ("roster_fetch_log pairs", "SELECT count(*) FROM roster_fetch_log"),
    (
        "empty (team,season) pairs",
        "SELECT count(*) FROM roster_fetch_log WHERE player_count = 0",
    ),
]

# Players with no edge at all (appear in no shared roster).
_ZERO_EDGE_TOTAL = """
    SELECT count(*) FROM players p
    WHERE NOT EXISTS (
        SELECT 1 FROM edges e
        WHERE e.player_a_id = p.id OR e.player_b_id = p.id
    )
"""

# Zero-edge players who were still active within scope — these are NOT
# explained by the pre-1990 cutoff, so a large number here is a red flag.
_ZERO_EDGE_IN_SCOPE = """
    SELECT count(*) FROM players p
    WHERE p.last_active_season >= %s
      AND NOT EXISTS (
        SELECT 1 FROM edges e
        WHERE e.player_a_id = p.id OR e.player_b_id = p.id
    )
"""

# Players on more than one team in a single season (mid-season trades).
_MID_SEASON_TRADES = """
    SELECT count(*) FROM (
        SELECT player_id, season
        FROM roster_memberships
        GROUP BY player_id, season
        HAVING count(DISTINCT team_id) > 1
    ) t
"""

_EDGE_STATS = """
    SELECT min(shared_seasons), max(shared_seasons), round(avg(shared_seasons), 2)
    FROM edges
"""


def _scalar(cur, sql, params=()):
    cur.execute(sql, params)
    return cur.fetchone()


def main() -> None:
    with get_connection() as conn, conn.cursor() as cur:
        print("=== row counts ===")
        for label, sql in _COUNT_CHECKS:
            (n,) = _scalar(cur, sql)
            print(f"  {label:28} {n:>8}")

        print("\n=== zero-edge players (orphans) ===")
        (total,) = _scalar(cur, _ZERO_EDGE_TOTAL)
        (in_scope,) = _scalar(cur, _ZERO_EDGE_IN_SCOPE, (FIRST_SCOPE_SEASON,))
        print(f"  total with no edges          {total:>8}")
        print(
            f"  ...still active >= {FIRST_SCOPE_SEASON}      {in_scope:>8}"
            "   <- should be small; pre-1990 retirees explain the rest"
        )

        print("\n=== mid-season-trade players ===")
        (trades,) = _scalar(cur, _MID_SEASON_TRADES)
        print(f"  player-seasons on >1 team    {trades:>8}")

        print("\n=== edge shared_seasons stats ===")
        mn, mx, avg = _scalar(cur, _EDGE_STATS)
        print(f"  min={mn}  max={mx}  avg={avg}")


if __name__ == "__main__":
    main()
