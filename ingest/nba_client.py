"""Resilient wrapper around nba_api endpoints.

Every fetch against stats.nba.com goes through `fetch()`, which adds the
defenses the raw API lacks: a polite inter-call delay, an explicit timeout, and
retry with exponential backoff. Browser-like headers are already supplied by
nba_api's own defaults, so we deliberately do NOT override them.
"""

import logging
import time
from typing import TypeVar

import requests
from nba_api.stats.endpoints._base import Endpoint

from ingest.exceptions import NBAFetchError

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30  # seconds before giving up on a hung request
REQUEST_DELAY = 0.6  # polite pause before each call, to avoid rate limits
MAX_RETRIES = 5
BACKOFF_BASE = 0.5  # seconds; the wait doubles after each failed attempt

# Only transient transport errors are worth retrying. Bad params, etc. are not.
RETRYABLE_ERRORS = (requests.exceptions.RequestException,)

E = TypeVar("E", bound=Endpoint)


def fetch(endpoint_cls: type[E], **params) -> E:
    """Call an nba_api endpoint resiliently and return the constructed object.

    nba_api performs its HTTP request in the endpoint's constructor, so the
    retry loop wraps construction. Raises after exhausting MAX_RETRIES.
    """
    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        time.sleep(REQUEST_DELAY)
        try:
            return endpoint_cls(timeout=REQUEST_TIMEOUT, **params)
        except RETRYABLE_ERRORS as err:
            last_error = err
            wait = BACKOFF_BASE * (2 ** (attempt - 1))
            logger.warning(
                "nba_api %s failed (attempt %d/%d): %s — retrying in %.1fs",
                endpoint_cls.__name__,
                attempt,
                MAX_RETRIES,
                err,
                wait,
            )
            time.sleep(wait)

    raise NBAFetchError(
        f"nba_api {endpoint_cls.__name__} failed after {MAX_RETRIES} attempts"
    ) from last_error
