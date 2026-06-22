"""Route-level tests for the FastAPI app.

The DB is replaced via a dependency override and the query layer is patched, so
these exercise routing, validation, and serialization only — no DB, no network.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app, get_db, get_graph
from backend.schemas import (
    Graph,
    Link,
    Node,
    PlayerProfile,
    PlayerSearchResult,
    TeamRef,
)


@pytest.fixture
def client():
    # Override the per-request DB dependency with a throwaway connection; the
    # query function is patched per-test, so the connection is never used.
    app.dependency_overrides[get_db] = lambda: MagicMock()
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_search_returns_serialized_results(client):
    fake = [
        PlayerSearchResult(id=201939, name="Stephen Curry", active_years="2009–present")
    ]
    with patch("backend.main.search_players", return_value=fake) as mock_search:
        resp = client.get("/players", params={"q": "curry"})

    assert resp.status_code == 200
    assert resp.json() == [
        {"id": 201939, "name": "Stephen Curry", "active_years": "2009–present"}
    ]
    # Default cap is applied when the client omits `limit`.
    _conn, q, limit = mock_search.call_args.args
    assert (q, limit) == ("curry", 8)


def test_search_rejects_too_short_query(client):
    assert client.get("/players", params={"q": "c"}).status_code == 422


def test_search_rejects_oversized_limit(client):
    assert (
        client.get("/players", params={"q": "curry", "limit": 1000}).status_code == 422
    )


def test_profile_returns_serialized_player(client):
    fake = PlayerProfile(
        id=201939,
        name="Stephen Curry",
        active_years="2009–present",
        teams=[
            TeamRef(id=1610612744, abbreviation="GSW", name="Golden State Warriors")
        ],
        connection_count=412,
    )
    with patch("backend.main.get_player_profile", return_value=fake):
        resp = client.get("/players/201939")

    assert resp.status_code == 200
    assert resp.json() == {
        "id": 201939,
        "name": "Stephen Curry",
        "active_years": "2009–present",
        "teams": [
            {"id": 1610612744, "abbreviation": "GSW", "name": "Golden State Warriors"}
        ],
        "connection_count": 412,
    }


def test_profile_404_when_player_missing(client):
    with patch("backend.main.get_player_profile", return_value=None):
        resp = client.get("/players/999999")
    assert resp.status_code == 404


def test_profile_rejects_non_integer_id(client):
    # Path param is typed int → FastAPI validates before the handler runs.
    assert client.get("/players/abc").status_code == 422


def test_connections_returns_graph(client):
    fake = Graph(
        nodes=[
            Node(id=201939, name="Stephen Curry"),
            Node(id=203110, name="Draymond Green"),
        ],
        links=[Link(source=201939, target=203110, seasons=[2012, 2013])],
    )
    with patch("backend.main.get_connections", return_value=fake) as mock_conn:
        resp = client.get(
            "/players/201939/connections",
            params={"season_from": 2012, "season_to": 2014},
        )

    assert resp.status_code == 200
    assert resp.json() == {
        "nodes": [
            {"id": 201939, "name": "Stephen Curry"},
            {"id": 203110, "name": "Draymond Green"},
        ],
        "links": [{"source": 201939, "target": 203110, "seasons": [2012, 2013]}],
    }
    # Era window is passed through to the query layer.
    _conn, player_id, limit, season_from, season_to = mock_conn.call_args.args
    assert (player_id, limit, season_from, season_to) == (201939, 25, 2012, 2014)


def test_connections_404_when_player_missing(client):
    with patch("backend.main.get_connections", return_value=None):
        resp = client.get("/players/999999/connections")
    assert resp.status_code == 404


def test_connections_rejects_oversized_limit(client):
    assert (
        client.get("/players/1/connections", params={"limit": 9999}).status_code == 422
    )


def test_path_found_enriches_chain(client):
    # Toy graph supplies the per-hop seasons; shortest_path/names are patched.
    graph = {1: {2: (2010, 2011)}, 2: {1: (2010, 2011), 3: (2015,)}, 3: {2: (2015,)}}
    app.dependency_overrides[get_graph] = lambda: graph
    with (
        patch("backend.main.shortest_path", return_value=[1, 2, 3]),
        patch("backend.main.fetch_player_names", return_value={1: "A", 2: "B", 3: "C"}),
    ):
        resp = client.get("/path", params={"from": 1, "to": 3})

    assert resp.status_code == 200
    assert resp.json() == {
        "found": True,
        "nodes": [
            {"id": 1, "name": "A"},
            {"id": 2, "name": "B"},
            {"id": 3, "name": "C"},
        ],
        "links": [
            {"source": 1, "target": 2, "seasons": [2010, 2011]},
            {"source": 2, "target": 3, "seasons": [2015]},
        ],
    }


def test_path_not_found_is_explicit(client):
    app.dependency_overrides[get_graph] = lambda: {}
    with patch("backend.main.shortest_path", return_value=None):
        resp = client.get("/path", params={"from": 1, "to": 999})

    assert resp.status_code == 200
    assert resp.json() == {"found": False, "nodes": [], "links": []}


def test_path_requires_from_and_to(client):
    app.dependency_overrides[get_graph] = lambda: {}
    assert client.get("/path", params={"from": 1}).status_code == 422
