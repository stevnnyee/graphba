"""Unit tests for player ingestion — fully mocked, no network, no DB."""

from unittest.mock import MagicMock, patch

from ingest.players import Player, fetch_players, upsert_players


def test_fetch_players_parses_fields_and_converts_years():
    fake = {
        "CommonAllPlayers": [
            {
                "PERSON_ID": 2544,
                "DISPLAY_FIRST_LAST": "LeBron James",
                "FROM_YEAR": "2003",
                "TO_YEAR": "2024",
            },
            # Blank years must become None, not crash on int("").
            {
                "PERSON_ID": 1,
                "DISPLAY_FIRST_LAST": "Ghost Player",
                "FROM_YEAR": "",
                "TO_YEAR": "",
            },
        ]
    }
    endpoint = MagicMock()
    endpoint.get_normalized_dict.return_value = fake

    with patch("ingest.players.fetch", return_value=endpoint) as mock_fetch:
        result = fetch_players()

    mock_fetch.assert_called_once()
    assert result == [
        Player(
            id=2544,
            full_name="LeBron James",
            first_active_season=2003,
            last_active_season=2024,
        ),
        Player(
            id=1,
            full_name="Ghost Player",
            first_active_season=None,
            last_active_season=None,
        ),
    ]


def test_upsert_players_executes_batch_and_returns_count():
    players = [
        Player(id=1, full_name="A", first_active_season=2000, last_active_season=2010),
        Player(id=2, full_name="B", first_active_season=None, last_active_season=None),
    ]
    cur = MagicMock()
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur

    count = upsert_players(conn, players)

    assert count == 2
    cur.executemany.assert_called_once()
    _sql, rows = cur.executemany.call_args.args
    assert rows == [(1, "A", 2000, 2010), (2, "B", None, None)]
