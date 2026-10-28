"""Authored offline fixtures only; no GitHub, Auth, process or task execution."""

import base64
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

from personal_evals.delivery import (MAX_BLOBS, MAX_DELIVERY_BYTES, build_delivery_plan,
    delivery_manifest, read_delivery_plan, validate_actor, validate_delivery_intent,
    validate_delivery_plan, validate_target, validate_timestamp, write_delivery_plan)
from personal_evals.errors import UserError
from personal_evals.suite import verify_bundle, write_bundle


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def identity(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def reseal(plan):
    plan["planId"] = identity({key: value for key, value in plan.items() if key != "planId"})
    return plan


def blob(path, data):
    return {"path": path, "mode": "100644", "encoding": "base64", "content": base64.b64encode(data).decode("ascii"),
            "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "gitBlob": hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()}


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="personal-evals-delivery-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.source = self.root / "source"
        self.source.mkdir()
        self.binary = b"\x00\xff\xfe\r\n"
        files = {"task.toml": b'schema_version="1.4"\n[task]\nname="authored/task-a"\nversion="v1"\n',
                 "instruction.md": "Authored instructions: café 🌊\r\n".encode(),
                 "environment/Dockerfile": b"FROM scratch\n", "environment/data.bin": self.binary,
                 "tests/test.sh": b"#!/bin/sh\n# Authored only; never run.\n"}
        for relative, data in files.items():
            path = self.source / "task-a" / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.suite = {"schemaVersion": 1, "id": "authored-suite", "version": "v1", "split": "holdout",
                      "decision": {"question": "Does this candidate help on selected tasks?", "minimumPairedTasks": 2,
                                   "minimumImprovement": 0.1, "maxCriticalRegressions": 0},
                      "dataPolicy": {"classification": "authored", "permission": "owned", "containsPersonalData": False},
                      "tasks": [{"id": "task-a", "path": "task-a", "files": list(files), "critical": True,
                                 "rewardKey": "reward", "successThreshold": 1}]}
        self.suite_file = self.source / "suite.json"
        self.suite_file.write_bytes(canonical_bytes(self.suite))
        self.bundle = self.root / "accepted-bundle"
        self.manifest = write_bundle(self.suite_file, self.bundle)
        self.intent = {"schemaVersion": 1,
                       "target": {"repository": "authored-owner/authored-repo", "repositoryId": 101, "visibility": "private",
                                  "baseBranch": "main", "baseCommit": "1" * 40, "newBranch": "personal-evals/authored",
                                  "pathPrefix": "evals/authored"},
                       "actor": {"login": "authored-owner", "id": 202}, "createdAt": "2026-10-28T12:00:00Z",
                       "pullRequest": {"title": "Add reviewed authored evals", "body": "Authored fixture only.\nNo task is executed.", "draft": False},
                       "purpose": "Deliver this reviewed authored task bundle"}

    def plan(self, **keywords):
        return build_delivery_plan(self.bundle, self.intent, publication_consent=True, **keywords)

    def replace_file(self, plan, path, data):
        for index, file in enumerate(plan["files"]):
            if file["path"] == path:
                plan["files"][index] = blob(path, data)
                return
        raise AssertionError("authored fixture file not found")

    def test_binary_bytes_full_inventory_and_independent_git_hashes_are_preserved(self):
        plan = self.plan()
        payload = {file["path"]: base64.b64decode(file["content"], validate=True) for file in plan["files"]}
        prefix = self.intent["target"]["pathPrefix"] + "/"
        self.assertEqual(payload[prefix + "tasks/task-a/environment/data.bin"], self.binary)
        self.assertEqual(payload[prefix + "bundle.json"], canonical_bytes(self.manifest) + b"\n")
        self.assertEqual(len(payload), 6)
        for file in plan["files"]:
            data = payload[file["path"]]
            self.assertEqual(file["bytes"], len(data))
            self.assertEqual(file["sha256"], hashlib.sha256(data).hexdigest())
            self.assertEqual(file["gitBlob"], hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest())
            self.assertEqual((file["mode"], file["encoding"]), ("100644", "base64"))
        self.assertEqual(plan["planId"], identity({key: value for key, value in plan.items() if key != "planId"}))
        self.assertEqual(plan["bundleId"], self.manifest["bundleId"])
        self.assertEqual(plan["publication"]["targetFingerprint"], identity(plan["target"]))

    def test_plan_and_embedded_manifest_validate_without_original_files(self):
        plan = self.plan()
        shutil.rmtree(self.bundle)
        self.assertEqual(validate_delivery_plan(plan), plan)
        self.assertEqual(delivery_manifest(plan), self.manifest)

    def test_consent_requires_literal_true_before_any_bundle_read(self):
        for consent in (False, None, 1, "true"):
            with patch("personal_evals.delivery.verify_bundle") as verify:
                with self.assertRaisesRegex(UserError, "delivery_consent_required"):
                    build_delivery_plan(self.bundle, self.intent, publication_consent=consent)
                verify.assert_not_called()

    def test_public_policy_restrictions_do_not_silently_change_requested_visibility_or_draft(self):
        self.intent["target"]["visibility"] = "public"
        public = self.plan()
        self.assertEqual(public["target"]["visibility"], "public")
        self.assertIs(public["pullRequest"]["draft"], False)
        for number, policy in enumerate(({"classification": "private", "permission": "owned", "containsPersonalData": False},
                                        {"classification": "authored", "permission": "authorized", "containsPersonalData": True})):
            source = copy.deepcopy(self.suite)
            source["dataPolicy"] = policy
            self.suite_file.write_bytes(canonical_bytes(source))
            bundle = self.root / f"private-{number}"
            write_bundle(self.suite_file, bundle)
            with self.assertRaisesRegex(UserError, "delivery_publication_disallowed"):
                build_delivery_plan(bundle, self.intent, publication_consent=True)
            private = copy.deepcopy(self.intent)
            private["target"]["visibility"] = "private"
            private["pullRequest"]["draft"] = True
            private_plan = build_delivery_plan(bundle, private, publication_consent=True)
            self.assertIs(private_plan["pullRequest"]["draft"], True)
            private_plan["target"]["visibility"] = "public"
            private_plan["publication"]["targetFingerprint"] = identity(private_plan["target"])
            with self.assertRaisesRegex(UserError, "delivery_publication_disallowed"):
                validate_delivery_plan(reseal(private_plan))

    def test_repository_and_numeric_identity_inputs_are_strict_and_bounded(self):
        for repository in ("https://github.com/owner/repo", "owner/repo/extra", "owner/..", "bad_owner/repo", "-owner/repo", "o" * 40 + "/repo", "owner/" + "r" * 101):
            target = {**self.intent["target"], "repository": repository}
            with self.assertRaises(UserError):
                validate_target(target)
        for value in (True, 0, -1, 2**53, "101", 1.0):
            with self.assertRaises(UserError):
                validate_target({**self.intent["target"], "repositoryId": value})
        with self.assertRaises(UserError):
            validate_target({**self.intent["target"], "provider": "github"})

    def test_branches_are_conservative_short_refs_and_distinct(self):
        for branch in ("feature/topic-1", "Release_1.2", "v1"):
            self.assertEqual(validate_target({**self.intent["target"], "newBranch": branch})["newBranch"], branch)
        for branch in ("main", "refs/heads/new", "../escape", "new..branch", ".hidden", "topic/.hidden", "topic//new", "topic/", "topic.lock", "topic.", "topic@{1}", "bad branch", "x" * 121):
            with self.assertRaises(UserError):
                validate_target({**self.intent["target"], "newBranch": branch})
        with self.assertRaises(UserError):
            validate_target({**self.intent["target"], "baseCommit": "a" * 39})

    def test_prefix_is_an_explicit_safe_ascii_relative_namespace(self):
        for prefix in ("", "/evals", "evals/../other", "evals//new", "evals/.hidden", ".github/workflows", ".git", "C:/evals", "evals\\new", "café/tasks", "x" * 121):
            with self.assertRaises(UserError):
                validate_target({**self.intent["target"], "pathPrefix": prefix})
        self.assertEqual(validate_target(self.intent["target"])["pathPrefix"], "evals/authored")

    def test_actor_timestamp_and_pr_text_are_explicit_and_not_coerced(self):
        for actor in ({"login": "app[bot]", "id": 1}, {"login": "private@example.invalid", "id": 1}, {"login": "owner", "id": True}, {"login": "o" * 40, "id": 1}):
            with self.assertRaises(UserError):
                validate_actor(actor)
        for value in ("2026-02-30T12:00:00Z", "2026-10-28T12:00:00.000Z", "2026-10-28T12:00:00+00:00", "2026-10-28", "٢٠٢٦-10-28T12:00:00Z"):
            with self.assertRaises(UserError):
                validate_timestamp(value)
        self.assertEqual(validate_timestamp("2024-02-29T23:59:59Z"), "2024-02-29T23:59:59Z")
        for field, value in (("title", "line\nbreak"), ("title", "x" * 121), ("body", "x" * 8001), ("draft", 1)):
            intent = copy.deepcopy(self.intent)
            intent["pullRequest"][field] = value
            with self.assertRaises(UserError):
                validate_delivery_intent(intent)

    def test_exact_target_actor_time_pr_mode_and_purpose_bind_recovery_identity(self):
        original = self.plan()
        self.assertEqual(self.plan(), original)
        changes = [lambda value: value["target"].update(repositoryId=102), lambda value: value["target"].update(newBranch="other-branch"),
                   lambda value: value["actor"].update(id=203), lambda value: value.update(createdAt="2026-10-28T12:00:01Z"),
                   lambda value: value["pullRequest"].update(draft=True), lambda value: value.update(purpose="Another explicit purpose")]
        for change in changes:
            intent = copy.deepcopy(self.intent)
            change(intent)
            changed = build_delivery_plan(self.bundle, intent, publication_consent=True)
            self.assertNotEqual(changed["planId"], original["planId"])
            self.assertEqual(changed["bundleId"], original["bundleId"])

    def test_blob_content_length_hash_modes_and_git_identity_are_verified(self):
        original = self.plan()
        for field, value in (("content", "eA=="), ("bytes", True), ("bytes", 999), ("sha256", "0" * 64), ("gitBlob", "0" * 40), ("mode", "120000"), ("encoding", "utf-8")):
            plan = copy.deepcopy(original)
            plan["files"][1][field] = value
            reseal(plan)
            with self.assertRaises(UserError):
                validate_delivery_plan(plan)
    def test_noncanonical_base64_is_rejected_even_when_decoded_bytes_match(self):
        original = self.plan()
        index = next(index for index, file in enumerate(original["files"]) if file["path"].endswith("/environment/data.bin"))
        encoded = original["files"][index]["content"]
        self.assertEqual(encoded, "AP/+DQo=")
        for value in (encoded + "\n", encoded + "=", "AP/+DQp=", "非ASCII"):
            plan = copy.deepcopy(original)
            plan["files"][index]["content"] = value
            reseal(plan)
            with self.assertRaises(UserError):
                validate_delivery_plan(plan)

    def test_expected_inventory_rejects_missing_extra_duplicate_and_unrooted_files(self):
        original = self.plan()
        changes = [lambda value: value["files"].pop(), lambda value: value["files"].append(copy.deepcopy(value["files"][-1])),
                   lambda value: value["files"].append(blob("evals/authored/request.json", b"unselected")),
                   lambda value: value["files"][0].update(path="elsewhere/bundle.json")]
        for change in changes:
            plan = copy.deepcopy(original)
            change(plan)
            plan["files"].sort(key=lambda file: file["path"])
            reseal(plan)
            with self.assertRaises(UserError):
                validate_delivery_plan(plan)
        plan = copy.deepcopy(original)
        plan["files"].reverse()
        reseal(plan)
        with self.assertRaises(UserError):
            validate_delivery_plan(plan)

    def test_rehashed_manifest_cannot_relabel_toml_and_manifest_bytes_are_canonical(self):
        plan = self.plan()
        manifest_path = self.intent["target"]["pathPrefix"] + "/bundle.json"
        self.replace_file(plan, manifest_path, json.dumps(self.manifest, indent=2).encode())
        with self.assertRaises(UserError):
            validate_delivery_plan(reseal(plan))
        manifest = copy.deepcopy(self.manifest)
        manifest["tasks"][0]["name"] = "authored/other"
        manifest["sampleManifestId"] = identity(manifest["tasks"])
        manifest["bundleId"] = identity({key: value for key, value in manifest.items() if key != "bundleId"})
        plan = self.plan()
        plan["bundleId"] = plan["publication"]["bundleId"] = manifest["bundleId"]
        self.replace_file(plan, manifest_path, canonical_bytes(manifest) + b"\n")
        with self.assertRaisesRegex(UserError, "delivery_bundle_mismatch"):
            validate_delivery_plan(reseal(plan))

    def test_nfc_casefold_and_file_directory_collisions_are_detected(self):
        extra_sets = [[blob("evals/authored/tasks/task-a/environment/Data.Bin", self.binary)],
                      [blob("evals/authored/tasks/task-a/environment/data.bin/child.txt", b"child")],
                      [blob("evals/authored/tasks/task-a/environment/Caf\u00e9/a.txt", b"a"),
                       blob("evals/authored/tasks/task-a/environment/Cafe\u0301/b.txt", b"b")]]
        for extras in extra_sets:
            plan = self.plan()
            plan["files"].extend(extras)
            plan["files"].sort(key=lambda file: file["path"])
            with self.assertRaisesRegex(UserError, "delivery_path_collision"):
                validate_delivery_plan(reseal(plan))

    def test_unknown_metadata_weakened_preconditions_and_retargeted_consent_are_rejected(self):
        changes = [lambda value: value.update(extra="private trace"), lambda value: value["publication"].update(operatorConfirmed=1),
                   lambda value: value["preconditions"].update(pathPrefixAbsent=False),
                   lambda value: value["preconditions"].update(baseUnchanged=1),
                   lambda value: value["target"].update(repositoryId=999), lambda value: value.update(planId="0" * 64)]
        for change in changes:
            plan = self.plan()
            change(plan)
            with self.assertRaises(UserError):
                validate_delivery_plan(plan)
        retargeted = self.plan()
        retargeted["target"]["repositoryId"] = 999
        with self.assertRaisesRegex(UserError, "delivery_consent_required"):
            validate_delivery_plan(reseal(retargeted))

    def test_validation_returns_detached_plan_and_manifest_without_rewriting_intent(self):
        original = copy.deepcopy(self.intent)
        plan = self.plan()
        validated = validate_delivery_plan(plan)
        validated["target"]["repositoryId"] = 999
        validated["files"][0]["bytes"] = 0
        self.assertEqual(self.intent, original)
        self.assertEqual(plan["target"]["repositoryId"], 101)
        self.assertNotEqual(plan["files"][0]["bytes"], 0)
        manifest = delivery_manifest(plan)
        manifest["tasks"][0]["critical"] = False
        self.assertIs(delivery_manifest(plan)["tasks"][0]["critical"], True)

    def test_plan_byte_boundary_uses_small_fixtures_and_explicit_large_artifact_limit(self):
        self.assertEqual(MAX_DELIVERY_BYTES, 64 * 1024 * 1024)
        self.assertEqual(MAX_BLOBS, 10001)
        plan = self.plan()
        size = len(canonical_bytes(plan)) + 1
        output = self.root / "at-limit.json"
        with patch("personal_evals.delivery.MAX_DELIVERY_BYTES", size):
            write_delivery_plan(plan, output)
            self.assertEqual(read_delivery_plan(output), plan)
        with patch("personal_evals.delivery.MAX_DELIVERY_BYTES", size - 1):
            for action in (lambda: validate_delivery_plan(plan), lambda: read_delivery_plan(output),
                           lambda: write_delivery_plan(plan, self.root / "too-large.json")):
                with self.assertRaises(UserError):
                    action()
        self.assertFalse((self.root / "too-large.json").exists())
        with patch("personal_evals.delivery.MAX_BLOBS", len(plan["files"]) - 1):
            with self.assertRaisesRegex(UserError, "delivery_inventory_invalid"):
                validate_delivery_plan(plan)

    def test_private_output_is_complete_exclusive_and_preserves_existing_links(self):
        plan = self.plan()
        output = self.root / "delivery.json"
        receipt = write_delivery_plan(plan, output)
        original = output.read_bytes()
        self.assertEqual(original, canonical_bytes(plan) + b"\n")
        self.assertEqual(receipt, {"planId": plan["planId"], "bundleId": plan["bundleId"], "files": len(plan["files"]),
                                   "bytes": len(original), "sha256": hashlib.sha256(original).hexdigest()})
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
        with self.assertRaisesRegex(UserError, "output_exists"):
            write_delivery_plan(plan, output)
        link = self.root / "linked.json"
        link.symlink_to(output)
        with self.assertRaisesRegex(UserError, "output_exists"):
            write_delivery_plan(plan, link)
        with self.assertRaises(UserError):
            read_delivery_plan(link)
        self.assertEqual(output.read_bytes(), original)
        self.assertTrue(link.is_symlink())
        with patch("personal_evals.jsonio.os.link", side_effect=OSError("authored publication failure")):
            with self.assertRaises(UserError):
                write_delivery_plan(plan, self.root / "failed-output.json")
        self.assertFalse((self.root / "failed-output.json").exists())
        self.assertFalse(list(self.root.glob(".personal-evals-*")))

    def test_bundle_change_after_initial_verification_is_rejected_during_capture(self):
        def changed(path):
            manifest = verify_bundle(path)
            (path / "tasks/task-a/environment/data.bin").write_bytes(b"changed after verification")
            return manifest

        with patch("personal_evals.delivery.verify_bundle", side_effect=changed):
            with self.assertRaisesRegex(UserError, "delivery_bundle_changed"):
                self.plan()

    def test_no_process_network_or_private_source_context_is_automatically_exported(self):
        sentinel = b"PRIVATE_SOURCE_CONTEXT_SENTINEL"
        (self.source / "request.json").write_bytes(sentinel)
        with patch("subprocess.Popen", side_effect=AssertionError("no process")), \
             patch("socket.create_connection", side_effect=AssertionError("no network")), \
             patch("urllib.request.urlopen", side_effect=AssertionError("no provider")):
            plan = self.plan()
            validate_delivery_plan(plan)
        self.assertTrue(all(sentinel not in base64.b64decode(file["content"]) for file in plan["files"]))
        self.assertEqual([file["path"].split("/", 2)[2] for file in plan["files"] if file["path"].endswith("/bundle.json")], ["bundle.json"])
        self.assertNotIn(str(self.root), json.dumps(plan))


if __name__ == "__main__":
    unittest.main()
