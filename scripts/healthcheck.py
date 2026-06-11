"""Verify the database connection works end to end.

Run from the project root:
    python -m scripts.healthcheck
"""

from backend.database import get_connection


def main() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            result = cur.fetchone()

    if result == (1,):
        print("OK — database connection works (SELECT 1 returned 1).")
    else:
        raise SystemExit(f"Unexpected result from SELECT 1: {result!r}")


if __name__ == "__main__":
    main()
