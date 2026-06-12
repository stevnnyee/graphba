"""Crawl NBA team rosters into the database — the core data-layer ingest.

Run from the project root:
    python -m scripts.ingest_rosters

Long-running (~1,000 live API calls). Safe to interrupt and re-run: it commits
after each (team, season) and resumes from `roster_fetch_log`, so a restart
skips everything already fetched.
"""

import logging

from backend.database import get_connection
from ingest.rosters import crawl_rosters

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    with get_connection() as conn:
        crawl_rosters(conn)


if __name__ == "__main__":
    main()
