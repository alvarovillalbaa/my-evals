"""Authored handoffs/files only; no Git, provider, task or grader is executed."""

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
import unittest
from unittest.mock import patch

from personal_evals.errors import UserError
from personal_evals.generation import (MAX_HANDOFF_BYTES, accept_draft, build_request,
                                      import_response, validate_request)
from personal_evals.suite import prepare_suite, verify_bundle, write_bundle


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                                     allow_nan=False).encode("utf-8")).hexdigest()


class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="personal-evals-generation-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        policy = {"classification": "private", "permission": "authorized", "containsPersonalData": True}
        files = []
        for path, content in (("src/calculator.py", "def add(a, b):\n    return a + b\n"), ("README.md", "# Authored project\n")):
            data = content.encode("utf-8")
            files.append({"path": path, "mode": "100644", "gitBlob": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest(),
                          "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "content": content})
        self.snapshot = {"schemaVersion": 1, "kind": "personal-evals-repository",
                         "repository": {"label": "authored-project", "commit": "1" * 40, "objectFormat": "sha1"},
                         "dataPolicy": policy, "dataPolicyFingerprint": identity(policy), "files": files}
        self.snapshot["snapshotId"] = identity(self.snapshot)
        task = {"id": "task-a", "name": "authored/task-a", "version": "v1", "sourcePaths": ["src/calculator.py", "README.md"],
                "goal": "Exercise the requested addition behavior", "graderRequirements": ["Check the exact requested result"],
                "critical": True, "rewardKey": "reward", "successThreshold": 1}
        self.intent = {"schemaVersion": 1, "model": "authored/generator", "suite": {"id": "authored-suite", "version": "v1"},
                       "split": "holdout", "decision": {"question": "Does the candidate improve this selected workload?",
                           "minimumPairedTasks": 2, "minimumImprovement": 0.1, "maxCriticalRegressions": 0},
                       "tasks": [task, {**copy.deepcopy(task), "id": "task-b", "name": "authored/task-b", "critical": False,
                                       "sourcePaths": ["src/calculator.py"]}]}
        self.request = build_request(self.snapshot, self.intent)
        self.response_file = self.root / "response.json"

    def response(self):
        tasks = []
        for task in self.request["tasks"]:
            tasks.append({"id": task["id"], "sourcePaths": list(task["sourcePaths"]), "files": [
                {"path": "task.toml", "content": f'schema_version="1.4"\n[task]\nname="{task["name"]}"\nversion="{task["version"]}"\n'},
                {"path": "instruction.md", "content": "Authored task contents supplied by this fixture.\r\n"},
                {"path": "environment/Dockerfile", "content": "FROM scratch\n"},
                {"path": "tests/test.sh", "content": "#!/bin/sh\n# Authored only. Never executed by these checks.\n"},
            ]})
        return {"schemaVersion": 1, "kind": "personal-evals-generated-tasks", "requestId": self.request["requestId"],
                "snapshotId": self.snapshot["snapshotId"], "model": self.request["model"], "tasks": tasks}

    def write_response(self, value=None):
        self.response_file.write_text(json.dumps(self.response() if value is None else value), encoding="utf-8")

    def draft(self, name="draft"):
        self.write_response()
        destination = self.root / name
        review = import_response(self.request, self.response_file, destination)
        return destination, review

    def write_json(self, path, value):
        path.write_text(json.dumps(value), encoding="utf-8")

    def test_request_binds_full_source_policy_and_normalizes_explicit_paths(self):
        self.assertEqual(self.request["snapshot"], self.snapshot)
        self.assertEqual(self.request["tasks"][0]["sourcePaths"], ["README.md", "src/calculator.py"])
        self.assertEqual(self.request["snapshot"]["dataPolicy"]["classification"], "private")
        self.assertEqual(self.request["requestId"], identity({key: value for key, value in self.request.items() if key != "requestId"}))
        self.assertEqual(validate_request(self.request), self.request)
        multiline = copy.deepcopy(self.intent)
        multiline["tasks"][0]["goal"] = "Exercise addition.\n\tInclude zero and negative values."
        multiline["tasks"][0]["graderRequirements"] = ["Check the result.\r\nReject extra output."]
        request = build_request(self.snapshot, multiline)
        self.assertEqual(request["tasks"][0]["goal"], multiline["tasks"][0]["goal"])
        self.assertEqual(validate_request(request)["tasks"][0]["graderRequirements"], multiline["tasks"][0]["graderRequirements"])
        self.snapshot["files"][0]["content"] = "changed afterwards"
        self.intent["tasks"][0]["graderRequirements"][0] = "changed afterwards"
        self.assertEqual(self.request["snapshot"]["files"][0]["content"], "def add(a, b):\n    return a + b\n")
        self.assertEqual(self.request["tasks"][0]["graderRequirements"], ["Check the exact requested result"])

    def test_strict_owner_intent_rejects_unknown_fields_invalid_bounds_and_duplicate_ids(self):
        changes = [lambda value: value.update(dataPolicy={"classification": "authored"}),
                   lambda value: value.update(schemaVersion=True), lambda value: value.update(model="unqualified"),
                   lambda value: value.update(tasks=[]), lambda value: value.update(tasks=value["tasks"] * 11),
                   lambda value: value["tasks"][1].update(id="task-a"), lambda value: value["tasks"][1].update(name="authored/task-a"),
                   lambda value: value["tasks"][0].update(name="unnamespaced"), lambda value: value["tasks"][0].update(version=""),
                   lambda value: value["tasks"][0].update(goal="x" * 4001), lambda value: value["tasks"][0].update(goal=""),
                   lambda value: value["tasks"][0].update(goal="bad\0goal"), lambda value: value["tasks"][0].update(goal="bad\ud800goal"),
                   lambda value: value["tasks"][0].update(graderRequirements=[]),
                   lambda value: value["tasks"][0].update(graderRequirements=["x"] * 11),
                   lambda value: value["tasks"][0].update(graderRequirements=["x" * 1001]),
                   lambda value: value["tasks"][0].update(critical=1), lambda value: value["tasks"][0].update(successThreshold=True)]
        for change in changes:
            intent = copy.deepcopy(self.intent)
            change(intent)
            with self.assertRaises(UserError):
                build_request(self.snapshot, intent)

    def test_missing_duplicate_unknown_or_unused_selected_source_is_rejected(self):
        for paths in ([], ["README.md", "README.md"], ["not-selected.md"]):
            intent = copy.deepcopy(self.intent)
            intent["tasks"][0]["sourcePaths"] = paths
            with self.assertRaises(UserError):
                build_request(self.snapshot, intent)
        intent = copy.deepcopy(self.intent)
        intent["tasks"][0]["sourcePaths"] = ["src/calculator.py"]
        with self.assertRaisesRegex(UserError, "generation_unused_source"):
            build_request(self.snapshot, intent)

    def test_request_identity_and_nested_snapshot_tampering_are_rejected(self):
        changes = [lambda value: value.update(requestId="0" * 64), lambda value: value.update(extra="private trace"),
                   lambda value: value.update(model="authored/other"),
                   lambda value: value["snapshot"]["files"][0].update(content="changed source"),
                   lambda value: value["snapshot"]["dataPolicy"].update(containsPersonalData=False),
                   lambda value: value["tasks"][0].update(critical=False),
                   lambda value: value["harbor"].update(profile="other")]
        for change in changes:
            value = copy.deepcopy(self.request)
            change(value)
            with self.assertRaises(UserError):
                validate_request(value)

    def test_request_artifact_limit_has_an_exact_small_fixture_boundary(self):
        self.assertEqual(MAX_HANDOFF_BYTES, 4 * 1024 * 1024)
        size = len(json.dumps(self.request, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()) + 1
        with patch("personal_evals.generation.MAX_HANDOFF_BYTES", size):
            self.assertEqual(validate_request(self.request), self.request)
        with patch("personal_evals.generation.MAX_HANDOFF_BYTES", size - 1):
            with self.assertRaisesRegex(UserError, "generation_too_large"):
                validate_request(self.request)

    def test_import_maps_response_ids_and_preserves_provider_bytes_owner_metadata_and_policy(self):
        response = self.response()
        response["tasks"].reverse()
        self.write_response(response)
        raw = self.response_file.read_bytes()
        draft = self.root / "draft"
        review = import_response(self.request, self.response_file, draft)
        self.assertEqual(review["status"], "review_required")
        self.assertEqual(review["taskIds"], ["task-a", "task-b"])
        self.assertEqual(review["responseSha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual((draft / "tasks/task-a/instruction.md").read_bytes(), b"Authored task contents supplied by this fixture.\r\n")
        suite = json.loads((draft / "suite.json").read_text())
        self.assertEqual(suite["decision"], self.request["decision"])
        self.assertEqual(suite["dataPolicy"], self.snapshot["dataPolicy"])
        self.assertEqual(suite["tasks"][0]["critical"], True)
        self.assertEqual(suite["tasks"][0]["path"], "tasks/task-a")
        self.assertFalse((draft / "bundle.json").exists())
        self.assertEqual(json.loads((draft / "request.json").read_text()), self.request)
        self.assertEqual(self.response_file.read_bytes(), raw)
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(draft.stat().st_mode), 0o700)
            self.assertTrue(all(stat.S_IMODE(path.stat().st_mode) == (0o700 if path.is_dir() else 0o600) for path in draft.rglob("*")))

    def test_response_binding_and_exact_requested_task_set_are_required_before_output(self):
        changes = [lambda value: value.update(requestId="0" * 64), lambda value: value.update(snapshotId="0" * 64),
                   lambda value: value.update(model="authored/other"), lambda value: value.update(schemaVersion=True),
                   lambda value: value["tasks"].pop(), lambda value: value["tasks"][0].update(id="other-task"),
                   lambda value: value["tasks"][1].update(id="task-a"),
                   lambda value: value["tasks"][0].update(sourcePaths=["src/calculator.py"])]
        for change in changes:
            response = self.response()
            change(response)
            self.write_response(response)
            destination = self.root / "rejected"
            with self.assertRaises(UserError):
                import_response(self.request, self.response_file, destination)
            self.assertFalse(destination.exists())

    def test_missing_or_blank_instructions_environment_and_graders_are_not_fabricated(self):
        for required in ("task.toml", "instruction.md", "environment/Dockerfile", "tests/test.sh"):
            for missing in (True, False):
                response = self.response()
                files = response["tasks"][0]["files"]
                if missing:
                    response["tasks"][0]["files"] = [file for file in files if file["path"] != required]
                else:
                    next(file for file in files if file["path"] == required)["content"] = " \n"
                self.write_response(response)
                with self.assertRaises(UserError):
                    import_response(self.request, self.response_file, self.root / "rejected")
                self.assertFalse((self.root / "rejected").exists())

    def test_provider_cannot_change_task_name_version_or_harbor_profile(self):
        for old, new in (("authored/task-a", "authored/other"), ('version="v1"', 'version="v2"'),
                         ('schema_version="1.4"', 'schema_version="1.3"')):
            response = self.response()
            response["tasks"][0]["files"][0]["content"] = response["tasks"][0]["files"][0]["content"].replace(old, new)
            self.write_response(response)
            with self.assertRaises(UserError):
                import_response(self.request, self.response_file, self.root / "rejected")
            self.assertFalse((self.root / "rejected").exists())

    def test_generated_paths_secrets_ignored_files_and_case_collisions_are_rejected(self):
        for path in ("../escape", "/absolute", "environment/.env", "tests/credentials.json", "tests/code.pyc", "tests/test.sh", "tests/TEST.sh", "tests/test.sh/child"):
            response = self.response()
            response["tasks"][0]["files"].append({"path": path, "content": "authored"})
            self.write_response(response)
            with self.assertRaises(UserError):
                import_response(self.request, self.response_file, self.root / "rejected")
            self.assertFalse((self.root / "rejected").exists())

    def test_generated_content_is_strict_utf8_nul_free_and_bounded(self):
        for content in (None, "\0", "\ud800", "x" * (1024 * 1024 + 1)):
            response = self.response()
            response["tasks"][0]["files"][1]["content"] = content
            self.write_response(response)
            with self.assertRaises(UserError):
                import_response(self.request, self.response_file, self.root / "rejected")
        response = self.response()
        response["tasks"][0]["files"] = response["tasks"][0]["files"] * 26
        self.write_response(response)
        with self.assertRaises(UserError):
            import_response(self.request, self.response_file, self.root / "rejected")

    def test_response_limit_and_invalid_json_utf8_duplicate_keys_never_create_output(self):
        response = self.response()
        response["tasks"][0]["files"][1]["content"] = "x" * 5000
        self.write_response(response)
        size = self.response_file.stat().st_size
        with patch("personal_evals.generation.MAX_HANDOFF_BYTES", size):
            self.assertEqual(import_response(self.request, self.response_file, self.root / "at-limit")["status"], "review_required")
        with patch("personal_evals.generation.MAX_HANDOFF_BYTES", size - 1):
            with self.assertRaises(UserError):
                import_response(self.request, self.response_file, self.root / "rejected")
        for raw in (b"{", b"\xff", b'{"schemaVersion":1,"schemaVersion":1}'):
            self.response_file.write_bytes(raw)
            with self.assertRaises(UserError):
                import_response(self.request, self.response_file, self.root / "rejected")
            self.assertFalse((self.root / "rejected").exists())

    def test_acceptance_requires_explicit_boolean_owner_review(self):
        draft, _review = self.draft()
        for reviewed in (False, None, 1, "true"):
            with self.assertRaisesRegex(UserError, "generation_review_required"):
                accept_draft(draft, self.root / "accepted", reviewed=reviewed)
            self.assertFalse((self.root / "accepted").exists())

    def test_acceptance_writes_a_real_verified_bundle_bound_to_the_review(self):
        draft, review = self.draft()
        destination = self.root / "accepted"
        accepted = accept_draft(draft, destination, reviewed=True)
        self.assertEqual(accepted, {"reviewId": review["reviewId"], "requestId": self.request["requestId"],
                                   "snapshotId": self.snapshot["snapshotId"], "bundleId": review["draftBundleId"], "status": "accepted"})
        self.assertEqual(verify_bundle(destination)["bundleId"], review["draftBundleId"])
        self.assertEqual(json.loads((draft / "review.json").read_text())["status"], "review_required")
        self.assertFalse((destination / "request.json").exists())

    def test_edited_task_request_review_or_extra_inventory_blocks_acceptance(self):
        original, _review = self.draft()
        for number, relative in enumerate(("tasks/task-a/instruction.md", "request.json", "review.json", "extra.txt")):
            draft = self.root / f"changed-{number}"
            shutil.copytree(original, draft)
            path = draft / relative
            path.write_bytes(path.read_bytes() + b"changed" if path.exists() else b"extra")
            with self.assertRaises(UserError):
                accept_draft(draft, self.root / "accepted", reviewed=True)
            self.assertFalse((self.root / "accepted").exists())
        link = original / "extra-link"
        link.symlink_to(self.response_file)
        with self.assertRaises(UserError):
            accept_draft(original, self.root / "accepted", reviewed=True)

    def test_rehashing_review_does_not_allow_owner_policy_or_grader_metadata_changes(self):
        original, _review = self.draft()
        for number, change in enumerate((lambda suite: suite["dataPolicy"].update(containsPersonalData=False),
                                         lambda suite: suite["tasks"][0].update(critical=False),
                                         lambda suite: suite["decision"].update(minimumImprovement=0.2))):
            draft = self.root / f"metadata-{number}"
            shutil.copytree(original, draft)
            suite = json.loads((draft / "suite.json").read_text())
            change(suite)
            self.write_json(draft / "suite.json", suite)
            manifest, _payload = prepare_suite(draft / "suite.json")
            review = json.loads((draft / "review.json").read_text())
            review["draftBundleId"] = manifest["bundleId"]
            review["reviewId"] = identity({key: value for key, value in review.items() if key != "reviewId"})
            self.write_json(draft / "review.json", review)
            with self.assertRaisesRegex(UserError, "generation_owner_metadata_changed"):
                accept_draft(draft, self.root / "accepted", reviewed=True)
        redirected = self.root / "redirected"
        shutil.copytree(original, redirected)
        suite = json.loads((redirected / "suite.json").read_text())
        suite["tasks"][0]["path"] = "other-task-location"
        self.write_json(redirected / "suite.json", suite)
        with patch("personal_evals.generation.prepare_suite", side_effect=AssertionError("must reject metadata before reading task files")):
            with self.assertRaisesRegex(UserError, "generation_owner_metadata_changed"):
                accept_draft(redirected, self.root / "accepted", reviewed=True)

    def test_import_and_acceptance_refuse_existing_outputs_and_nested_bundle_destination(self):
        draft, _review = self.draft()
        existing = self.root / "existing"
        existing.mkdir()
        (existing / "sentinel").write_bytes(b"preserve")
        with self.assertRaisesRegex(UserError, "output_exists"):
            import_response(self.request, self.response_file, existing)
        with self.assertRaisesRegex(UserError, "output_exists"):
            accept_draft(draft, existing, reviewed=True)
        with self.assertRaisesRegex(UserError, "output_inside_draft"):
            accept_draft(draft, draft / "bundle", reviewed=True)
        self.assertEqual(list(existing.iterdir()), [existing / "sentinel"])
        self.assertEqual((existing / "sentinel").read_bytes(), b"preserve")

    def test_failed_import_cleans_only_owned_outputs_and_preserves_foreign_additions(self):
        self.write_response()
        destination = self.root / "failed"

        def fail(path):
            (path.parent / "foreign-sentinel").write_bytes(b"another writer")
            raise UserError("authored_failure")

        with patch("personal_evals.generation.prepare_suite", side_effect=fail):
            with self.assertRaisesRegex(UserError, "authored_failure"):
                import_response(self.request, self.response_file, destination)
        self.assertEqual(list(destination.iterdir()), [destination / "foreign-sentinel"])
        self.assertEqual((destination / "foreign-sentinel").read_bytes(), b"another writer")
        self.assertTrue(self.response_file.exists())

    def test_acceptance_uses_captured_reviewed_bytes_when_input_changes_before_bundle_write(self):
        draft, review = self.draft()
        original = (draft / "tasks/task-a/instruction.md").read_bytes()
        captured_roots = []

        def changed_after_capture(suite_file, destination):
            captured_roots.append(suite_file.parent.parent)
            (draft / "tasks/task-a/instruction.md").write_bytes(b"new unreviewed input\n")
            return write_bundle(suite_file, destination)

        with patch("personal_evals.generation.write_bundle", side_effect=changed_after_capture):
            accepted = accept_draft(draft, self.root / "accepted", reviewed=True)
        self.assertEqual(accepted["bundleId"], review["draftBundleId"])
        self.assertEqual((self.root / "accepted/tasks/task-a/instruction.md").read_bytes(), original)
        self.assertEqual((draft / "tasks/task-a/instruction.md").read_bytes(), b"new unreviewed input\n")
        self.assertTrue(captured_roots)
        self.assertTrue(all(not path.exists() for path in captured_roots))

    def test_arbitrary_response_metadata_and_trace_fields_are_not_retained(self):
        for modify in (lambda response: response.update(trace="private authored sentinel"),
                       lambda response: response["tasks"][0].update(critical=False),
                       lambda response: response["tasks"][0]["files"][0].update(extra="private authored sentinel")):
            response = self.response()
            modify(response)
            self.write_response(response)
            raw = self.response_file.read_bytes()
            with self.assertRaises(UserError):
                import_response(self.request, self.response_file, self.root / "rejected")
            self.assertFalse((self.root / "rejected").exists())
            self.assertEqual(self.response_file.read_bytes(), raw)


if __name__ == "__main__":
    unittest.main()
