"""Clients supplied for a tracker definition."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class Credentials(Protocol):
    """The identity of a tracker client: hashable and comparable.

    Two tracker definitions with the same URL and equal credentials share
    one client. The plugin never looks inside them.
    """

    def __hash__(self) -> int:
        ...


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

    credentials: Credentials
    client: IssueClient
