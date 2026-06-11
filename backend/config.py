"""Application configuration loaded from environment variables."""

import os

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
