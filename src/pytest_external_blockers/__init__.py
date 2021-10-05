import pytest
from _pytest.mark import MarkDecorator, Mark
from _pytest.config import Config
from _pytest.skipping import evaluate_condition, evaluate_skip_marks
import attr
from typing import Optional

class BlockOutcome(pytest.skip.Exception):
    """raised from pytest.block"""

    pass


BLOCKED = "blocked"


def block(reason):
    """block a test"""
    __tracebackhide__ = True
    raise BlockOutcome(reason)


block.Exception = BlockOutcome

@attr.s(slots=True, frozen=True, auto_attribs=True)
class Block:
    """The result of evaluate_skip_marks()."""

    reason: str

@pytest.hookimpl()
def pytest_configure(config:  Config):
    config.addinivalue_line("markers", "block(reason): mark a test as blocked from execution for a reason")

    config.addinivalue_line("markers", "blockif(*conditions, reason): mark a test as blocked from execution for a reason")



def evaluate_block_marks(item: pytest.Item) -> Optional[Block]:
    """Evaluate skip and skipif marks on item, returning Skip if triggered."""
    for mark in item.iter_markers(name="blockif"):
        if "condition" not in mark.kwargs:
            conditions = mark.args
        else:
            conditions = (mark.kwargs["condition"],)

        # Unconditional.
        if not conditions:
            reason = mark.kwargs.get("reason", "")
            return Block(reason)

        # If any of the conditions are true.
        for condition in conditions:
            result, reason = evaluate_condition(item, mark, condition)
            if result:
                return Block(reason)

    for mark in item.iter_markers(name="block"):
        if "reason" in mark.kwargs:
            reason = mark.kwargs["reason"]
        elif mark.args:
            reason = mark.args[0]
        else:
            reason = "unconditional skip"
        return Block(reason)

    return None



@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item: pytest.Item):
    # Check if block or blockif are specified as pytest marks

    # todo: use stash
    item._should_block = should_block = evaluate_block_marks(item)
    if should_block is not None:
        block(should_block.reason)


@pytest.hookimpl(tryfirst=True)
def pytest_report_teststatus(report):
    if report.outcome == BLOCKED:
        return BLOCKED, "B", BLOCKED.upper()


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if rep.skipped and call.excinfo.errisinstance(BlockOutcome):
        rep.outcome = "blocked"

        evalblock = getattr(rep, "_should_block", None)
        if evalblock is not None and type(rep.longrepr) is tuple:
            # taken from _pytest.skipping, patch failure location to item name
            filename, line, reason = rep.longrepr
            filename, line = item.location[:2]
            rep.longrepr = filename, line, reason
