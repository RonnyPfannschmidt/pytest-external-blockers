"""Wrap a Jira API the host already holds, or open one from credentials."""
from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import cast
from typing import Protocol

from pytest_external_blockers.clients import IssueClient
from pytest_external_blockers.clients import TrackerClient
from pytest_external_blockers.credentials import JiraBasicAuth
from pytest_external_blockers.trackers import IssueTracker

log = logging.getLogger(__name__)

_TIMEOUT = 5
_MAX_RETRIES = 0


class JiraApi(Protocol):
    """The ``jira.JIRA`` call this plugin uses."""

    def issue(self, key: str) -> object:
        """Return the issue for ``key``."""


class JiraRestClient(IssueClient):
    """Read issue status through a ``jira.JIRA`` instance."""

    def __init__(self, api: JiraApi) -> None:
        self._api = api

    def status(self, issue_key: str) -> str | None:
        """Return the lowercase status, or ``None`` if it cannot be read."""
        try:
            name = _status_name(self._api.issue(issue_key))
        except Exception:
            log.warning(
                "jira issue %s could not be read",
                issue_key,
                exc_info=True,
            )
            return None
        return name


def jira_rest_client(
    api: JiraApi,
    credentials: JiraBasicAuth,
) -> TrackerClient:
    """Wrap a client the host already holds, such as a process-scoped one."""
    return TrackerClient(credentials, JiraRestClient(api))


def open_jira(
    tracker: IssueTracker,
    credentials: JiraBasicAuth,
    *,
    client_cls: Callable[..., JiraApi] | None = None,
) -> TrackerClient:
    """Open a Jira client for a hook implementation that has credentials.

    ``client_cls`` defaults to ``jira.JIRA``. IQE can ignore this and return
    :func:`jira_rest_client` around the client it already provides.
    """
    cls = client_cls or _jira_cls()
    api = cls(
        tracker.url,
        basic_auth=(credentials.email, credentials.token),
        options={"verify": jira_ssl_verify()},
        validate=True,
        timeout=_TIMEOUT,
        max_retries=_MAX_RETRIES,
    )
    return jira_rest_client(api, credentials)


def jira_ssl_verify() -> bool | str:
    """Return the verify value passed to ``jira.JIRA``.

    ``JIRA_SSL_VERIFY=false`` disables verification. ``REQUESTS_CA_BUNDLE``
    selects a CA file when that path exists. Otherwise verification stays on
    and the HTTP library uses its default trust store.
    """
    flag = os.environ.get("JIRA_SSL_VERIFY", "").lower()
    if flag in {"false", "0", "no", "off"}:
        log.warning("SSL verification disabled for Jira connections")
        return False
    ca_bundle = os.environ.get("REQUESTS_CA_BUNDLE")
    if ca_bundle and os.path.isfile(ca_bundle):
        return ca_bundle
    return True


def _jira_cls() -> Callable[..., JiraApi]:
    try:
        from jira import JIRA
    except ImportError as exc:
        raise ImportError(
            "jira is required to open a Jira client; "
            "install pytest-external-blockers[jira]"
        ) from exc
    return cast(Callable[..., JiraApi], JIRA)


def _status_name(issue: object) -> str | None:
    fields = getattr(issue, "fields", None)
    status = getattr(fields, "status", None)
    name = getattr(status, "name", None)
    if not isinstance(name, str):
        return None
    text = name.strip().lower()
    return text or None
