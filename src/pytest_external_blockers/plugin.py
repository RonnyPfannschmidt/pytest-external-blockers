"""Pytest wiring: markers, hooks, and session state for tracker clients."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import NamedTuple

import pytest
from _pytest.config import Config
from _pytest.skipping import evaluate_condition

from pytest_external_blockers import hookspecs
from pytest_external_blockers.clients import Credentials
from pytest_external_blockers.clients import IssueClient
from pytest_external_blockers.clients import TrackerClient
from pytest_external_blockers.outcomes import block
from pytest_external_blockers.outcomes import BLOCKED
from pytest_external_blockers.outcomes import Blocked
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
        self._clients: dict[tuple[str, Credentials], IssueClient] = {}
        self._by_tracker: dict[IssueTracker, IssueClient | None] = {}
        self._status: dict[tuple[IssueTracker, str], str | None] = {}

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


class Block(NamedTuple):
    """The result of evaluate_block_marks()."""

    reason: str


def evaluate_block_marks(item: pytest.Item) -> Block | None:
    """Evaluate block and blockif marks, returning Block if triggered."""
    for mark in item.iter_markers(name="blockif"):
        if "condition" not in mark.kwargs:
            conditions = mark.args
        else:
            conditions = (mark.kwargs["condition"],)

        # Unconditional.
        if not conditions:
            reason = mark.kwargs.get("reason", "")
            return Block(reason)

        # If any of the conditions are true.
        for condition in conditions:
            result, reason = evaluate_condition(item, mark, condition)
            if result:
                return Block(reason)

    for mark in item.iter_markers(name="block"):
        if "reason" in mark.kwargs:
            reason = mark.kwargs["reason"]
        elif mark.args:
            reason = mark.args[0]
        else:
            reason = "unconditional skip"
        return Block(reason)

    return None


def pytest_addhooks(pluginmanager: pytest.PytestPluginManager) -> None:
    pluginmanager.add_hookspecs(hookspecs)


def pytest_configure(config: Config):
    config.addinivalue_line(
        "markers", "block(reason): mark a test as blocked from execution"
    )

    config.addinivalue_line(
        "markers",
        "blockif(*conditions, reason): mark a test as blocked from execution",
    )
    config.addinivalue_line(
        "markers",
        (
            "blocked_by(tracker, issue, *, category): "
            "block when an external issue is open"
        ),
    )
    config.pluginmanager.register(ExternalBlockersPlugin(config), SESSION_NAME)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item: pytest.Item):
    # Check if block or blockif are specified as pytest marks

    # todo: use stash
    item.__dict__["_should_block"] = should_block = evaluate_block_marks(item)
    if should_block is not None:
        block(should_block.reason)
    _block_from_tracker(item)


def _block_from_tracker(item: pytest.Item) -> None:
    plugin = item.config.pluginmanager.get_plugin(SESSION_NAME)
    if not isinstance(plugin, ExternalBlockersPlugin):
        return
    use = plugin.blocking_use(item)
    if use is None:
        return
    item.user_properties.extend(_use_properties(use))
    block(plugin.block_reason(use))


def _use_properties(use: BlockedBy) -> list[tuple[str, str]]:
    return [
        ("external-blocker-category", use.category.value),
        ("external-blocker-issue", use.issue),
        ("external-blocker-tracker", use.tracker.name),
    ]


@pytest.hookimpl(tryfirst=True)
def pytest_report_teststatus(report):
    if report.outcome == BLOCKED:
        return BLOCKED, "B", BLOCKED.upper()


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    excinfo = call.excinfo
    if excinfo is not None and excinfo.errisinstance(Blocked):
        rep.outcome = BLOCKED

        evalblock = getattr(item, "_should_block", None)
        if evalblock is not None and type(rep.longrepr) is tuple:
            # taken from _pytest.skipping, patch failure location to item name
            filename, line, reason = rep.longrepr
            filename, line = item.location[:2]
            rep.longrepr = filename, line, reason
