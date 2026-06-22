"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from datetime import date

from dotenv import load_dotenv

# Load variables from a local .env file into the process environment.
# In production the environment is set directly, so a missing .env is fine.
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Copy .env.example to .env (or set the "
        "variable in your environment) before running."
    )


def _current_season_start_year(today: date | None = None) -> int:
    """NBA season start-year for a date (1990 == the 1990-91 season).

    A season tips off in October, so before October the current season is still
    the one that started the previous calendar year.
    """
    today = today or date.today()
    return today.year if today.month >= 10 else today.year - 1


# Used to render a still-active player's range as "<from>–present".
CURRENT_SEASON = _current_season_start_year()

# Earliest NBA season (1946-47 == the BAA's first year). The semantic floor for
# an open-ended era-slider lower bound; data currently starts at 1990.
MIN_SEASON = 1946
