pytest-external-blockers
========================

A pytest outcome for tests you dont run for external/environmental reason.


examples of such reasons reasons are:

* lack of access to a bugtracker telling you what tests apply
  for the current version of software under test
* lack of access to a backend service providing essential details for the tests in question
* issue in a bugtracker is unresolved
* failure of the internet connection




install
-------

::

    $ pip install pytest-external-blockers


issue trackers
--------------

A tracker definition is a constant. A marker points at it. The first time
that marker is used, the ``pytest_external_blockers_client`` hook supplies
the client, and the plugin instance keeps it. The same URL and the same
credentials share one client. The plugin does not choose a site and it
does not read a vault.

.. code-block:: python

    import pytest
    from pytest_external_blockers import Category, IssueTracker

    REDHAT = IssueTracker("redhat", "https://jira.example")

    @pytest.mark.blocked_by(REDHAT, "IQE-1", category=Category.PRODUCT_ISSUE)
    def test_checkout():
        ...

The hook returns a ``TrackerClient`` (credentials plus client). Wrap a
client the process already holds with ``jira_rest_client``. The outcome
is ``blocked``, and the category is stored on the report.

``not_blocking`` defaults to ``done``, ``rejected``, and ``closed``.
An issue those statuses do not cover is blocking, including an issue the
client cannot read. A status, once read, is kept for the session.


use
---

.. code-block:: python

    import os
    import pytest
    from .issues import get_tracker

    pytestmark = pytest.mark.skipif(
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
