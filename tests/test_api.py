"""Route-level tests for the FastAPI app.

The DB is replaced via a dependency override and the query layer is patched, so
these exercise routing, validation, and serialization only — no DB, no network.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app, get_db
from backend.schemas import PlayerProfile, PlayerSearchResult, TeamRef


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
