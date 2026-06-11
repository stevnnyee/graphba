"""Unit tests for the resilient wrapper — fully mocked, no network.

We simulate nba_api endpoints failing (or succeeding) and assert the wrapper's
retry / backoff / timeout logic behaves correctly.
"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from ingest import nba_client
from ingest.nba_client import (
    MAX_RETRIES,
    REQUEST_TIMEOUT,
    fetch,
)


@pytest.fixture(autouse=True)
def no_sleep():
    """Patch out real sleeping; yield the mock so tests can inspect the waits."""
    with patch.object(nba_client.time, "sleep") as mock_sleep:
        yield mock_sleep


def fake_endpoint(*side_effects):
    """A stand-in for an nba_api endpoint class whose constructor follows side_effects.

    An exception in the list is raised on that call; any other value is returned.
    """
    cls = MagicMock(name="FakeEndpoint")
    cls.__name__ = "FakeEndpoint"
    cls.side_effect = side_effects
    return cls


def test_returns_on_first_success():
    sentinel = object()
    cls = fake_endpoint(sentinel)

    result = fetch(cls, team_id=1)

    assert result is sentinel
    cls.assert_called_once_with(timeout=REQUEST_TIMEOUT, team_id=1)


def test_retries_transient_error_then_succeeds():
    sentinel = object()
    cls = fake_endpoint(
        requests.exceptions.ConnectionError(),
        requests.exceptions.Timeout(),
        sentinel,
    )

    result = fetch(cls)

    assert result is sentinel
    assert cls.call_count == 3  # failed twice, succeeded on the third


def test_raises_after_max_retries():
    cls = fake_endpoint(*[requests.exceptions.ConnectionError()] * MAX_RETRIES)

    with pytest.raises(RuntimeError):
        fetch(cls)

    assert cls.call_count == MAX_RETRIES


def test_non_retryable_error_propagates_immediately():
    cls = fake_endpoint(ValueError("bad parameter"))

    with pytest.raises(ValueError):
        fetch(cls)

    assert cls.call_count == 1  # not retried


def test_backoff_grows_exponentially(no_sleep):
    cls = fake_endpoint(*[requests.exceptions.ConnectionError()] * MAX_RETRIES)

    with pytest.raises(RuntimeError):
        fetch(cls)

    # sleep calls alternate: polite delay, then backoff, per attempt.
    waits = [call.args[0] for call in no_sleep.call_args_list]
    backoff_waits = waits[1::2]
    assert backoff_waits == [0.5, 1.0, 2.0, 4.0, 8.0]
