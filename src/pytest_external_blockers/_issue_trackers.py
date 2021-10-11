import enum
from typing import Dict
from typing import FrozenSet
from typing import Optional
from typing import Protocol
from typing import Union

import attr
from jira import JIRA as JiraClient

# from jira.exceptions import JIRAError


class BlockType(enum.Enum):
    """the type of a block"""

    TRIAGE = enum.auto()
    ISSUE = enum.auto()
    RFE = enum.auto()


class BlockOrigin(enum.Enum):
    """designated the origin of a block"""

    UNKNOWN = enum.auto()
    AUTOMATION = enum.auto()
    PRODUCT = enum.auto()
    ENVIRONMENT = enum.auto()


ISSUE_KEY = Union[str, int]


@attr.s(auto_attribs=True, frozen=True, hash=True)
class BlockerRequirement:
    name: str
    value: Union[str, int, bool]


@attr.s(auto_attribs=True, frozen=True, hash=True)
class IssueTracker:
    url_or_key: str
    project: Optional[str] = None

    def __call__(self, *k, **kw) -> "BlockerIssue":
        return BlockerIssue(self, *k, **kw)


@attr.s(auto_attribs=True, frozen=True, hash=True)
class BlockerIssue:
    tracker: IssueTracker
    key: ISSUE_KEY
    type: BlockType = BlockType.TRIAGE
    origin: BlockOrigin = BlockOrigin.UNKNOWN
    requriements: Optional[FrozenSet[BlockerRequirement]] = None
    description: Optional[str] = None
    blocks_by_default: bool = True


class IssueChecker(Protocol):
    def is_closed(self, issue: BlockerIssue) -> bool:
        pass


@attr.s(auto_attribs=True, hash=False, eq=False)
class CachedIssueChecker:
    checker: IssueChecker
    _cache: Dict[BlockerIssue, bool] = attr.ib(factory=dict)

    def is_closed(self, issue: BlockerIssue) -> bool:
        res = self._cache.get(issue)
        if res is None:
            res = self._cache[issue] = self.checker.is_closed(issue)
        return res


@attr.s(auto_attribs=True, hash=False, eq=False)
class JiraIssueChecker:
    client: JiraClient

    NOT_BLOCKING = ("done", "rejected")

    def is_closed(self, issue):
        issue = self.client.issue(issue.key)
        return issue.fields.status.name.lower() in self.NOT_BLOCKING


@attr.s(hash=False, eq=False)
class DefaultChecker:
    def is_closed(self, issue: BlockerIssue):
        return issue.blocks_by_default


@attr.s(auto_attribs=True, eq=False, hash=False)
class BlockerResolver:
    tracker: IssueTracker

    checker: IssueChecker

    def __call__(self, issue: BlockerIssue) -> bool:
        assert issue.tracker is self.tracker
        return self.checker.is_closed(issue)
