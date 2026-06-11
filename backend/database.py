"""Database connection helpers.

Centralizes how the rest of the codebase obtains a Postgres connection so
connection details live in exactly one place.
"""

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg

from backend.config import DATABASE_URL


@contextmanager
def get_connection() -> Iterator[psycopg.Connection]:
    """Yield a Postgres connection, committing on success and closing always.

    Usage:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
    """
    conn = psycopg.connect(DATABASE_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
