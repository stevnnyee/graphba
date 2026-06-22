"""Derive the edges graph from roster memberships.

Run from the project root:
    python -m scripts.derive_edges

Pure SQL, no API. Idempotent: rebuilds `edges` from scratch each run, so it's
safe to re-run any time the roster data changes.
"""

import logging

from backend.database import get_connection
from ingest.edges import derive_edges

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    with get_connection() as conn:
        derive_edges(conn)


if __name__ == "__main__":
    main()
