"""T2 authored commit-contract regression; no account, process or remote IO."""
from copy import deepcopy
import unittest

from personal_evals.github_delivery import GitHubError, _commit_payload, _verify_commit


class CommitMessageContractTests(unittest.TestCase):
    def setUp(self):
        self.plan = {
            'actor': {'login': 'authored-operator', 'id': 123},
            'createdAt': '2026-11-13T18:17:04Z', 'bundleId': 'b' * 64,
            'planId': 'a' * 64, 'target': {'baseCommit': '1' * 40},
        }
        self.payload = _commit_payload(self.plan, '2' * 40)
        self.row = {
            'sha': '3' * 40, 'tree': {'sha': self.payload['tree']},
            'parents': [{'sha': self.payload['parents'][0]}],
            'message': self.payload['message'],
            'author': dict(self.payload['author']), 'committer': dict(self.payload['committer']),
        }

    def verify(self, row):
        class Readback:
            def request(self, method, path):
                if method != 'GET' or path != '/repos/authored/fixture/git/commits/' + '3' * 40:
                    raise AssertionError('Unexpected request')
                return row
        _verify_commit(Readback(), '/repos/authored/fixture', '3' * 40, self.payload)

    def test_outgoing_message_matches_observed_github_form_without_terminal_newline(self):
        self.assertEqual(self.payload['message'], 'Add Personal Evals bundle ' + 'b' * 64
                         + '\n\nPersonal-Evals-Delivery: ' + 'a' * 64)
        self.verify(self.row)

    def test_readback_remains_literal_and_rejects_extra_or_missing_message_content(self):
        for message in [self.row['message'] + '\n', self.row['message'].replace('\n\n', '\n'),
                        self.row['message'][:-1], ' ' + self.row['message']]:
            with self.subTest(message=message):
                row = deepcopy(self.row); row['message'] = message
                with self.assertRaisesRegex(GitHubError, 'github_object_mismatch'):
                    self.verify(row)

    def test_message_repair_does_not_relax_tree_parent_or_authorship_identity(self):
        for field, key in [('tree','sha'), ('author','name'), ('author','email'), ('committer','date')]:
            with self.subTest(field=field, key=key):
                row = deepcopy(self.row); row[field][key] = 'changed'
                with self.assertRaisesRegex(GitHubError, 'github_object_mismatch'):
                    self.verify(row)
        row = deepcopy(self.row); row['parents'][0]['sha'] = '4' * 40
        with self.assertRaisesRegex(GitHubError, 'github_object_mismatch'):
            self.verify(row)


if __name__ == '__main__':
    unittest.main()
