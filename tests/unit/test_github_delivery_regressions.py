"""T2 activation regressions; authored files/fake API and one isolated CLI child."""

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from personal_evals import github_delivery as publisher
from personal_evals.delivery import write_delivery_plan
from tests.unit import test_github_delivery as fixtures


class PublisherRegressionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.GitHubDeliveryTests(
            "test_execute_requires_literal_true_before_auth_client_construction")
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.root = self.fixture.root

    def test_offline_cli_cold_import_and_verification_do_not_require_fcntl(self):
        plan_path = self.root / "offline-plan.json"
        write_delivery_plan(self.fixture.plan, plan_path)
        home = self.root / "isolated-home"
        home.mkdir(mode=0o700)
        script = """import sys
sys.modules['fcntl'] = None
from personal_evals.cli import main
assert 'personal_evals.github_delivery' not in sys.modules
status = main(['delivery-verify', sys.argv[1]])
assert 'personal_evals.github_delivery' not in sys.modules
raise SystemExit(status)
"""
        result = subprocess.run(
            [sys.executable, "-B", "-S", "-c", script, str(plan_path)],
            cwd=Path(__file__).resolve().parents[2], stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10,
            env={"HOME": str(home), "TMPDIR": str(self.root), "TZ": "UTC",
                 "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1"},
            check=False)
        self.assertEqual(result.returncode, 0, result.stderr[:1000])
        self.assertEqual(result.stderr, b"")
        self.assertLessEqual(len(result.stdout), 16384)
        value = json.loads(result.stdout)
        self.assertEqual(value["planId"], self.fixture.plan["planId"])
        self.assertIs(value["verified"], True)
        self.assertIs(value["remoteChecked"], False)

    def test_unsupported_publisher_refuses_before_validation_journal_or_client(self):
        available = publisher.fcntl
        for label, locking, platform in (("missing-locking", None, "posix"),
                                         ("non-posix", available, "nt")):
            target = self.root / label
            with self.subTest(profile=label):
                with patch.object(publisher, "_Journal") as journal, \
                        patch.object(publisher, "GhApi") as client, \
                        patch.object(publisher, "validate_delivery_plan") as validate, \
                        patch.object(publisher, "fcntl", locking), \
                        patch.object(publisher.os, "name", platform):
                    with self.assertRaises(publisher.GitHubError) as rejected:
                        publisher.publish_delivery(self.fixture.plan, target, execute=True)
                    self.assertEqual(rejected.exception.code, "github_platform_unavailable")
                    with self.assertRaises(publisher.GitHubError) as disabled:
                        publisher.publish_delivery(self.fixture.plan, target, execute=False)
                    self.assertEqual(disabled.exception.code, "github_execution_not_enabled")
                    with self.assertRaises(publisher.GitHubError) as malformed:
                        publisher.publish_delivery(self.fixture.plan, target, execute=True, resume="true")
                    self.assertEqual(malformed.exception.code, "github_request_invalid")
                    validate.assert_not_called()
                    journal.assert_not_called()
                    client.assert_not_called()
                self.assertFalse(target.exists())

    def test_absent_pending_branch_is_never_recreated_and_exact_pr_can_recover(self):
        plan = self.fixture.plan
        branch = plan["target"]["newBranch"]
        for positive_pr in (False, True):
            with self.subTest(exact_closed_pr=positive_pr):
                api = fixtures.AuthoredGitHub(plan)
                journal = self.root / ("positive-pr" if positive_pr else "absent-pr")

                def lose_branch_response(method, path, payload, response):
                    if method == "POST" and path.endswith("/git/refs"):
                        raise publisher.GitHubError(0, "github_request_failed")
                    return response

                api.after = lose_branch_response
                with self.assertRaises(publisher.GitHubError):
                    self.fixture.publish(api=api, journal=journal)
                api.after = None
                events = self.fixture.events(journal)
                self.assertTrue(any(row["event"] == "branch_pending" for row in events))
                self.assertFalse(any(row["event"] == "branch_verified" for row in events))
                commit = api.refs[branch]
                if positive_pr:
                    # Author remote state through the existing fake protocol, not a
                    # stubbed private recovery helper. The branch is deleted afterward.
                    api.request("POST", api.root + "/pulls", {
                        "head": branch, "base": plan["target"]["baseBranch"],
                        "title": plan["pullRequest"]["title"],
                        "body": plan["pullRequest"]["body"] +
                                "\n\n<!-- personal-evals-delivery:" + plan["planId"] + " -->\n",
                        "draft": plan["pullRequest"]["draft"], "maintainer_can_modify": False})
                    api.pulls[-1]["state"] = "closed"
                del api.refs[branch]  # An authored later owner deletion.
                writes_before = len(api.writes())
                if positive_pr:
                    recovered = self.fixture.publish(api=api, journal=journal, resume=True)
                    self.assertEqual(recovered["state"], "closed")
                    self.assertEqual(recovered["headCommit"], commit)
                else:
                    with self.assertRaises(publisher.GitHubError) as uncertain:
                        self.fixture.publish(api=api, journal=journal, resume=True)
                    self.assertEqual(uncertain.exception.code, "github_outcome_uncertain")
                self.assertEqual(len(api.writes()), writes_before)
                self.assertEqual(len(api.writes("/git/refs")), 1)
                self.assertNotIn(branch, api.refs)
                self.fixture.no_ref_mutation(api)
