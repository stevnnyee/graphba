"""Ingest NBA teams into the database.

Run from the project root:
    python -m scripts.ingest_teams

Idempotent — re-running leaves `teams` in the same state.
"""

import logging

from backend.database import get_connection
from ingest.teams import fetch_teams, upsert_teams

logger = logging.getLogger(__name__)


def main() -> None:
    # Config (level + format) lives at the entry point, not in library modules.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    teams = fetch_teams()
    logger.info("Fetched %d teams from the static source", len(teams))

    with get_connection() as conn:
        upsert_teams(conn, teams)


if __name__ == "__main__":
    main()
