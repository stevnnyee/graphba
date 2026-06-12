"""Pytest configuration.

Lives at the project root so pytest puts the root on sys.path (making the
`ingest`/`backend` packages importable from tests). Holds the *code* half of
the test config — the custom `--run-integration` option and the skip logic;
the declarative half (markers, testpaths) lives in pyproject.toml.

Integration tests (those hitting the real stats.nba.com) are skipped unless
`--run-integration` is passed.
"""

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="run integration tests that hit the real NBA API",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-integration"):
        return
    skip = pytest.mark.skip(reason="needs --run-integration (hits the real API)")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)
