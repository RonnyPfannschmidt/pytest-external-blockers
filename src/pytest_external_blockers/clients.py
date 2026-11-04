"""Clients supplied for a tracker definition."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from pytest_external_blockers.credentials import JiraBasicAuth


class IssueClient(Protocol):
    """Reads the status of one issue."""

    def status(self, issue_key: str) -> str | None:
        """Return a status name, or ``None`` if it cannot be read."""


@dataclass(frozen=True, slots=True)
class TrackerClient:
    """A client for one tracker, with the credentials that identify it.

    The plugin instance reuses the client when another definition has the
    same URL and the same credentials.
    """

    credentials: JiraBasicAuth
    client: IssueClient
