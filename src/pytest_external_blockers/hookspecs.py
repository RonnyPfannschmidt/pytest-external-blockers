"""Hook specifications for pytest-external-blockers."""
from __future__ import annotations

import pytest
from _pytest.config import Config


@pytest.hookspec
def pytest_external_blockers_add_jira(config: Config) -> None:
    """Register Jira servers for this session.

    Call :func:`pytest_external_blockers.add_jira` with a
    :class:`~pytest_external_blockers.JiraDefinition` and a client the host
    already built. This plugin does not choose a server or credentials.
    """
