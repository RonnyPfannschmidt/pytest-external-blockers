"""Credentials a host has already resolved.

The plugin does not read a vault, a keyring, or an environment variable.
"""
from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field


def _required_text(value: str, label: str) -> str:
    if not isinstance(value, str):
        kind = type(value).__name__
        raise TypeError(f"{label} must be str, not {kind}")
    text = value.strip()
    if not text:
        raise ValueError(f"{label} is empty")
    return text


@dataclass(frozen=True, slots=True)
class JiraBasicAuth:
    """Atlassian account email and API token.

    Passed to ``jira.JIRA`` as ``basic_auth=(email, token)``.
    """

    email: str
    token: str = field(repr=False)

    def __post_init__(self) -> None:
        email = _required_text(self.email, "jira email")
        token = _required_text(self.token, "jira token")
        object.__setattr__(self, "email", email)
        object.__setattr__(self, "token", token)
