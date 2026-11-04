from __future__ import annotations

from collections.abc import Callable

import pytest

pytest_plugins = ["pytester"]


@pytest.fixture
def run_blocked(pytester: pytest.Pytester) -> Callable[..., pytest.RunResult]:
    """Run pytest so it loads the installed plugin."""
    return pytester.runpytest
