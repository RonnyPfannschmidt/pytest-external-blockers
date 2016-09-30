
import pytest

from _pytest.mark import MarkInfo, MarkDecorator
from _pytest.skipping import MarkEvaluator


class BlockOutcome(pytest.skip.Exception):
    """ raised from pytest.block """
    pass


BLOCKED = 'blocked'


def block(reason):
    """ block a test """
    __tracebackhide__ = True
    raise BlockOutcome(reason)

block.Exception = BlockOutcome


def pytest_namespace():
    return {'block': block}


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    # Check if block or blockif are specified as pytest marks

    blockif_info = item.get_marker('blockif')
    if blockif_info is not None:
        eval_blockif = MarkEvaluator(item, 'blockif')
        if eval_blockif.istrue():
            item._evalblock = eval_blockif
            pytest.block(eval_blockif.getexplanation())

    block_info = item.get_marker('block')
    if isinstance(block_info, (MarkInfo, MarkDecorator)):
        item._evalblock = True
        if 'reason' in block_info.kwargs:
            block(block_info.kwargs['reason'])
        elif block_info.args:
            block(block_info.args[0])
        else:
            block("unconditional skip")


@pytest.hookimpl(tryfirst=True)
def pytest_report_teststatus(report):
    if report.outcome == BLOCKED:
        return BLOCKED, 'B', BLOCKED.upper()


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if rep.skipped and call.excinfo.errisinstance(BlockOutcome):
        rep.outcome = "blocked"

        evalblock = getattr(rep, '_evalblock', None)
        if evalblock is not None and type(rep.longrepr) is tuple:
            # taken from _pytest.skipping, patch failure location to item name
            filename, line, reason = rep.longrepr
            filename, line = item.location[:2]
            rep.longrepr = filename, line, reason
