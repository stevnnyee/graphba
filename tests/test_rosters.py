"""Unit tests for the roster crawl — fully mocked, no network, no DB."""

from unittest.mock import MagicMock, patch

import pytest

from ingest.exceptions import NBAFetchError
from ingest.rosters import (
    RosterMembership,
    crawl_rosters,
    fetch_roster,
    season_to_api_str,
    upsert_memberships,
)


@pytest.mark.parametrize(
    "year, expected",
    [
        (1990, "1990-91"),
        (2015, "2015-16"),
        (1999, "1999-00"),  # century rollover must zero-pad
        (2009, "2009-10"),
    ],
)
def test_season_to_api_str(year, expected):
    assert season_to_api_str(year) == expected


def test_fetch_roster_extracts_id_and_name_pairs():
    fake = {
        "CommonTeamRoster": [
            {"PLAYER_ID": 201575, "PLAYER": "Brandon Rush"},
            {"PLAYER_ID": 201939, "PLAYER": "Stephen Curry"},
        ]
    }
    endpoint = MagicMock()
    endpoint.get_normalized_dict.return_value = fake

    with patch("ingest.rosters.fetch", return_value=endpoint) as mock_fetch:
        result = fetch_roster(team_id=1610612744, season=2015)

    mock_fetch.assert_called_once()
    # Name is carried alongside the id so the crawl can backfill missing players.
    assert result == [(201575, "Brandon Rush"), (201939, "Stephen Curry")]


def test_upsert_memberships_executes_batch_and_returns_count():
    memberships = [
        RosterMembership(player_id=201939, team_id=1610612744, season=2015),
        RosterMembership(player_id=201575, team_id=1610612744, season=2015),
    ]
    cur = MagicMock()
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur

    count = upsert_memberships(conn, memberships)

    assert count == 2
    cur.executemany.assert_called_once()
    _sql, rows = cur.executemany.call_args.args
    assert rows == [(201939, 1610612744, 2015), (201575, 1610612744, 2015)]


@patch("ingest.rosters.record_fetch")
@patch("ingest.rosters.upsert_memberships")
@patch("ingest.rosters.backfill_players")
@patch("ingest.rosters.fetch_roster")
@patch("ingest.rosters.completed_pairs", return_value={(1, 1990)})
@patch("ingest.rosters._load_team_ids", return_value=[1, 2])
def test_crawl_skips_completed_and_continues_past_failures(
    _mock_teams,
    _mock_completed,
    mock_fetch_roster,
    mock_backfill,
    mock_upsert,
    mock_record,
):
    # plan = {1,2} x {1990,1991}; (1,1990) already done -> 3 remaining.
    # Make (2, 1990) fail to prove a failed pair is skipped but the run goes on.
    def fetch_side_effect(team_id, season):
        if (team_id, season) == (2, 1990):
            raise NBAFetchError("boom")
        return [(101, "A"), (102, "B")]

    mock_fetch_roster.side_effect = fetch_side_effect
    conn = MagicMock()

    crawl_rosters(conn, first_season=1990, last_season=1991)

    # Tried all 3 remaining (not the already-completed (1,1990)).
    assert mock_fetch_roster.call_count == 3

    # Only the 2 successes are recorded; the failed (2,1990) is NOT marked done
    # (so a later run retries it), and didn't get committed.
    recorded_pairs = [call.args[1:3] for call in mock_record.call_args_list]
    assert recorded_pairs == [(1, 1991), (2, 1991)]
    assert (2, 1990) not in recorded_pairs
    assert conn.commit.call_count == 2
    # Backfill runs for each success, never for the failed pair.
    assert mock_backfill.call_count == 2
