"""Domain exceptions for GraphBA ingestion.

Named exceptions let callers catch a specific failure mode (e.g. "the API gave
up on this team, skip and continue") without also swallowing unrelated bugs.
Grow this file only when a new failure mode needs to be caught separately.
"""


class GraphBAError(Exception):
    """Base for all GraphBA domain errors."""


class NBAFetchError(GraphBAError):
    """An nba_api call failed after exhausting retries."""
