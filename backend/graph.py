"""In-memory graph + shortest-path search (six degrees).

The whole player graph is loaded into memory once and pathfinding runs against
the COMPLETE graph — every node, every edge (CLAUDE.md #2). Display filtering
(ego networks, caps) never touches this; only the *year* filter does, and it's
applied at traversal time so no per-window snapshots are precomputed.

The algorithm is deliberately pure: it operates on player ids and an adjacency
map, knowing nothing about names, teams, or HTTP. Enrichment (names, per-hop
team/season) is the serving layer's job, so this stays unit-testable on toy
graphs and reusable regardless of how a path is presented.
"""

from __future__ import annotations

from collections import deque

import psycopg

from backend.config import CURRENT_SEASON, MIN_SEASON

# node id -> {neighbor id -> seasons they were teammates (sorted ascending)}.
# The seasons tuple powers both the strict year filter and hop annotation.
Adjacency = dict[int, dict[int, tuple[int, ...]]]


_EDGES_SQL = "SELECT player_a_id, player_b_id, seasons FROM edges"


def build_graph(conn: psycopg.Connection) -> Adjacency:
    """Load every edge into an undirected adjacency map (both directions).

    Edges are stored canonically (a < b); pathfinding needs to traverse either
    way, so each edge is inserted under both endpoints.
    """
    graph: Adjacency = {}
    with conn.cursor() as cur:
        cur.execute(_EDGES_SQL)
        for player_a, player_b, seasons in cur:
            shared = tuple(sorted(seasons))
            graph.setdefault(player_a, {})[player_b] = shared
            graph.setdefault(player_b, {})[player_a] = shared
    return graph


def _overlaps(seasons: tuple[int, ...], window: tuple[int, int]) -> bool:
    """True if a (sorted) seasons tuple intersects the inclusive window.

    Strict semantics: an edge is usable only if the pair shared a roster within
    the window. Sorted input lets us decide with the endpoints alone.
    """
    start, end = window
    return seasons[0] <= end and seasons[-1] >= start


def _reconstruct(prev: dict[int, int | None], target: int) -> list[int]:
    """Walk predecessor links from target back to source, then reverse."""
    path = []
    node: int | None = target
    while node is not None:
        path.append(node)
        node = prev[node]
    path.reverse()
    return path


def shortest_path(
    graph: Adjacency,
    source: int,
    target: int,
    season_from: int | None = None,
    season_to: int | None = None,
) -> list[int] | None:
    """Fewest-hops path of player ids from source to target, or None.

    BFS, because every teammate hop costs the same (unweighted shortest path);
    predecessors are tracked to reconstruct the chain. With a season range, only
    edges overlapping the window are traversable (strict). Returns [source] when
    source == target, and None when either id is absent or no path exists.
    """
    if source not in graph or target not in graph:
        return None
    if source == target:
        return [source]

    window: tuple[int, int] | None = None
    if season_from is not None or season_to is not None:
        window = (
            season_from if season_from is not None else MIN_SEASON,
            season_to if season_to is not None else CURRENT_SEASON,
        )

    prev: dict[int, int | None] = {source: None}
    queue = deque([source])
    while queue:
        node = queue.popleft()
        for neighbor, seasons in graph[node].items():
            if neighbor in prev:
                continue
            if window is not None and not _overlaps(seasons, window):
                continue
            prev[neighbor] = node
            if neighbor == target:
                return _reconstruct(prev, target)
            queue.append(neighbor)
    return None
