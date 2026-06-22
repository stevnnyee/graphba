"""Unit tests for the read-query layer — fully mocked, no DB."""

from unittest.mock import MagicMock

from backend.config import CURRENT_SEASON
from backend.queries import (
    _escape_like,
    _format_active_years,
    get_player_profile,
    search_players,
)
from backend.schemas import PlayerProfile, PlayerSearchResult, TeamRef


def test_format_active_years_retired_player():
    assert _format_active_years(1990, 2007) == "1990–2007"


def test_format_active_years_active_player_reads_present():
    assert _format_active_years(2016, CURRENT_SEASON) == "2016–present"


def test_format_active_years_single_season():
    assert _format_active_years(2015, 2015) == "2015"


def test_format_active_years_unknown_when_both_missing():
    assert _format_active_years(None, None) == "Unknown"


def test_escape_like_neutralizes_wildcards():
    # A user typing % or _ must not turn the query into a wildcard match.
    assert _escape_like("a%b_c") == r"a\%b\_c"


def test_search_players_wraps_substring_and_maps_rows():
    # Trailing column is `weighted_degree` (ranking signal); the mapper ignores it.
    rows = [
        (201939, "Stephen Curry", 2009, CURRENT_SEASON, 412),
        (101108, "Eddy Curry", 2001, 2012, 137),
    ]
    cur = MagicMock()
    cur.fetchall.return_value = rows
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur

    results = search_players(conn, "  curry ", limit=8)

    # Query is parameterized: substring pattern, raw term for ranking, the cap.
    _sql, params = cur.execute.call_args.args
    assert params == {"pattern": "%curry%", "q": "curry", "limit": 8}

    assert results == [
        PlayerSearchResult(
            id=201939, name="Stephen Curry", active_years="2009–present"
        ),
        PlayerSearchResult(id=101108, name="Eddy Curry", active_years="2001–2012"),
    ]


def test_get_player_profile_assembles_panel():
    cur = MagicMock()
    # Three executes in order: player row, then teams, then connection count.
    cur.fetchone.side_effect = [
        (201939, "Stephen Curry", 2009, CURRENT_SEASON),  # player
        (412,),  # connection count
    ]
    cur.fetchall.return_value = [(1610612744, "GSW", "Golden State Warriors")]
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur

    profile = get_player_profile(conn, 201939)

    assert profile == PlayerProfile(
        id=201939,
        name="Stephen Curry",
        active_years="2009–present",
        teams=[
            TeamRef(id=1610612744, abbreviation="GSW", name="Golden State Warriors")
        ],
        connection_count=412,
    )


def test_get_player_profile_returns_none_when_missing():
    cur = MagicMock()
    cur.fetchone.return_value = None
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur

    assert get_player_profile(conn, 999999) is None
    # Short-circuits after the first lookup — no teams/count queries.
    cur.fetchall.assert_not_called()
