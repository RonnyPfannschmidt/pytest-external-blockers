from __future__ import annotations

from collections.abc import Callable

import pytest

from pytest_external_blockers import add_jira
from pytest_external_blockers import get_jira
from pytest_external_blockers import JiraAlreadyRegistered
from pytest_external_blockers import JiraDefinition
from pytest_external_blockers import JiraNotRegistered
from pytest_external_blockers.jira import JiraFields
from pytest_external_blockers.jira import JiraIssueView
from pytest_external_blockers.jira import JiraStatus


class _Status(JiraStatus):
    name: str

    def __init__(self, name: str) -> None:
        self.name = name


class _Fields(JiraFields):
    status: _Status

    def __init__(self, name: str) -> None:
        self.status = _Status(name)


class _Issue(JiraIssueView):
    fields: _Fields

    def __init__(self, name: str) -> None:
        self.fields = _Fields(name)


class FakeJira:
    def __init__(self, name: str | Exception) -> None:
        self.name = name
        self.keys: list[str] = []

    def issue(self, key: str) -> _Issue:
        self.keys.append(key)
        if isinstance(self.name, Exception):
            raise self.name
        return _Issue(self.name)


@pytest.fixture
def config(pytester: pytest.Pytester) -> pytest.Config:
    return pytester.parseconfig()


def test_add_jira_stores_the_host_client(config: pytest.Config) -> None:
    client = FakeJira("Open")
    definition = JiraDefinition(
        "https://jira.example/ ", not_blocking=["Done", " Closed "]
    )

    registered = add_jira(config, definition, client)

    assert registered.client is client
    assert registered.definition.url == "https://jira.example"
    assert registered.definition.not_blocking == frozenset({"done", "closed"})
    assert get_jira(config, "https://jira.example/").client is client


def test_add_jira_rejects_a_second_registration(config: pytest.Config) -> None:
    add_jira(config, JiraDefinition("https://jira.example"), FakeJira("Open"))

    with pytest.raises(JiraAlreadyRegistered, match="https://jira.example"):
        add_jira(
            config,
            JiraDefinition("https://jira.example/"),
            FakeJira("Done"),
        )


def test_get_jira_rejects_an_unknown_server(config: pytest.Config) -> None:
    with pytest.raises(JiraNotRegistered, match="https://other.example"):
        get_jira(config, "https://other.example")


@pytest.mark.parametrize(
    ("url", "message"),
    [
        ("", "empty"),
        ("   ", "empty"),
        ("jira.example", "http"),
        ("ftp://jira.example", "http"),
    ],
)
def test_definition_rejects_a_bad_url(url: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        JiraDefinition(url)


def test_issue_blocks_when_the_status_is_outside_not_blocking(
    config: pytest.Config,
) -> None:
    client = FakeJira("In Progress")
    registered = add_jira(
        config,
        JiraDefinition("https://jira.example"),
        client,
    )

    assert registered.issue_blocks(" IQE-1 ") is True
    assert client.keys == ["IQE-1"]


def test_issue_does_not_block_when_the_status_is_not_blocking(
    config: pytest.Config,
) -> None:
    registered = add_jira(
        config,
        JiraDefinition("https://jira.example"),
        FakeJira("Done"),
    )

    assert registered.issue_blocks("IQE-1") is False


def test_issue_blocks_when_the_client_cannot_read_it(
    config: pytest.Config,
) -> None:
    registered = add_jira(
        config,
        JiraDefinition("https://jira.example"),
        FakeJira(RuntimeError("down")),
    )

    assert registered.issue_blocks("IQE-1") is True


def test_issue_blocks_when_the_status_name_is_blank(
    config: pytest.Config,
) -> None:
    registered = add_jira(
        config,
        JiraDefinition("https://jira.example"),
        FakeJira("  "),
    )

    assert registered.issue_blocks("IQE-1") is True


def test_hook_registers_the_client(
    pytester: pytest.Pytester, run_blocked: Callable[..., pytest.RunResult]
) -> None:
    pytester.makeconftest(
        """
        from pytest_external_blockers import JiraDefinition, add_jira

        class Client:
            def issue(self, key: str):
                raise AssertionError(key)

        def pytest_external_blockers_add_jira(config):
            add_jira(config, JiraDefinition("https://jira.example/"), Client())
        """
    )
    pytester.makepyfile(
        """
        from pytest_external_blockers import get_jira

        def test_registered(pytestconfig):
            got = get_jira(pytestconfig, "https://jira.example")
            assert got.definition.url == "https://jira.example"
        """
    )

    result = run_blocked()

    result.assert_outcomes(passed=1)
