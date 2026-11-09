"""The ``blocked`` outcome and the ``block`` helper."""
from typing import ClassVar
from typing import NoReturn
from typing import Type

from _pytest.outcomes import OutcomeException

BLOCKED = "blocked"


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


class _Block:
    """``block(reason)`` raises :class:`Blocked`.

    ``Exception`` matches the attribute ``_with_exception`` used to attach,
    before pytest 7 removed that private helper.
    """

    Exception: ClassVar[Type[Blocked]] = Blocked

    def __call__(self, reason: str = "") -> NoReturn:
        """block a test"""
        __tracebackhide__ = True
        raise Blocked(msg=reason, pytrace=False)


block = _Block()
