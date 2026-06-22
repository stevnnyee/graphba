"""Unit tests for the in-memory graph and BFS — toy graphs, no DB."""

from unittest.mock import MagicMock

from backend.graph import build_graph, shortest_path

# A small fixed graph. Seasons are illustrative; BFS ignores them unless a window
# is given.
#   1 — 2 — 4
#   |
#   3
_GRAPH = {
    1: {2: (2000,), 3: (2010,)},
    2: {1: (2000,), 4: (2005,)},
    3: {1: (2010,)},
    4: {2: (2005,)},
    5: {},  # isolated node (known player, no teammates)
}


def test_build_graph_inserts_both_directions():
    cur = MagicMock()
    cur.__iter__.return_value = iter(
        [
            (10, 20, [2001, 2000]),  # unsorted on purpose
            (20, 30, [2005]),
        ]
    )
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur

    graph = build_graph(conn)

    # Each edge appears under both endpoints, with seasons sorted ascending.
    assert graph == {
        10: {20: (2000, 2001)},
        20: {10: (2000, 2001), 30: (2005,)},
        30: {20: (2005,)},
    }


def test_shortest_path_direct_neighbor():
    assert shortest_path(_GRAPH, 1, 3) == [1, 3]


def test_shortest_path_multi_hop():
    assert shortest_path(_GRAPH, 3, 4) == [3, 1, 2, 4]


def test_shortest_path_same_node():
    assert shortest_path(_GRAPH, 1, 1) == [1]


def test_shortest_path_unknown_node_is_none():
    assert shortest_path(_GRAPH, 1, 999) is None


def test_shortest_path_isolated_node_unreachable():
    assert shortest_path(_GRAPH, 5, 1) is None


def test_shortest_path_window_blocks_out_of_range_edge():
    # 1—2 (2000,2001), 2—3 (2010). Path 1→3 needs the 2010 edge.
    graph = {
        1: {2: (2000, 2001)},
        2: {1: (2000, 2001), 3: (2010,)},
        3: {2: (2010,)},
    }
    # Window excludes 2010 → 3 is unreachable.
    assert shortest_path(graph, 1, 3, season_from=1999, season_to=2005) is None
    # Window includes 2010 → path exists.
    assert shortest_path(graph, 1, 3, season_from=1999, season_to=2015) == [1, 2, 3]
