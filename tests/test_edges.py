"""Unit tests for edge derivation — mocked DB.

The SQL's *correctness* is proven against real data (spot-checking known
teammates after `make derive-edges`); these tests pin the function's contract:
a clean rebuild (TRUNCATE before INSERT) and returning the row count.
"""

from unittest.mock import MagicMock

from ingest.edges import derive_edges


def test_derive_edges_truncates_before_insert_and_returns_count():
    cur = MagicMock()
    cur.fetchone.return_value = (42,)
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur

    count = derive_edges(conn)

    assert count == 42
    executed = [call.args[0].strip() for call in cur.execute.call_args_list]
    # Clean rebuild: TRUNCATE must come first, then the INSERT … SELECT.
    assert executed[0].startswith("TRUNCATE")
    assert any(stmt.startswith("INSERT INTO edges") for stmt in executed)
