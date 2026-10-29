from __future__ import annotations

from collections.abc import Callable

import pytest

from pytest_external_blockers import ExternalBlockersPlugin
from pytest_external_blockers import IssueTracker
from pytest_external_blockers import jira_rest_client
from pytest_external_blockers import JiraBasicAuth
from pytest_external_blockers import open_jira
from pytest_external_blockers import TrackerClient
from pytest_external_blockers.clients import IssueClient
from pytest_external_blockers.jira import JiraApi
from pytest_external_blockers.plugin import SESSION_NAME


class FakeClient(IssueClient):
    def __init__(self, status_name: str | None) -> None:
        self.status_name = status_name
        self.calls = 0

    def status(self, issue_key: str) -> str | None:
        self.calls += 1
        return self.status_name


class _Status:
    def __init__(self, name: str) -> None:
        self.name = name


class _Fields:
    def __init__(self, name: str) -> None:
        self.status = _Status(name)


class _Issue:
    def __init__(self, name: str) -> None:
        self.fields = _Fields(name)


class FakeApi(JiraApi):
    def __init__(self, name: str | Exception) -> None:
        self.name = name

    def issue(self, key: str) -> _Issue:
        if isinstance(self.name, Exception):
            raise self.name
        return _Issue(self.name)


def _plugin(
    config: pytest.Config,
    provide: Callable[[IssueTracker], TrackerClient],
) -> ExternalBlockersPlugin:
    class Provider:
        def pytest_external_blockers_client(
            self,
            tracker: IssueTracker,
        ) -> TrackerClient:
            return provide(tracker)

    config.pluginmanager.register(Provider())
    plugin = config.pluginmanager.get_plugin(SESSION_NAME)
    assert isinstance(plugin, ExternalBlockersPlugin)
    return plugin


def test_tracker_constant_normalizes_url_and_statuses() -> None:
    tracker = IssueTracker(
        " rh ",
        "https://jira.example/ ",
        not_blocking=["Done"],
    )

    assert tracker.name == "rh"
    assert tracker.url == "https://jira.example"
    assert tracker.not_blocking == frozenset({"done"})


@pytest.mark.parametrize(
    ("url", "message"),
    [
        ("", "empty"),
        ("jira.example", "http"),
    ],
)
def test_tracker_rejects_a_bad_url(url: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        IssueTracker("rh", url)


def test_credentials_hide_the_token() -> None:
    credentials = JiraBasicAuth(" qe@example.com ", "secret")

    assert credentials.email == "qe@example.com"
    assert "secret" not in repr(credentials)


def test_same_url_and_credentials_share_one_client(
    pytester: pytest.Pytester,
) -> None:
    config = pytester.parseconfigure("-p", "pytest_external_blockers")
    created: list[FakeClient] = []
    credentials = JiraBasicAuth("qe@example.com", "secret")

    def provide(tracker: IssueTracker) -> TrackerClient:
        client = FakeClient("open")
        created.append(client)
        return TrackerClient(credentials, client)

    plugin = _plugin(config, provide)
    first = IssueTracker("a", "https://jira.example")
    second = IssueTracker("b", "https://jira.example/")

    assert plugin.client_for(first) is plugin.client_for(second)
    assert plugin.client_for(first) is created[0]
    assert plugin.credentials_for(second) == credentials
    assert len(created) == 2


def test_different_credentials_do_not_share_a_client(
    pytester: pytest.Pytester,
) -> None:
    config = pytester.parseconfigure("-p", "pytest_external_blockers")
    secret = JiraBasicAuth("qe@example.com", "secret")
    other = JiraBasicAuth("qe@example.com", "other")

    def provide(tracker: IssueTracker) -> TrackerClient:
        credentials = secret if tracker.name == "a" else other
        return TrackerClient(credentials, FakeClient("open"))

    plugin = _plugin(config, provide)
    first = plugin.client_for(IssueTracker("a", "https://jira.example"))
    second = plugin.client_for(IssueTracker("b", "https://jira.example"))

    assert first is not second


def test_status_is_read_once_per_tracker_and_issue(
    pytester: pytest.Pytester,
) -> None:
    config = pytester.parseconfigure("-p", "pytest_external_blockers")
    client = FakeClient("In Progress")
    credentials = JiraBasicAuth("qe@example.com", "secret")
    tracker = IssueTracker("redhat", "https://jira.example")

    plugin = _plugin(
        config,
        lambda current: TrackerClient(credentials, client),
    )

    assert plugin.issue_blocks(tracker, " IQE-1 ") is True
    assert plugin.issue_blocks(tracker, "IQE-1") is True
    assert client.calls == 1


def test_closed_status_does_not_block(pytester: pytest.Pytester) -> None:
    config = pytester.parseconfigure("-p", "pytest_external_blockers")
    credentials = JiraBasicAuth("qe@example.com", "secret")
    tracker = IssueTracker("redhat", "https://jira.example")
    plugin = _plugin(
        config, lambda current: TrackerClient(credentials, FakeClient("Done"))
    )

    assert plugin.issue_blocks(tracker, "IQE-1") is False


def test_missing_hook_blocks(pytester: pytest.Pytester) -> None:
    config = pytester.parseconfigure("-p", "pytest_external_blockers")
    plugin = config.pluginmanager.get_plugin(SESSION_NAME)
    assert isinstance(plugin, ExternalBlockersPlugin)
    tracker = IssueTracker("redhat", "https://jira.example")

    assert plugin.issue_blocks(tracker, "IQE-1") is True


def test_open_jira_passes_basic_auth() -> None:
    tracker = IssueTracker("rh", "https://jira.example")
    credentials = JiraBasicAuth("qe@example.com", "secret")
    constructed: dict[str, object] = {}

    def client_cls(*args: object, **kwargs: object) -> FakeApi:
        constructed["args"] = args
        constructed["kwargs"] = kwargs
        return FakeApi("In Progress")

    provided = open_jira(tracker, credentials, client_cls=client_cls)
    kwargs = constructed["kwargs"]

    assert constructed["args"] == ("https://jira.example",)
    assert isinstance(kwargs, dict)
    assert kwargs["basic_auth"] == ("qe@example.com", "secret")
    assert provided.client.status("IQE-1") == "in progress"


def test_jira_rest_client_wraps_an_existing_api() -> None:
    credentials = JiraBasicAuth("qe@example.com", "secret")
    provided = jira_rest_client(FakeApi(RuntimeError("down")), credentials)

    assert provided.credentials is credentials
    assert provided.client.status("IQE-1") is None


def test_blocked_by_marker_reports_the_category(
    pytester: pytest.Pytester,
    run_blocked: Callable[..., pytest.RunResult],
) -> None:
    pytester.makeconftest(
        """
        from pytest_external_blockers import JiraBasicAuth, TrackerClient

        class Client:
            def status(self, issue_key):
                return "open"

        def pytest_external_blockers_client(tracker):
            return TrackerClient(
                JiraBasicAuth("qe@example.com", "secret"),
                Client(),
            )

        def pytest_runtest_logreport(report):
            if report.when != "setup" or report.outcome != "blocked":
                return
            props = dict(report.user_properties)
            assert props["external-blocker-category"] == "product-issue"
            assert props["external-blocker-issue"] == "IQE-1"
            assert props["external-blocker-tracker"] == "redhat"
        """
    )
    pytester.makepyfile(
        """
        import pytest
        from pytest_external_blockers import Category, IssueTracker

        REDHAT = IssueTracker("redhat", "https://jira.example")

        @pytest.mark.blocked_by(
            REDHAT,
            "IQE-1",
            category=Category.PRODUCT_ISSUE,
        )
        def test_checkout():
            raise AssertionError("should not run")
        """
    )

    result = run_blocked()

    result.stdout.fnmatch_lines(["* 1 blocked *"])


def test_resolved_issue_does_not_block_the_test(
    pytester: pytest.Pytester,
    run_blocked: Callable[..., pytest.RunResult],
) -> None:
    pytester.makeconftest(
        """
        from pytest_external_blockers import JiraBasicAuth, TrackerClient

        class Client:
            def status(self, issue_key):
                return "done"

        def pytest_external_blockers_client(tracker):
            return TrackerClient(
                JiraBasicAuth("qe@example.com", "secret"),
                Client(),
            )
        """
    )
    pytester.makepyfile(
        """
        import pytest
        from pytest_external_blockers import Category, IssueTracker

        REDHAT = IssueTracker("redhat", "https://jira.example")

        @pytest.mark.blocked_by(REDHAT, "IQE-1", category="product-issue")
        def test_checkout():
            pass
        """
    )

    result = run_blocked()

    result.assert_outcomes(passed=1)
