from typing import NoReturn
from typing import Optional

import attr
import pytest
from _pytest.config import Config
from _pytest.outcomes import _with_exception
from _pytest.outcomes import OutcomeException
from _pytest.skipping import evaluate_condition


class Blocked(OutcomeException):
    # XXX hackish: on 3k we fake to live in the builtins
    # in order to have Skipped exception printing shorter/nicer
    __module__ = "builtins"

    def __init__(
        self,
        msg: str,
        pytrace: bool = False,
    ) -> None:
        super().__init__(msg=msg, pytrace=pytrace)


BLOCKED = "blocked"


@_with_exception(Blocked)
def block(reason: str) -> NoReturn:
    """block a test"""
    __tracebackhide__ = True
    raise Blocked(reason)


@attr.s(slots=True, frozen=True, auto_attribs=True)
class Block:
    """The result of evaluate_skip_marks()."""

    reason: str


@pytest.hookimpl()
def pytest_configure(config: Config):
    config.addinivalue_line(
        "markers", "block(reason): mark a test as blocked from execution"
    )

    config.addinivalue_line(
        "markers",
        "blockif(*conditions, reason): mark a test as blocked from execution",
    )


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
    item.__dict__["_should_block"] = should_block = evaluate_block_marks(item)
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
    excinfo = call.excinfo
    if excinfo is not None and excinfo.errisinstance(Blocked):
        rep.outcome = BLOCKED

        evalblock = getattr(item, "_should_block", None)
        if evalblock is not None and type(rep.longrepr) is tuple:
            # taken from _pytest.skipping, patch failure location to item name
            filename, line, reason = rep.longrepr
            filename, line = item.location[:2]
            rep.longrepr = filename, line, reason
