"""Issue tracker definitions. A definition is a constant tests can import."""
from __future__ import annotations

import enum
from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import urlsplit
from urllib.parse import urlunsplit

_DEFAULT_NOT_BLOCKING = frozenset({"done", "rejected", "closed"})


class Category(enum.Enum):
    """Why a test is tied to an external issue."""

    NEEDS_TRIAGE = "needs-triage"
    AUTOMATION_ISSUE = "automation-issue"
    AUTOMATION_RFE = "automation-rfe"
    ENVIRONMENT_ISSUE = "environment-issue"
    PRODUCT_ISSUE = "product-issue"
    PRODUCT_RFE = "product-rfe"


@dataclass(frozen=True, slots=True, init=False)
class IssueTracker:
    """One external tracker.

    ``url`` is the server. ``not_blocking`` is the status names, compared
    case-insensitively, that mean an issue does not block. The default is
    ``done``, ``rejected``, and ``closed``.
    """

    name: str
    url: str
    kind: str
    not_blocking: frozenset[str]

    def __init__(
        self,
        name: str,
        url: str,
        kind: str = "jira",
        not_blocking: Iterable[str] = _DEFAULT_NOT_BLOCKING,
    ) -> None:
        object.__setattr__(self, "name", _tracker_name(name))
        object.__setattr__(self, "url", normalize_tracker_url(url))
        object.__setattr__(self, "kind", _tracker_kind(kind))
        object.__setattr__(
            self,
            "not_blocking",
            normalize_statuses(not_blocking),
        )


def parse_category(value: Category | str) -> Category:
    """Return the category for a marker value."""
    if isinstance(value, Category):
        return value
    if isinstance(value, str):
        text = value.strip()
        for item in Category:
            if text == item.value or text == item.name:
                return item
    raise ValueError(f"unknown blocker category: {value!r}")


def normalize_tracker_url(url: str) -> str:
    """Return ``url`` without a trailing slash.

    Raise if it is not an http(s) URL.
    """
    if not isinstance(url, str):
        kind = type(url).__name__
        raise TypeError(f"tracker url must be str, not {kind}")
    stripped = url.strip()
    if not stripped:
        raise ValueError("tracker url is empty")
    parts = urlsplit(stripped)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        message = f"tracker url must be an http(s) URL, got {stripped!r}"
        raise ValueError(message)
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, ""))


def normalize_statuses(statuses: Iterable[str]) -> frozenset[str]:
    """Return lowercase status names, dropping blanks."""
    normalized: set[str] = set()
    for status in statuses:
        if not isinstance(status, str):
            kind = type(status).__name__
            raise TypeError(f"tracker status must be str, not {kind}")
        text = status.strip().lower()
        if text:
            normalized.add(text)
    return frozenset(normalized)


def _tracker_name(name: str) -> str:
    if not isinstance(name, str):
        kind = type(name).__name__
        raise TypeError(f"tracker name must be str, not {kind}")
    text = name.strip()
    if not text:
        raise ValueError("tracker name is empty")
    return text


def _tracker_kind(kind: str) -> str:
    if not isinstance(kind, str):
        got = type(kind).__name__
        raise TypeError(f"tracker kind must be str, not {got}")
    text = kind.strip().lower()
    if not text:
        raise ValueError("tracker kind is empty")
    return text
