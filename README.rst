pytest-external-blockers
========================

a distinct pytest  test result for tests
that are skipped for external/environmental reasons
that may daynamically change even for the same test environment

examples of such reasons reasons are

* lack of access to a bugtracker
* lack of access to a backend service
* issue in a bugtracker is unresolved
* failure of the internet connection




install
-------

::
    $ pip install pytest-external-blockers


use
---

::
    import os
    import pytest
    from .issues import get_tracker

    pytestmark = pytest.mark.skipifif(
        "BUGTRACKER" in os.environ,
        reason="no bugtracker configured")

    @pytest.fixture(scope="session")
    def bugtracker():
        try:
            return get_tracker():
        except Exception:
            pytest.block("bugtracker unavailiable")


    @pytest.fixture(autouse=True)
    def _block_unresolved(request, bugtracker):
        issue = request.node.getmarker('issue')
        if issue is not None:
            for issue_id in issue.args:
                if bugtracker.is_unresolved(issue_id)
                    pytest.block(
                        "{issue_id} was not resolved".format(issue_id))