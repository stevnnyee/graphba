"""FastAPI application — the GraphBA serving layer.

Phase 2: read-only endpoints over the graph built in Phase 1. Ingestion lives in
ingest/ and scripts/ and is entirely separate from this app.

Run locally: ``make api`` (uvicorn with auto-reload).
"""

from collections.abc import Iterator
from typing import Annotated

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from backend.database import get_connection
from backend.queries import get_player_profile, search_players
from backend.schemas import PlayerProfile, PlayerSearchResult

app = FastAPI(title="GraphBA API")

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
