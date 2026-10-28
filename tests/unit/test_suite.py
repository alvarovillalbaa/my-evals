"""Authored T2 filesystem fixtures only; no Harbor/model/container execution."""

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
from personal_evals.suite import (HARBOR_COMMIT, MAX_FILE_BYTES, MAX_TOTAL_BYTES,
                                  prepare_suite, validate_manifest, verify_bundle, write_bundle)


def identity(value):
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def reseal(manifest):
    manifest["dataPolicyFingerprint"] = identity(manifest["dataPolicy"])
    manifest["sampleManifestId"] = identity(manifest["tasks"])
    manifest.pop("bundleId", None)
    manifest["bundleId"] = identity(manifest)
    return manifest


class SuiteTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="personal-evals-suite-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.suite_file = self.root / "suite.json"
        self.tasks = []
        for number in (1, 2):
            task_id = f"case-{number}"
            folder = self.root / task_id
            files = {
                "task.toml": f'schema_version = "1.4"\n[task]\nname = "authored/{task_id}"\nversion = "v1"\n'.encode(),
                "instruction.md": b"# Authored task\r\nPreserve these bytes.\r\n",
                "environment/Dockerfile": b"FROM scratch\n",
                "tests/test.sh": b"#!/bin/sh\n# Authored only; this file is never run.\n",
                "solution/solve.sh": b"#!/bin/sh\n# Authored reference; never run.\n",
            }
            for relative, data in files.items():
                path = folder / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            self.tasks.append({"id": task_id, "path": task_id, "files": list(files), "critical": number == 1,
                               "rewardKey": "reward", "successThreshold": 0.75})
        self.source = {"schemaVersion": 1, "id": "authored-suite", "version": "v1", "split": "holdout",
                       "decision": {"question": "Does the candidate improve this authored workload?", "minimumPairedTasks": 2,
                                    "minimumImprovement": 0.1, "maxCriticalRegressions": 0},
                       "dataPolicy": {"classification": "authored", "permission": "owned", "containsPersonalData": False},
                       "tasks": self.tasks}
        self.write_source()

    def write_source(self, value=None):
        self.suite_file.write_text(json.dumps(self.source if value is None else value), encoding="utf-8")

    def bundle(self, name="bundle"):
        destination = self.root / name
        manifest = write_bundle(self.suite_file, destination)
        return destination, manifest

    def write_manifest(self, bundle, manifest):
        (bundle / "bundle.json").write_text(json.dumps(manifest), encoding="utf-8")

    def test_explicit_bytes_and_independent_harbor_digest(self):
        extra = self.root / "case-1/environment/credentials.json"
        extra.write_bytes(b"unselected authored sentinel")
        (self.root / "case-1/environment/asset.bin").write_bytes(b"\x00\xff\r\n")
        self.tasks[0]["files"].append("environment/asset.bin")
        self.write_source()
        manifest, payload = prepare_suite(self.suite_file)
        self.assertEqual(payload["tasks/case-1/instruction.md"], b"# Authored task\r\nPreserve these bytes.\r\n")
        self.assertEqual(payload["tasks/case-1/environment/asset.bin"], b"\x00\xff\r\n")
        self.assertNotIn("tasks/case-1/environment/credentials.json", payload)
        for task in manifest["tasks"]:
            lines = []
            for file in task["files"]:
                data = payload[f"tasks/{task['id']}/{file['path']}"]
                hashed = hashlib.sha256(data).hexdigest()
                self.assertEqual(file["sha256"], hashed)
                self.assertEqual(file["bytes"], len(data))
                lines.append(file["path"] + "\0" + hashed + "\n")
            self.assertEqual(task["harborDigest"], "sha256:" + hashlib.sha256("".join(lines).encode()).hexdigest())
        self.assertEqual(manifest["harbor"]["sourceCommit"], HARBOR_COMMIT)
        self.assertEqual(manifest["sampleManifestId"], identity(manifest["tasks"]))
        prior = {key: value for key, value in manifest.items() if key != "bundleId"}
        self.assertEqual(manifest["bundleId"], identity(prior))
        self.assertNotIn(str(self.root), json.dumps(manifest))

    def test_private_bundle_roundtrip_remains_valid_after_transfer(self):
        bundle, manifest = self.bundle()
        self.assertEqual(verify_bundle(bundle), manifest)
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(bundle.stat().st_mode), 0o700)
            for path in bundle.rglob("*"):
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700 if path.is_dir() else 0o600)
        moved = self.root / "transferred"
        shutil.copytree(bundle, moved)
        self.assertEqual(verify_bundle(moved), manifest)

    def test_policy_decision_split_task_order_and_grader_settings_bind_identity(self):
        original, _ = prepare_suite(self.suite_file)
        changes = [lambda source: source.update(split="blind_holdout"),
                   lambda source: source["decision"].update(minimumImprovement=0.2),
                   lambda source: source["dataPolicy"].update(containsPersonalData=True),
                   lambda source: source["tasks"].reverse(),
                   lambda source: source["tasks"][0].update(critical=False),
                   lambda source: source["tasks"][0].update(rewardKey="accuracy"),
                   lambda source: source["tasks"][0].update(successThreshold=0.9)]
        for change in changes:
            source = copy.deepcopy(self.source)
            change(source)
            self.write_source(source)
            modified, _ = prepare_suite(self.suite_file)
            self.assertNotEqual(modified["bundleId"], original["bundleId"])
        self.assertEqual(original["tasks"][0]["id"], "case-1")

    def test_strict_suite_scalars_and_unknown_fields_are_rejected(self):
        changes = [lambda source: source.update(schemaVersion=True), lambda source: source.update(extra="unapproved"),
                   lambda source: source.update(id="../escape"), lambda source: source.update(version=""),
                   lambda source: source.update(split="training"),
                   lambda source: source["decision"].update(minimumPairedTasks=True),
                   lambda source: source["decision"].update(minimumPairedTasks=1),
                   lambda source: source["decision"].update(maxCriticalRegressions=-1),
                   lambda source: source["decision"].update(minimumImprovement=float("nan")),
                   lambda source: source["decision"].update(minimumImprovement=10**400),
                   lambda source: source["dataPolicy"].update(permission="publicly-found"),
                   lambda source: source["dataPolicy"].update(containsPersonalData="false"),
                   lambda source: source["tasks"][0].update(critical=1),
                   lambda source: source["tasks"][0].update(successThreshold=True)]
        for change in changes:
            source = copy.deepcopy(self.source)
            change(source)
            self.write_source(source)
            with self.assertRaises(UserError):
                prepare_suite(self.suite_file)

    def test_empty_excessive_duplicate_task_ids_and_harbor_names_are_rejected(self):
        for tasks in ([], [copy.deepcopy(self.tasks[0])] * 101, [self.tasks[0], self.tasks[0]]):
            self.write_source({**self.source, "tasks": tasks})
            with self.assertRaises(UserError):
                prepare_suite(self.suite_file)
        self.write_source()
        path = self.root / "case-2/task.toml"
        path.write_bytes((self.root / "case-1/task.toml").read_bytes())
        with self.assertRaises(UserError):
            prepare_suite(self.suite_file)

    def test_required_explicit_files_and_supported_locations_are_enforced(self):
        for missing in ("task.toml", "instruction.md", "environment/Dockerfile", "tests/test.sh"):
            source = copy.deepcopy(self.source)
            source["tasks"][0]["files"].remove(missing)
            self.write_source(source)
            with self.assertRaises(UserError):
                prepare_suite(self.suite_file)
        for forbidden in ("package.json", "other/instruction.md", "environment", "task.toml/child"):
            source = copy.deepcopy(self.source)
            source["tasks"][0]["files"].append(forbidden)
            self.write_source(source)
            with self.assertRaises(UserError):
                prepare_suite(self.suite_file)

    def test_relative_paths_reject_traversal_absolute_and_ambiguous_segments(self):
        for path in ("../case-1", "/case-1", "case-1/../case-2", "case-1//nested", "./case-1", "C:/case-1", "case-1\\nested"):
            source = copy.deepcopy(self.source)
            source["tasks"][0]["path"] = path
            self.write_source(source)
            with self.assertRaises(UserError):
                prepare_suite(self.suite_file)
        for path in ("../outside", "/instruction.md", "tests/../task.toml", "tests//test.sh", "tests/./test.sh", "tests\\test.sh"):
            source = copy.deepcopy(self.source)
            source["tasks"][0]["files"].append(path)
            self.write_source(source)
            with self.assertRaises(UserError):
                prepare_suite(self.suite_file)

    def test_secret_filenames_are_rejected_without_reading_them(self):
        for path in ("environment/.env", "environment/.env.local", "tests/credentials.json", "solution/id_rsa", "environment/client.key", "environment/server.pem", "environment/.ssh/config", "environment/api_key.txt", "environment/service_account.json",
                     "tests/__pycache__/cached.py", "tests/cached.pyc", "tests/edit.swp", "tests/edit.swo", "solution/draft~", "tests/.DS_Store"):
            source = copy.deepcopy(self.source)
            source["tasks"][0]["files"].append(path)
            self.write_source(source)
            with self.assertRaisesRegex(UserError, "task_file_forbidden"):
                prepare_suite(self.suite_file)

    def test_symlink_task_directory_selected_file_and_ancestor_are_rejected(self):
        (self.root / "task-link").symlink_to(self.root / "case-1", target_is_directory=True)
        source = copy.deepcopy(self.source)
        source["tasks"][0]["path"] = "task-link"
        self.write_source(source)
        with self.assertRaisesRegex(UserError, "symlink_forbidden"):
            prepare_suite(self.suite_file)
        instruction = self.root / "case-1/instruction.md"
        instruction.unlink()
        instruction.symlink_to(self.root / "case-2/instruction.md")
        self.write_source()
        with self.assertRaisesRegex(UserError, "symlink_forbidden"):
            prepare_suite(self.suite_file)
        instruction.unlink()
        instruction.write_bytes(b"Restored authored text\n")
        shutil.rmtree(self.root / "case-1/tests")
        (self.root / "case-1/tests").symlink_to(self.root / "case-2/tests", target_is_directory=True)
        with self.assertRaisesRegex(UserError, "symlink_forbidden"):
            prepare_suite(self.suite_file)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX FIFO fixture")
    def test_nonregular_selected_file_is_rejected_before_read(self):
        path = self.root / "case-1/tests/test.sh"
        path.unlink()
        os.mkfifo(path)
        with self.assertRaises(UserError):
            prepare_suite(self.suite_file)

    def test_per_file_and_aggregate_byte_limits(self):
        self.assertEqual(MAX_FILE_BYTES, 1024 * 1024)
        self.assertEqual(MAX_TOTAL_BYTES, 32 * 1024 * 1024)
        oversized = self.root / "case-1/environment/large.bin"
        oversized.write_bytes(b"x" * (MAX_FILE_BYTES + 1))
        source = copy.deepcopy(self.source)
        source["tasks"][0]["files"].append("environment/large.bin")
        self.write_source(source)
        with self.assertRaises(UserError):
            prepare_suite(self.suite_file)
        oversized.unlink()
        self.write_source()
        total = sum((self.root / task["path"] / path).stat().st_size for task in self.tasks for path in task["files"])
        with patch("personal_evals.suite.MAX_TOTAL_BYTES", total):
            _manifest, payload = prepare_suite(self.suite_file)
            self.assertEqual(sum(map(len, payload.values())), total)
        with patch("personal_evals.suite.MAX_TOTAL_BYTES", total - 1):
            with self.assertRaises(UserError):
                prepare_suite(self.suite_file)

    def test_file_count_duplicates_and_portable_case_collisions_are_rejected(self):
        for paths in (["tests/test.sh"] * 101, self.tasks[0]["files"] + ["tests/test.sh"],
                      self.tasks[0]["files"] + ["tests/TEST.sh"]):
            source = copy.deepcopy(self.source)
            source["tasks"][0]["files"] = paths
            self.write_source(source)
            with self.assertRaises(UserError):
                prepare_suite(self.suite_file)

    def test_task_schema_identity_version_utf8_and_multistep_are_validated(self):
        valid = (self.root / "case-1/task.toml").read_bytes()
        invalid = [b"\xff", b"not = [valid", valid.replace(b'"1.4"', b'"1.3"'),
                   b'schema_version="1.4"\n[task]\nversion="v1"\n',
                   b'schema_version="1.4"\n[task]\nname="authored/case-1"\n',
                   valid.replace(b"authored/case-1", b"not-namespaced"),
                   b"steps=[]\n" + valid, b'multi_step_reward_strategy="mean"\n' + valid,
                   b'version="1.0"\n' + valid, b'version="1.4"\n' + valid]
        for data in invalid:
            (self.root / "case-1/task.toml").write_bytes(data)
            with self.assertRaises(UserError):
                prepare_suite(self.suite_file)

    def test_manifest_metadata_fingerprints_and_exact_shape_are_checked(self):
        _, original = self.bundle()
        changes = [lambda manifest: manifest.update(extra="unapproved"),
                   lambda manifest: manifest["harbor"].update(sourceCommit="0" * 40),
                   lambda manifest: manifest["decision"].update(minimumImprovement=0.2),
                   lambda manifest: manifest["dataPolicy"].update(permission="authorized"),
                   lambda manifest: manifest["tasks"].reverse(),
                   lambda manifest: manifest["tasks"][0]["files"][0].update(sha256="0" * 64)]
        for change in changes:
            manifest = copy.deepcopy(original)
            change(manifest)
            with self.assertRaises(UserError):
                validate_manifest(manifest)

    def test_tampered_file_bytes_or_lengths_never_verify(self):
        bundle, _ = self.bundle()
        path = bundle / "tasks/case-1/instruction.md"
        original = path.read_bytes()
        for data in (b"!" + original[1:], original + b"extra"):
            path.write_bytes(data)
            with self.assertRaisesRegex(UserError, "bundle_hash_mismatch"):
                verify_bundle(bundle)

    def test_bundle_inventory_rejects_extra_files_directories_missing_files_and_links(self):
        bundle, _ = self.bundle()
        extra = bundle / "extra.txt"
        extra.write_bytes(b"not selected")
        with self.assertRaisesRegex(UserError, "bundle_inventory_mismatch"):
            verify_bundle(bundle)
        extra.unlink()
        extra.mkdir()
        with self.assertRaisesRegex(UserError, "bundle_inventory_mismatch"):
            verify_bundle(bundle)
        extra.rmdir()
        extra.symlink_to(self.root / "suite.json")
        with self.assertRaisesRegex(UserError, "symlink_forbidden"):
            verify_bundle(bundle)
        extra.unlink()
        (bundle / "tasks/case-1/instruction.md").unlink()
        with self.assertRaises(UserError):
            verify_bundle(bundle)

    def test_rehashed_metadata_cannot_substitute_a_different_toml_identity(self):
        bundle, manifest = self.bundle()
        manifest["tasks"][0]["name"] = "authored/renamed"
        manifest = reseal(manifest)
        self.assertEqual(validate_manifest(manifest), manifest)
        self.write_manifest(bundle, manifest)
        with self.assertRaisesRegex(UserError, "bundle_hash_mismatch"):
            verify_bundle(bundle)

    def test_existing_output_directory_file_or_link_is_never_overwritten(self):
        directory = self.root / "already-there"
        directory.mkdir()
        (directory / "sentinel").write_bytes(b"preserve me")
        file = self.root / "existing-file"
        file.write_bytes(b"preserve file")
        link = self.root / "existing-link"
        link.symlink_to(directory, target_is_directory=True)
        for output in (directory, file, link):
            with self.assertRaisesRegex(UserError, "output_exists"):
                write_bundle(self.suite_file, output)
        self.assertEqual((directory / "sentinel").read_bytes(), b"preserve me")
        self.assertEqual(file.read_bytes(), b"preserve file")
        self.assertTrue(link.is_symlink())

    def test_write_failure_removes_only_owned_outputs_and_preserves_a_foreign_file(self):
        destination = self.root / "failed-bundle"

        def reject(path):
            (path / "foreign-sentinel").write_bytes(b"another writer")
            raise UserError("authored_failure")

        with patch("personal_evals.suite.verify_bundle", side_effect=reject):
            with self.assertRaisesRegex(UserError, "authored_failure"):
                write_bundle(self.suite_file, destination)
        self.assertEqual(list(destination.iterdir()), [destination / "foreign-sentinel"])
        self.assertEqual((destination / "foreign-sentinel").read_bytes(), b"another writer")
        self.assertTrue((self.root / "case-1/instruction.md").exists())

    def test_manifest_validation_detaches_data_and_source_relocation_does_not_change_ids(self):
        original, _ = prepare_suite(self.suite_file)
        detached = validate_manifest(original)
        detached["tasks"][0]["files"][0]["bytes"] = 0
        self.assertNotEqual(detached, original)
        relocated = self.root / "relocated"
        relocated.mkdir()
        for task in self.tasks:
            shutil.copytree(self.root / task["path"], relocated / task["path"])
        (relocated / "suite.json").write_bytes(self.suite_file.read_bytes())
        moved, _ = prepare_suite(relocated / "suite.json")
        self.assertEqual(moved, original)


if __name__ == "__main__":
    unittest.main()
