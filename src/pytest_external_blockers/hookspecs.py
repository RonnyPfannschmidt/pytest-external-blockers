"""Hook specifications for pytest-external-blockers."""
from __future__ import annotations

import pytest

from pytest_external_blockers.clients import TrackerClient
from pytest_external_blockers.trackers import IssueTracker


@pytest.hookspec(firstresult=True)
def pytest_external_blockers_client(
    tracker: IssueTracker,
) -> TrackerClient | None:
    """Return the client for this tracker definition.

    The plugin calls this the first time a marker uses ``tracker`` and keeps
    the result on the plugin instance. Include the credentials that identify
    the client. The same URL and the same credentials share one client.
    """
