"""Pydantic response models — the locked JSON contracts the API serves.

Two deliberately *separate* shapes (a change to one must not ripple into the
other):

- The **graph contract** (`Node`, `Link`, `Graph`) — what every graph-shaped
  endpoint (profile, connections, path) will return. `Link` uses
  ``source``/``target`` — the generic graph-theory terms, which are also what
  React Force Graph consumes — rather than the DB's
  ``player_a_id``/``player_b_id``. The wire format is shaped for its consumer
  (the renderer / graph domain), not for storage; the column names stay an
  internal detail.
- The **search result** (`PlayerSearchResult`) — a lightweight typeahead row,
  intentionally NOT the graph `Node`. A dropdown only needs enough to render and
  disambiguate, and it fires on nearly every keystroke, so it carries the
  minimum.
"""

from pydantic import BaseModel


class PlayerSearchResult(BaseModel):
    """One row in the typeahead dropdown."""

    id: int
    name: str
    # Human display string, e.g. "1990–2007" or "2016–present". Disambiguates
    # same-named players (Gary Payton vs Gary Payton II) by era.
    active_years: str


class TeamRef(BaseModel):
    """A franchise a player appeared for, for the profile panel."""

    id: int
    abbreviation: str
    name: str


class PlayerProfile(BaseModel):
    """The detail-panel view of one player.

    Its own richer shape (not the graph `Node`): the panel renders a single
    player and has room for attributes + summary scalars. The teammate *list*
    is deliberately NOT here — that's the `/connections` endpoint's job; profile
    answers "who is this player?", connections answers "who are they linked to?".
    """

    id: int
    name: str
    active_years: str
    teams: list[TeamRef]
    connection_count: int  # distinct teammates; the list itself lives in /connections


class Node(BaseModel):
    """A player as a graph node."""

    id: int
    name: str


class Link(BaseModel):
    """An edge between two players who shared a roster.

    ``source``/``target`` (not ``player_a_id``/``player_b_id``): the contract
    speaks the graph domain's language, which the renderer also speaks.
    """

    source: int
    target: int
    seasons: list[int]


class Graph(BaseModel):
    """The locked ``{nodes, links}`` payload for all graph endpoints."""

    nodes: list[Node]
    links: list[Link]
