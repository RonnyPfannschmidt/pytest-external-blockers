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


jira
----

A host registers each Jira server and a client it already built. The plugin
does not choose a site and does not read credentials.

.. code-block:: python

    from pytest_external_blockers import JiraDefinition, add_jira

    def pytest_external_blockers_add_jira(config):
        add_jira(config, JiraDefinition("https://jira.example"), client)

``not_blocking`` defaults to ``done``, ``rejected``, and ``closed``.
An issue those statuses do not cover is blocking, including an issue the
client cannot read.


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
