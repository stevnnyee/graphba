"""FastAPI application — the GraphBA serving layer.

Phase 2: read-only endpoints over the graph built in Phase 1. Ingestion lives in
ingest/ and scripts/ and is entirely separate from this app.

Run locally: ``make api`` (uvicorn with auto-reload).
"""

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Annotated, Optional

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.database import get_connection
from backend.graph import Adjacency, build_graph, shortest_path
from backend.queries import (
    fetch_player_names,
    get_connections,
    get_player_profile,
    search_players,
)
from backend.schemas import (
    Graph,
    Link,
    Node,
    PathResponse,
    PlayerProfile,
    PlayerSearchResult,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Load the full player graph into memory once, at startup.

    Pathfinding runs against the complete graph every request, so it can't be
    rebuilt per call (79k edges). It's held on app.state for the process lifetime.
    """
    with get_connection() as conn:
        app.state.graph = build_graph(conn)
    yield


app = FastAPI(title="GraphBA API", lifespan=lifespan)

# The frontend is a separate origin (Next.js on :3000 in dev, Vercel in prod).
# Tighten this allowlist to real origins before deploying (Phase 5).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def get_db() -> Iterator[psycopg.Connection]:
    """Per-request DB connection. Overridable in tests to avoid a real DB."""
    with get_connection() as conn:
        yield conn


def get_graph(request: Request) -> Adjacency:
    """The in-memory graph loaded at startup. Overridable in tests."""
    return request.app.state.graph


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/players", response_model=list[PlayerSearchResult])
def search_players_route(
    q: Annotated[str, Query(min_length=2, description="Name substring to search for")],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=25, description="Max results to return")] = 8,
) -> list[PlayerSearchResult]:
    """Typeahead player search — fuzzy, match-anywhere, best match first."""
    return search_players(conn, q, limit)


@app.get("/players/{player_id}", response_model=PlayerProfile)
def player_profile_route(
    player_id: int,
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> PlayerProfile:
    """Detail-panel view of one player. 404 if the id is unknown."""
    profile = get_player_profile(conn, player_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Player not found")
    return profile


@app.get("/players/{player_id}/connections", response_model=Graph)
def player_connections_route(
    player_id: int,
    conn: Annotated[psycopg.Connection, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200, description="Max neighbors")] = 25,
    season_from: Annotated[Optional[int], Query(description="Era window start")] = None,
    season_to: Annotated[Optional[int], Query(description="Era window end")] = None,
) -> Graph:
    """Capped ego network `{nodes, links}`; optional era window. 404 if unknown."""
    graph = get_connections(conn, player_id, limit, season_from, season_to)
    if graph is None:
        raise HTTPException(status_code=404, detail="Player not found")
    return graph


@app.get("/path", response_model=PathResponse)
def path_route(
    conn: Annotated[psycopg.Connection, Depends(get_db)],
    graph: Annotated[Adjacency, Depends(get_graph)],
    source: Annotated[int, Query(alias="from", description="Start player id")],
    target: Annotated[int, Query(alias="to", description="End player id")],
    season_from: Annotated[Optional[int], Query(description="Era window start")] = None,
    season_to: Annotated[Optional[int], Query(description="Era window end")] = None,
) -> PathResponse:
    """Shortest teammate chain between two players, with per-hop seasons.

    Returns ``found: false`` (empty chain) when no path exists or an id is
    unknown/isolated — both players existing is not a guarantee of a connection.
    """
    path = shortest_path(graph, source, target, season_from, season_to)
    if path is None:
        return PathResponse(found=False, nodes=[], links=[])

    names = fetch_player_names(conn, path)
    nodes = [Node(id=pid, name=names[pid]) for pid in path]
    links = [
        Link(
            source=path[i],
            target=path[i + 1],
            seasons=list(graph[path[i]][path[i + 1]]),
        )
        for i in range(len(path) - 1)
    ]
    return PathResponse(found=True, nodes=nodes, links=links)
