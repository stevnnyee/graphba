"""Unit tests for team ingestion — fully mocked, no network, no DB."""

from unittest.mock import MagicMock, patch

from ingest.teams import Team, fetch_teams, upsert_teams


def test_fetch_teams_maps_full_name_to_name():
    fake_rows = [
        {
            "id": 1,
            "abbreviation": "ATL",
            "full_name": "Atlanta Hawks",
            "city": "Atlanta",
        },
    ]
    with patch("ingest.teams.static_teams.get_teams", return_value=fake_rows):
        result = fetch_teams()

    # full_name is mapped onto `name`; extra keys (city, …) are dropped.
    assert result == [Team(id=1, abbreviation="ATL", name="Atlanta Hawks")]


def test_upsert_teams_executes_batch_and_returns_count():
    teams = [
        Team(id=1, abbreviation="ATL", name="Atlanta Hawks"),
        Team(id=2, abbreviation="BOS", name="Boston Celtics"),
    ]
    cur = MagicMock()
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur

    count = upsert_teams(conn, teams)

    assert count == 2
    cur.executemany.assert_called_once()
    _sql, rows = cur.executemany.call_args.args
    assert rows == [(1, "ATL", "Atlanta Hawks"), (2, "BOS", "Boston Celtics")]
