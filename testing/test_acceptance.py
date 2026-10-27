from __future__ import annotations

from collections.abc import Callable

import pytest


def test_block_function(
    pytester: pytest.Pytester, run_blocked: Callable[..., pytest.RunResult]
) -> None:
    pytester.makepyfile(
        """
        from pytest_external_blockers import block

        def test_block():
            block("test")
    """
    )

    res = run_blocked()
    res.stdout.fnmatch_lines(
        [
            "* 1 blocked *",
        ]
    )


def test_block_mark(
    pytester: pytest.Pytester, run_blocked: Callable[..., pytest.RunResult]
) -> None:
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.block
        def test_block():
            pass
    """
    )

    res = run_blocked()
    res.stdout.fnmatch_lines(
        [
            "* 1 blocked *",
        ]
    )


def test_blockif_mark(
    pytester: pytest.Pytester, run_blocked: Callable[..., pytest.RunResult]
) -> None:
    pytester.makepyfile(
        """
        import pytest
        @pytest.mark.blockif(True, reason="yay")
        def test_block():
            pass
    """
    )

    res = run_blocked()
    res.stdout.fnmatch_lines(
        [
            "* 1 blocked *",
        ]
    )
