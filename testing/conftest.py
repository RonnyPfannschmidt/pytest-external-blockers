from __future__ import annotations

from collections.abc import Callable

import pytest

pytest_plugins = ["pytester"]


@pytest.fixture
def run_blocked(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> Callable[..., pytest.RunResult]:
    """Run a subprocess pytest with only this plugin loaded."""
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")

    def run(*args: str) -> pytest.RunResult:
        return pytester.runpytest("-p", "pytest_external_blockers", *args)

    return run
