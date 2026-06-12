"""Ingest the NBA player universe into the database.

Run from the project root:
    python -m scripts.ingest_players

Idempotent — re-running leaves `players` in the same state. Fetches all players
in one live API call; if that call fails after retries it raises NBAFetchError
and the script exits (no partial rows to salvage).
"""

import logging

from backend.database import get_connection
from ingest.players import fetch_players, upsert_players

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    players = fetch_players()
    logger.info("Fetched %d players from CommonAllPlayers", len(players))

    with get_connection() as conn:
        upsert_players(conn, players)


if __name__ == "__main__":
    main()
