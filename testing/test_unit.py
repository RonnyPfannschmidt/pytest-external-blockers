import pytest

from pytest_external_blockers import block


def test_block_raises_blocked_exception() -> None:
    with pytest.raises(block.Exception, match="not today"):
        block("not today")
