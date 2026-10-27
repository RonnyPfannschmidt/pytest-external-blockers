"""Register a Jira server and the client a host already built."""
from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit
from urllib.parse import urlunsplit

from _pytest.config import Config
from pytest import StashKey

log = logging.getLogger(__name__)

_DEFAULT_NOT_BLOCKING = frozenset({"done", "rejected", "closed"})


class JiraStatus(Protocol):
    """Status object exposed by ``jira.JIRA`` issue resources."""

    name: str


class JiraFields(Protocol):
    """Fields object exposed by ``jira.JIRA`` issue resources."""

    status: JiraStatus


class JiraIssueView(Protocol):
    """The part of a Jira issue this plugin reads."""

    fields: JiraFields


class JiraClient(Protocol):
    """A client that can fetch one issue.

    ``jira.JIRA`` satisfies this. The host builds it (including a client
    already held by the process) and passes it to :func:`add_jira`.
    """

    def issue(self, key: str) -> JiraIssueView:
        """Return the issue for ``key``."""


class JiraAlreadyRegistered(ValueError):
    """``add_jira`` was called twice for one server URL."""

    def __init__(self, url: str) -> None:
        self.url = url
        super().__init__(f"jira already registered for {url}")


class JiraNotRegistered(LookupError):
    """``get_jira`` found no server for this URL."""

    def __init__(self, url: str) -> None:
        self.url = url
        super().__init__(f"no jira registered for {url}")


@dataclass(frozen=True, slots=True, init=False)
class JiraDefinition:
    """One Jira server this session may ask about issues.

    ``url`` is the server the host selected. ``not_blocking`` is the status
    names (compared case-insensitively) that mean the issue does not block.
    The default is ``done``, ``rejected``, and ``closed``.
    """

    url: str
    not_blocking: frozenset[str]

    def __init__(
        self,
        url: str,
        not_blocking: Iterable[str] = _DEFAULT_NOT_BLOCKING,
    ) -> None:
        object.__setattr__(self, "url", normalize_jira_url(url))
        object.__setattr__(
            self,
            "not_blocking",
            normalize_statuses(not_blocking),
        )


@dataclass(frozen=True, slots=True)
class RegisteredJira:
    """A definition plus the client that talks to that server."""

    definition: JiraDefinition
    client: JiraClient

    def issue_blocks(self, issue_key: str) -> bool:
        """Return whether ``issue_key`` is still blocking.

        An issue the client cannot read is blocking.
        """
        key = _issue_key(issue_key)
        status = _read_status(self, key)
        if status is None:
            return True
        return status not in self.definition.not_blocking


_REGISTERED: StashKey[dict[str, RegisteredJira]] = StashKey()


def add_jira(
    config: Config,
    definition: JiraDefinition,
    client: JiraClient,
) -> RegisteredJira:
    """Remember ``client`` as the way to talk to ``definition``'s server."""
    if client is None:
        raise TypeError("jira client is required")
    registered = RegisteredJira(definition, client)
    registry = _registry(config)
    url = registered.definition.url
    if url in registry:
        raise JiraAlreadyRegistered(url)
    registry[url] = registered
    return registered


def get_jira(config: Config, url: str) -> RegisteredJira:
    """Return the registration for ``url``."""
    normalized = normalize_jira_url(url)
    registry = config.stash.get(_REGISTERED, None)
    if registry is None or normalized not in registry:
        raise JiraNotRegistered(normalized)
    return registry[normalized]


def _registry(config: Config) -> dict[str, RegisteredJira]:
    found = config.stash.get(_REGISTERED, None)
    if found is not None:
        return found
    registry: dict[str, RegisteredJira] = {}
    config.stash[_REGISTERED] = registry
    return registry


def normalize_jira_url(url: str) -> str:
    """Return ``url`` without a trailing slash.

    Raise if it is not an http(s) URL.
    """
    if not isinstance(url, str):
        kind = type(url).__name__
        raise TypeError(f"jira url must be str, not {kind}")
    stripped = url.strip()
    if not stripped:
        raise ValueError("jira url is empty")
    parts = urlsplit(stripped)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError(f"jira url must be an http(s) URL, got {stripped!r}")
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, ""))


def normalize_statuses(statuses: Iterable[str]) -> frozenset[str]:
    """Return lowercase status names, dropping blanks."""
    normalized: set[str] = set()
    for status in statuses:
        if not isinstance(status, str):
            kind = type(status).__name__
            raise TypeError(f"jira status must be str, not {kind}")
        text = status.strip().lower()
        if text:
            normalized.add(text)
    return frozenset(normalized)


def _issue_key(issue_key: str) -> str:
    if not isinstance(issue_key, str):
        kind = type(issue_key).__name__
        raise TypeError(f"jira issue key must be str, not {kind}")
    key = issue_key.strip()
    if not key:
        raise ValueError("jira issue key is empty")
    return key


def _read_status(registered: RegisteredJira, key: str) -> str | None:
    try:
        name = registered.client.issue(key).fields.status.name
    except Exception:
        log.warning(
            "jira issue %s at %s could not be read; treating it as blocking",
            key,
            registered.definition.url,
            exc_info=True,
        )
        return None
    if not isinstance(name, str):
        return None
    text = name.strip().lower()
    return text or None


def _install_hook(config: Config) -> None:
    """Run :func:`pytest_external_blockers_add_jira`."""
    hook = config.hook
    hook.pytest_external_blockers_add_jira(  # type: ignore[attr-defined]
        config=config,
    )
