"""Pytest plugin instance that owns clients and cached issue status."""
from __future__ import annotations

import logging
from dataclasses import dataclass

import pytest
from _pytest.config import Config

from pytest_external_blockers.clients import IssueClient
from pytest_external_blockers.clients import TrackerClient
from pytest_external_blockers.credentials import JiraBasicAuth
from pytest_external_blockers.trackers import Category
from pytest_external_blockers.trackers import IssueTracker
from pytest_external_blockers.trackers import parse_category

log = logging.getLogger(__name__)

SESSION_NAME = "external_blockers_session"


@dataclass(frozen=True, slots=True)
class BlockedBy:
    """One marker use of a tracker definition."""

    tracker: IssueTracker
    issue: str
    category: Category


class ExternalBlockersPlugin:
    """Session state for tracker clients.

    Definitions stay as constants. This instance asks
    :func:`pytest_external_blockers_client` the first time a definition is
    used, then keeps the client and any status it has read.
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._clients: dict[tuple[str, JiraBasicAuth], IssueClient] = {}
        self._by_tracker: dict[IssueTracker, IssueClient | None] = {}
        self._auth: dict[IssueTracker, JiraBasicAuth] = {}
        self._status: dict[tuple[IssueTracker, str], str | None] = {}

    def credentials_for(self, tracker: IssueTracker) -> JiraBasicAuth | None:
        """Return the credentials stored for ``tracker``."""
        return self._auth.get(tracker)

    def client_for(self, tracker: IssueTracker) -> IssueClient | None:
        """Return the shared client for ``tracker``, asking the hook once."""
        if tracker in self._by_tracker:
            return self._by_tracker[tracker]
        provided = self._ask(tracker)
        client = None if provided is None else self._share(tracker, provided)
        self._by_tracker[tracker] = client
        return client

    def status_of(self, tracker: IssueTracker, issue_key: str) -> str | None:
        """Return the cached lowercase status, reading it at most once."""
        key = (tracker, _issue_key(issue_key))
        if key not in self._status:
            self._status[key] = self._read_status(tracker, key[1])
        return self._status[key]

    def issue_blocks(self, tracker: IssueTracker, issue_key: str) -> bool:
        """Return whether ``issue_key`` on ``tracker`` is still blocking."""
        status = self.status_of(tracker, issue_key)
        if status is None:
            return True
        return status not in tracker.not_blocking

    def blocking_use(self, item: pytest.Item) -> BlockedBy | None:
        """Return the first ``blocked_by`` mark whose issue still blocks."""
        for mark in item.iter_markers("blocked_by"):
            use = _parse_blocked_by(mark)
            if self.issue_blocks(use.tracker, use.issue):
                return use
        return None

    def block_reason(self, use: BlockedBy) -> str:
        """Return the blocked message for ``use``."""
        status = self.status_of(use.tracker, use.issue)
        shown = status if status is not None else "unreadable"
        name = use.tracker.name
        return f"{name} {use.issue} is {shown} ({use.category.value})"

    def _share(
        self,
        tracker: IssueTracker,
        provided: TrackerClient,
    ) -> IssueClient:
        self._auth[tracker] = provided.credentials
        key = (tracker.url, provided.credentials)
        cached = self._clients.get(key)
        if cached is not None:
            return cached
        self._clients[key] = provided.client
        return provided.client

    def _ask(self, tracker: IssueTracker) -> TrackerClient | None:
        hook_name = "pytest_external_blockers_client"
        ask = getattr(self._config.hook, hook_name, None)
        if ask is None:
            return None
        try:
            result = ask(tracker=tracker)
        except Exception:
            log.warning(
                "client hook failed for tracker %s",
                tracker.name,
                exc_info=True,
            )
            return None
        if result is None:
            return None
        if not isinstance(result, TrackerClient):
            raise TypeError(
                "pytest_external_blockers_client must return a TrackerClient"
            )
        return result

    def _read_status(
        self,
        tracker: IssueTracker,
        issue_key: str,
    ) -> str | None:
        client = self.client_for(tracker)
        if client is None:
            log.warning(
                "no client for tracker %s; treating %s as blocking",
                tracker.name,
                issue_key,
            )
            return None
        try:
            raw = client.status(issue_key)
        except Exception:
            log.warning(
                "could not read %s on %s",
                issue_key,
                tracker.name,
                exc_info=True,
            )
            return None
        if not isinstance(raw, str):
            return None
        text = raw.strip().lower()
        return text or None


def _parse_blocked_by(mark: pytest.Mark) -> BlockedBy:
    if not mark.args or not isinstance(mark.args[0], IssueTracker):
        raise pytest.UsageError("blocked_by requires an IssueTracker")
    tracker = mark.args[0]
    issue = mark.args[1] if len(mark.args) > 1 else mark.kwargs.get("issue")
    if not isinstance(issue, str):
        raise pytest.UsageError("blocked_by requires an issue key")
    if "category" not in mark.kwargs:
        raise pytest.UsageError("blocked_by requires category")
    category = parse_category(mark.kwargs["category"])
    return BlockedBy(tracker, _issue_key(issue), category)


def _issue_key(issue_key: str) -> str:
    if not isinstance(issue_key, str):
        kind = type(issue_key).__name__
        raise TypeError(f"issue key must be str, not {kind}")
    key = issue_key.strip()
    if not key:
        raise ValueError("issue key is empty")
    return key
