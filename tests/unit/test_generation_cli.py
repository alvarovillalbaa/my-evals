"""Authored T2 CLI integration cases; no execution has been performed.

Future approved execution creates only tiny owned Git repositories and local
artifacts. These fixtures are neither provider output nor Harbor run evidence.
"""

from contextlib import ExitStack, contextmanager, redirect_stderr, redirect_stdout
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from personal_evals.cli import main
from personal_evals.suite import verify_bundle


class GenerationCliTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="personal-evals-generation-cli-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.repo = self.root / "authored repository"
        self.repo.mkdir()
        self.git = shutil.which("git")
        self.assertIsNotNone(self.git, "the approved T2 scope requires existing Git")
        self.git_environment = {"PATH": os.defpath, "LANG": "C", "LC_ALL": "C",
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_TERMINAL_PROMPT": "0", "GIT_ALLOW_PROTOCOL": "",
            "GIT_AUTHOR_DATE": "2026-10-28T12:00:00+00:00", "GIT_COMMITTER_DATE": "2026-10-28T12:00:00+00:00"}
        self.git_command("init", "--quiet", "--initial-branch=main", "--object-format=sha1")
        self.committed = "\ufeffCommitted café 🌊\r\nOnly this file is selected.\r\n".encode("utf-8")
        (self.repo / "source.txt").write_bytes(self.committed)
        (self.repo / "unselected.txt").write_text("UNSELECTED_AUTHORED_SENTINEL\n", encoding="utf-8")
        self.git_command("add", "--", "source.txt", "unselected.txt")
        self.git_command("commit", "--quiet", "--no-gpg-sign", "-m", "Authored generation CLI fixture")
        self.commit = self.git_command("rev-parse", "HEAD").strip()
        self.policy = {"classification": "private", "permission": "authorized", "containsPersonalData": True}
        self.policy_path = self.write_json("policy.json", self.policy)

    def git_command(self, *arguments):
        completed = subprocess.run([self.git, "-c", "core.hooksPath=" + os.devnull, "-c", "core.fsmonitor=false",
            "-c", "core.autocrlf=false", "-c", "user.name=Authored Fixture", "-c", "user.email=authored@fixture.invalid",
            "-C", str(self.repo), *arguments], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=self.git_environment, timeout=5, check=True, text=True, encoding="utf-8")
        return completed.stdout

    def write_json(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
        return path

    def read_json(self, path):
        return json.loads(path.read_text(encoding="utf-8"))

    def invoke(self, arguments):
        output, error = StringIO(), StringIO()
        with redirect_stdout(output), redirect_stderr(error):
            code = main([str(value) for value in arguments])
        text = output.getvalue()
        return code, json.loads(text) if text else None, error.getvalue(), text

    def success(self, arguments):
        code, data, error, _text = self.invoke(arguments)
        self.assertEqual((code, error), (0, ""))
        return data

    def failure(self, arguments, expected=None):
        code, data, error, text = self.invoke(arguments)
        self.assertEqual(code, 2); self.assertIsNone(data); self.assertEqual(text, "")
        self.assertRegex(error, r"\Aerror: [a-z][a-z0-9_]*\n\Z")
        if expected is not None:
            self.assertEqual(error, f"error: {expected}\n")
        return error

    def snapshot_arguments(self, destination):
        return ["snapshot", "--repo", self.repo, "--revision", self.commit, "--file", "source.txt",
                "--label", "authored-repository", "--policy", self.policy_path, "--out", destination]

    def snapshot(self):
        path = self.root / "snapshot.json"
        receipt = self.success(self.snapshot_arguments(path))
        return path, self.read_json(path), receipt

    def intent(self):
        return {"schemaVersion": 1, "model": "authored/generator", "suite": {"id": "authored-suite", "version": "v1"},
            "split": "holdout", "decision": {"question": "Does the candidate help on these authored tasks?", "minimumPairedTasks": 2,
                "minimumImprovement": 0.1, "maxCriticalRegressions": 0},
            "tasks": [{"id": "task-a", "name": "authored/task-a", "version": "v1", "sourcePaths": ["source.txt"],
                "goal": "Exercise the explicitly selected behavior", "graderRequirements": ["Check the exact expected output"],
                "critical": True, "rewardKey": "reward", "successThreshold": 1}]}

    def request(self):
        snapshot_path, snapshot, _receipt = self.snapshot()
        intent_path = self.write_json("intent.json", self.intent())
        destination = self.root / "request.json"
        receipt = self.success(["generation-request", snapshot_path, "--intent", intent_path, "--out", destination])
        return destination, self.read_json(destination), snapshot, receipt

    def response(self, request):
        return {"schemaVersion": 1, "kind": "personal-evals-generated-tasks", "requestId": request["requestId"],
            "snapshotId": request["snapshot"]["snapshotId"], "model": request["model"],
            "tasks": [{"id": "task-a", "sourcePaths": ["source.txt"], "files": [
                {"path": "task.toml", "content": 'schema_version = "1.4"\n[task]\nname = "authored/task-a"\nversion = "v1"\n'},
                {"path": "instruction.md", "content": "Authored format fixture: write fixture to /app/output.txt.\n"},
                {"path": "environment/Dockerfile", "content": "FROM scratch\n"},
                {"path": "tests/test.sh", "content": "#!/bin/sh\n# Authored review fixture, never executed by these CLI commands.\nexit 93\n"}]}]}

    def draft(self):
        request_path, request, snapshot, _receipt = self.request()
        response_path = self.write_json("response.json", self.response(request))
        destination = self.root / "review draft"
        receipt = self.success(["generation-import", request_path, "--response", response_path, "--out", destination])
        return destination, request, snapshot, receipt

    @contextmanager
    def no_services(self, *, allow_git=False):
        original = subprocess.Popen
        processes = []

        def process(argv, *arguments, **keywords):
            if not allow_git:
                raise AssertionError("generation artifacts must not execute a child process")
            self.assertIsInstance(argv, list)
            self.assertEqual(Path(argv[0]).resolve(), Path(self.git).resolve(), "only the existing Git reader is permitted")
            processes.append(list(argv))
            return original(argv, *arguments, **keywords)

        with ExitStack() as stack:
            stack.enter_context(patch("subprocess.Popen", side_effect=process))
            stack.enter_context(patch("socket.create_connection", side_effect=AssertionError("no provider or remote connection")))
            stack.enter_context(patch("urllib.request.urlopen", side_effect=AssertionError("no provider request")))
            stack.enter_context(patch("personal_evals.cli.import_job", side_effect=AssertionError("no Harbor result import")))
            yield processes

    def test_snapshot_requires_explicit_file_selection_and_policy_before_capture(self):
        destination = self.root / "not-created.json"
        complete = self.snapshot_arguments(destination)
        for flag in ("--file", "--policy"):
            index = complete.index(flag)
            arguments = complete[:index] + complete[index + 2:]
            with self.subTest(flag=flag), patch("personal_evals.cli.capture_repository") as capture:
                self.failure(arguments, "arguments_invalid")
                capture.assert_not_called()
            self.assertFalse(destination.exists())

    def test_snapshot_reads_the_committed_revision_and_ignores_dirty_and_unselected_files(self):
        (self.repo / "source.txt").write_text("DIRTY_WORKTREE_SENTINEL\n", encoding="utf-8")
        (self.repo / "untracked.txt").write_text("UNTRACKED_AUTHORED_SENTINEL\n", encoding="utf-8")
        with self.no_services(allow_git=True) as processes:
            _path, snapshot, receipt = self.snapshot()
        self.assertTrue(processes)
        self.assertEqual(receipt["commit"], self.commit); self.assertEqual(receipt["files"], 1)
        self.assertEqual(snapshot["repository"]["commit"], self.commit)
        self.assertEqual([row["path"] for row in snapshot["files"]], ["source.txt"])
        file = snapshot["files"][0]
        self.assertEqual(file["content"].encode("utf-8"), self.committed)
        self.assertEqual(file["sha256"], hashlib.sha256(self.committed).hexdigest())
        self.assertEqual(file["bytes"], len(self.committed))
        serialized = json.dumps(snapshot)
        for value in (str(self.repo), "DIRTY_WORKTREE_SENTINEL", "UNSELECTED_AUTHORED_SENTINEL", "UNTRACKED_AUTHORED_SENTINEL"):
            self.assertNotIn(value, serialized)
        self.assertEqual((self.repo / "source.txt").read_text(), "DIRTY_WORKTREE_SENTINEL\n")

    def test_invalid_snapshot_policy_is_finite_and_creates_no_artifact(self):
        self.write_json("policy.json", {"classification": "private", "permission": "authorized", "containsPersonalData": "PRIVATE_POLICY_PAYLOAD"})
        destination = self.root / "invalid-policy.json"
        error = self.failure(self.snapshot_arguments(destination), "repository_policy_invalid")
        self.assertFalse(destination.exists())
        self.assertNotIn("PRIVATE_POLICY_PAYLOAD", error); self.assertNotIn(str(self.root), error)

    def test_generation_request_is_an_unsent_deterministic_handoff_preserving_source_and_policy(self):
        snapshot_path, snapshot, _receipt = self.snapshot()
        intent_path = self.write_json("intent.json", self.intent())
        first, second = self.root / "first-request.json", self.root / "second-request.json"
        with self.no_services():
            receipt = self.success(["generation-request", snapshot_path, "--intent", intent_path, "--out", first])
            repeated = self.success(["generation-request", snapshot_path, "--intent", intent_path, "--out", second])
        self.assertIs(receipt["sent"], False); self.assertEqual(receipt, repeated)
        self.assertEqual(first.read_bytes(), second.read_bytes())
        request = self.read_json(first)
        self.assertEqual(request["snapshot"], snapshot)
        self.assertEqual(request["snapshot"]["dataPolicy"], self.policy)
        self.assertEqual(request["snapshot"]["dataPolicyFingerprint"], snapshot["dataPolicyFingerprint"])
        self.assertEqual(request["model"], "authored/generator")
        self.assertEqual(request["tasks"][0]["sourcePaths"], ["source.txt"])
        self.assertNotIn(str(self.repo), first.read_text(encoding="utf-8"))

    def test_generation_request_rejects_unselected_source_and_missing_grader_requirements(self):
        snapshot_path, _snapshot, _receipt = self.snapshot()
        for index, change in enumerate((lambda value: value["tasks"][0].update(sourcePaths=["unselected.txt"]),
                                        lambda value: value["tasks"][0].update(graderRequirements=[]),
                                        lambda value: value.update(unknown="PRIVATE_INTENT_PAYLOAD"))):
            intent = self.intent(); change(intent)
            intent_path = self.write_json(f"bad-intent-{index}.json", intent)
            destination = self.root / f"no-request-{index}.json"
            with self.subTest(index=index), self.no_services():
                error = self.failure(["generation-request", snapshot_path, "--intent", intent_path, "--out", destination])
            self.assertFalse(destination.exists()); self.assertNotIn("PRIVATE_INTENT_PAYLOAD", error)

    def test_generation_import_binds_response_to_request_snapshot_model_and_task_identity(self):
        request_path, request, _snapshot, _receipt = self.request()
        changes = (lambda row: row.update(requestId="0" * 64), lambda row: row.update(snapshotId="0" * 64),
                   lambda row: row.update(model="authored/other-model"), lambda row: row["tasks"][0].update(id="other-task"),
                   lambda row: row["tasks"][0].update(sourcePaths=["unselected.txt"]))
        for index, change in enumerate(changes):
            response = self.response(request); change(response)
            path = self.write_json(f"wrong-response-{index}.json", response)
            destination = self.root / f"no-draft-{index}"
            with self.subTest(index=index), self.no_services():
                self.failure(["generation-import", request_path, "--response", path, "--out", destination])
            self.assertFalse(destination.exists())

    def test_generation_import_creates_a_review_required_draft_without_accepting_or_executing_it(self):
        request_path, request, snapshot, _receipt = self.request()
        response_path = self.write_json("response.json", self.response(request))
        destination = self.root / "review draft"
        with self.no_services():
            receipt = self.success(["generation-import", request_path, "--response", response_path, "--out", destination])
        self.assertEqual(receipt["status"], "review_required")
        self.assertEqual(receipt["requestId"], request["requestId"])
        self.assertEqual(receipt["snapshotId"], snapshot["snapshotId"])
        self.assertEqual(self.read_json(destination / "request.json"), request)
        review = self.read_json(destination / "review.json")
        self.assertEqual(review["responseSha256"], hashlib.sha256(response_path.read_bytes()).hexdigest())
        self.assertEqual(review["taskIds"], ["task-a"])
        self.assertEqual(self.read_json(destination / "suite.json")["dataPolicy"], self.policy)
        self.assertTrue((destination / "tasks/task-a/tests/test.sh").is_file())
        self.assertFalse((destination / "bundle.json").exists())

    def test_missing_generated_grader_is_rejected_before_a_draft_can_be_created(self):
        request_path, request, _snapshot, _receipt = self.request()
        response = self.response(request)
        response["tasks"][0]["files"] = [row for row in response["tasks"][0]["files"] if row["path"] != "tests/test.sh"]
        response_path = self.write_json("missing-grader.json", response)
        destination = self.root / "no-grader-draft"
        with self.no_services():
            self.failure(["generation-import", request_path, "--response", response_path, "--out", destination], "generation_task_mismatch")
        self.assertFalse(destination.exists())

    def test_generation_accept_requires_the_reviewed_flag_and_preserves_owner_policy(self):
        draft, request, snapshot, receipt = self.draft()
        destination = self.root / "accepted bundle"
        with self.no_services():
            self.failure(["generation-accept", draft, "--out", destination], "generation_review_required")
            self.assertFalse(destination.exists())
            accepted = self.success(["generation-accept", draft, "--reviewed", "--out", destination])
        self.assertEqual(accepted["status"], "accepted")
        self.assertEqual(accepted["reviewId"], receipt["reviewId"])
        self.assertEqual(accepted["requestId"], request["requestId"])
        self.assertEqual(accepted["snapshotId"], snapshot["snapshotId"])
        bundle = verify_bundle(destination)
        self.assertEqual(bundle["bundleId"], accepted["bundleId"])
        self.assertEqual(bundle["dataPolicy"], self.policy)
        self.assertEqual(bundle["dataPolicyFingerprint"], snapshot["dataPolicyFingerprint"])
        self.assertEqual(bundle["decision"], self.intent()["decision"])
        self.assertEqual(bundle["tasks"][0]["name"], "authored/task-a")

    def test_changed_generated_files_cannot_be_accepted_under_the_old_review_identity(self):
        draft, _request, _snapshot, _receipt = self.draft()
        changed = draft / "tasks/task-a/instruction.md"
        changed.write_text("PRIVATE_TAMPERED_TASK_PAYLOAD\n", encoding="utf-8")
        destination = self.root / "not-accepted"
        with self.no_services():
            error = self.failure(["generation-accept", draft, "--reviewed", "--out", destination], "generation_draft_changed")
        self.assertFalse(destination.exists())
        self.assertEqual(changed.read_text(encoding="utf-8"), "PRIVATE_TAMPERED_TASK_PAYLOAD\n")
        self.assertNotIn("PRIVATE_TAMPERED_TASK_PAYLOAD", error)

    def test_all_four_generation_commands_preserve_existing_output_files_or_directories(self):
        draft, request, _snapshot, _receipt = self.draft()
        snapshot_path = self.root / "snapshot.json"
        intent_path, request_path = self.root / "intent.json", self.root / "request.json"
        response_path = self.root / "response.json"
        first = self.root / "existing-snapshot.json"; first.write_bytes(b"OWNED_EXISTING_SNAPSHOT\n")
        second = self.root / "existing-request.json"; second.write_bytes(b"OWNED_EXISTING_REQUEST\n")
        third = self.root / "existing-draft"; third.mkdir(); (third / "marker").write_bytes(b"OWNED_EXISTING_DRAFT\n")
        fourth = self.root / "existing-bundle"; fourth.mkdir(); (fourth / "marker").write_bytes(b"OWNED_EXISTING_BUNDLE\n")
        self.failure(self.snapshot_arguments(first), "output_exists")
        with self.no_services():
            self.failure(["generation-request", snapshot_path, "--intent", intent_path, "--out", second], "output_exists")
            self.failure(["generation-import", request_path, "--response", response_path, "--out", third], "output_exists")
            self.failure(["generation-accept", draft, "--reviewed", "--out", fourth], "output_exists")
        self.assertEqual(first.read_bytes(), b"OWNED_EXISTING_SNAPSHOT\n")
        self.assertEqual(second.read_bytes(), b"OWNED_EXISTING_REQUEST\n")
        self.assertEqual((third / "marker").read_bytes(), b"OWNED_EXISTING_DRAFT\n")
        self.assertEqual((fourth / "marker").read_bytes(), b"OWNED_EXISTING_BUNDLE\n")
        self.assertEqual(sorted(path.name for path in third.iterdir()), ["marker"])
        self.assertEqual(sorted(path.name for path in fourth.iterdir()), ["marker"])

    def test_cli_pipeline_has_no_provider_harbor_or_pr_execution_and_errors_do_not_echo_private_data(self):
        with self.no_services(allow_git=True) as processes:
            draft, _request, _snapshot, _receipt = self.draft()
            self.success(["generation-accept", draft, "--reviewed", "--out", self.root / "offline accepted"])
        self.assertTrue(processes)
        self.assertTrue(all(Path(argv[0]).resolve() == Path(self.git).resolve() for argv in processes))
        private = "PRIVATE_PROVIDER_PAYLOAD_AND_PATH"
        with patch("personal_evals.cli.capture_repository", side_effect=OSError(str(self.root / private))):
            error = self.failure(self.snapshot_arguments(self.root / "no-error-artifact.json"), "local_operation_failed")
        self.assertNotIn(private, error); self.assertNotIn(str(self.root), error)
        response = self.response(self.read_json(self.root / "request.json")); response["model"] = private
        response_path = self.write_json("private-response.json", response)
        with self.no_services():
            error = self.failure(["generation-import", self.root / "request.json", "--response", response_path, "--out", self.root / "no-private-draft"], "generation_response_mismatch")
        self.assertNotIn(private, error); self.assertNotIn(str(response_path), error)
