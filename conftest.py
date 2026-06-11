"""Pytest configuration.

Lives at the project root so pytest puts the root on sys.path (making the
`ingest`/`backend` packages importable from tests). Also defines an
`integration` marker for tests that hit the real stats.nba.com, skipped unless
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


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: test makes a real network call to stats.nba.com"
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-integration"):
        return
    skip = pytest.mark.skip(reason="needs --run-integration (hits the real API)")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)
