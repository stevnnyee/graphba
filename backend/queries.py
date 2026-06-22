"""Read queries that back the API endpoints.

SQL lives here, isolated from the HTTP layer, so routes stay thin and each query
is unit-testable with a mocked connection.
"""

from __future__ import annotations

import psycopg

from backend.config import CURRENT_SEASON, MIN_SEASON
from backend.schemas import (
    Graph,
    Link,
    Node,
    PlayerProfile,
    PlayerSearchResult,
    TeamRef,
)


def _format_active_years(first: int | None, last: int | None) -> str:
    """Render a player's active span for a typeahead row.

    Seasons are INT start-years in the DB (1990 == the 1990-91 season); the
    dropdown wants a human string. A player whose last season is the current one
    is still active, so it reads "present" instead of a year.
    """
    if first is None and last is None:
        return "Unknown"
    if first == last:
        return str(first)
    last_str = "present" if last is not None and last >= CURRENT_SEASON else str(last)
    return f"{first}–{last_str}"


def _escape_like(term: str) -> str:
    """Escape LIKE wildcards so a user typing % or _ can't alter the match."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# Filter with a substring ILIKE (accelerated by the pg_trgm GIN index on
# full_name), then RANK by prominence so the player a user most likely means
# leads the dropdown. Prominence = WEIGHTED degree: the total teammate-seasons a
# player accumulated (sum of shared_seasons over their edges), not just the count
# of distinct teammates. Counting teammates rewards journeymen who hop teams; the
# weighted sum rewards long tenures, which better tracks established stars. trigram
# similarity and name break ties. (similarity alone is a poor ranker: it's
# normalized by name length, so it rewards short names and buries famous players.)
#
# Edges are stored canonically (player_a_id < player_b_id), so the weight is two
# sums added — NOT `a = id OR b = id`, which can't use an index. The two sums hit
# the PK (leading player_a_id) and the edges(player_b_id) index respectively.
# COALESCE turns the NULL sum (a player with no edges) into 0. The ILIKE filter
# runs first, so this is computed only for the handful of name matches.
_SEARCH_SQL = """
    SELECT
        p.id,
        p.full_name,
        p.first_active_season,
        p.last_active_season,
        COALESCE(
            (SELECT sum(shared_seasons) FROM edges e WHERE e.player_a_id = p.id), 0
        ) + COALESCE(
            (SELECT sum(shared_seasons) FROM edges e WHERE e.player_b_id = p.id), 0
        ) AS weighted_degree
    FROM players p
    WHERE p.full_name ILIKE %(pattern)s
    ORDER BY weighted_degree DESC, similarity(p.full_name, %(q)s) DESC, p.full_name
    LIMIT %(limit)s
"""


def search_players(
    conn: psycopg.Connection, q: str, limit: int
) -> list[PlayerSearchResult]:
    """Find players whose name contains `q`, best fuzzy match first.

    The result cap is enforced here / by the route, never left to the client.
    """
    term = q.strip()
    params = {"pattern": f"%{_escape_like(term)}%", "q": term, "limit": limit}
    with conn.cursor() as cur:
        cur.execute(_SEARCH_SQL, params)
        rows = cur.fetchall()
    return [
        PlayerSearchResult(
            id=row[0],
            name=row[1],
            active_years=_format_active_years(row[2], row[3]),
        )
        for row in rows
    ]


_PROFILE_SQL = """
    SELECT id, full_name, first_active_season, last_active_season
    FROM players
    WHERE id = %(id)s
"""

# Franchises the player appeared for, deduped (a player has many membership rows
# per team across seasons). Ordered by name for a stable panel listing.
_PROFILE_TEAMS_SQL = """
    SELECT DISTINCT t.id, t.abbreviation, t.name
    FROM roster_memberships rm
    JOIN teams t ON t.id = rm.team_id
    WHERE rm.player_id = %(id)s
    ORDER BY t.name
"""

# Distinct teammates = edges incident to the player. Two equality counts (PK +
# edges(player_b_id) index), not an OR. This is the *count*; the list is /connections.
_CONNECTION_COUNT_SQL = """
    SELECT (SELECT count(*) FROM edges WHERE player_a_id = %(id)s)
         + (SELECT count(*) FROM edges WHERE player_b_id = %(id)s)
"""


def get_player_profile(
    conn: psycopg.Connection, player_id: int
) -> PlayerProfile | None:
    """Assemble one player's detail panel, or None if the id doesn't exist."""
    params = {"id": player_id}
    with conn.cursor() as cur:
        cur.execute(_PROFILE_SQL, params)
        row = cur.fetchone()
        if row is None:
            return None
        cur.execute(_PROFILE_TEAMS_SQL, params)
        teams = [TeamRef(id=t[0], abbreviation=t[1], name=t[2]) for t in cur.fetchall()]
        cur.execute(_CONNECTION_COUNT_SQL, params)
        (connection_count,) = cur.fetchone()
    return PlayerProfile(
        id=row[0],
        name=row[1],
        active_years=_format_active_years(row[2], row[3]),
        teams=teams,
        connection_count=connection_count,
    )


_FOCUS_SQL = "SELECT id, full_name FROM players WHERE id = %(id)s"

# The focus player's neighbors, strongest connection first, capped for display.
# UNION ALL of the two canonical halves (a = id, b = id) so each half uses its
# own index (PK / edges(player_b_id)) instead of an un-indexable OR. {window} is
# the strict era filter, spliced in only when a range is given: `seasons && %(window)s`
# keeps an edge iff the pair shared a roster within the window (array overlap,
# accelerated by the GIN on edges.seasons). The string is a fixed fragment, never
# user input — the year values travel as a bound param.
_CONNECTIONS_SQL = """
    SELECT nbr.neighbor_id, p.full_name, nbr.seasons
    FROM (
        SELECT player_b_id AS neighbor_id, shared_seasons, seasons
        FROM edges
        WHERE player_a_id = %(id)s {window}
        UNION ALL
        SELECT player_a_id AS neighbor_id, shared_seasons, seasons
        FROM edges
        WHERE player_b_id = %(id)s {window}
    ) nbr
    JOIN players p ON p.id = nbr.neighbor_id
    ORDER BY nbr.shared_seasons DESC, p.full_name
    LIMIT %(limit)s
"""


def get_connections(
    conn: psycopg.Connection,
    player_id: int,
    limit: int,
    season_from: int | None = None,
    season_to: int | None = None,
) -> Graph | None:
    """Capped ego network for one player as the `{nodes, links}` contract.

    Returns the focus node plus its top-`limit` teammates (by shared seasons) and
    a star of links between them. Strict era filter: when a season range is given,
    only edges whose seasons fall within it are kept. None if the focus is unknown.
    """
    params: dict = {"id": player_id, "limit": limit}
    window = ""
    if season_from is not None or season_to is not None:
        start = season_from if season_from is not None else MIN_SEASON
        end = season_to if season_to is not None else CURRENT_SEASON
        params["window"] = list(range(start, end + 1))
        # Cast to int[]: psycopg adapts a small-int list as smallint[], but the
        # column is integer[] and there's no integer[] && smallint[] operator.
        window = "AND seasons && %(window)s::int[]"

    with conn.cursor() as cur:
        cur.execute(_FOCUS_SQL, {"id": player_id})
        focus = cur.fetchone()
        if focus is None:
            return None
        cur.execute(_CONNECTIONS_SQL.format(window=window), params)
        rows = cur.fetchall()

    focus_id, focus_name = focus
    nodes = [Node(id=focus_id, name=focus_name)]
    links = []
    for neighbor_id, name, seasons in rows:
        nodes.append(Node(id=neighbor_id, name=name))
        links.append(Link(source=focus_id, target=neighbor_id, seasons=seasons))
    return Graph(nodes=nodes, links=links)
