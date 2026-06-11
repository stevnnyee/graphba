"""Integration tests that hit the real stats.nba.com.

Skipped by default. Run explicitly with:
    pytest --run-integration
or:
    make test-live
"""

import pytest
from nba_api.stats.endpoints import CommonTeamRoster

from ingest.nba_client import fetch

# A few real team ids to exercise repeated calls through the wrapper.
TEAM_IDS = [
    1610612747,  # Lakers
    1610612738,  # Celtics
    1610612744,  # Warriors
    1610612748,  # Heat
    1610612752,  # Knicks
]
SEASON = "2023-24"


@pytest.mark.integration
@pytest.mark.parametrize("team_id", TEAM_IDS)
def test_live_roster_fetch_returns_players(team_id):
    roster = fetch(CommonTeamRoster, team_id=team_id, season=SEASON)
    rows = roster.get_dict()["resultSets"][0]["rowSet"]
    assert len(rows) > 0
