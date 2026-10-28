"""Authored T2 files only; these fixtures do not run Harbor or any task command."""

import copy
import json
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from personal_evals.errors import UserError
from personal_evals.harbor import HARBOR_SOURCE_COMMIT, import_job, reported_model_matches
from personal_evals.jsonio import canonical, digest, sha256
from personal_evals.planning import build_plan
from personal_evals.suite import write_bundle


class HarborImportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        source = self.root / "source"
        source.mkdir()
        files = {
            "task.toml": 'schema_version = "1.4"\n[task]\nname = "authored/example"\nversion = "1.0.0"\n[verifier]\nenvironment_mode = "shared"\n',
            "instruction.md": "Write the authored greeting.\n",
            "environment/Dockerfile": "FROM python:3.12-slim\nWORKDIR /app\n",
            "tests/test.sh": "#!/bin/sh\nprintf '1' > /logs/verifier/reward.txt\n",
            "solution/solve.sh": "#!/bin/sh\nprintf 'authored greeting'\n",
        }
        for name, content in files.items():
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        suite = {"schemaVersion": 1, "id": "authored", "version": "1.0.0", "split": "holdout",
                 "decision": {"question": "Authored format fixture, never model evidence", "minimumPairedTasks": 2,
                              "minimumImprovement": 0.1, "maxCriticalRegressions": 0},
                 "dataPolicy": {"classification": "authored", "permission": "owned", "containsPersonalData": False},
                 "tasks": [{"id": "example", "path": "source", "files": sorted(files), "critical": True,
                            "rewardKey": "reward", "successThreshold": 1}]}
        suite_file = self.root / "suite.json"
        self.write(suite_file, suite)
        self.bundle = self.root / "bundle"
        self.manifest = write_bundle(suite_file, self.bundle)
        self.plan = build_plan(self.manifest, model="provider/model", agent="codex", agent_version="1.0.0", attempts=1)
        self.job = self.root / "job"
        self.job.mkdir()
        self.job_id = str(uuid4())
        self.result, self.lock = self.trial()
        self.persist()

    @staticmethod
    def write(path, value):
        path.write_bytes(canonical(value) + b"\n")

    def trial(self):
        agent = {"name": "codex", "model_name": "provider/model", "kwargs": {"version": "1.0.0"}}
        environment = {"type": "docker"}
        task = self.manifest["tasks"][0]
        task_path = "/private/authored-fixture/tasks/example"
        lock = {"schema_version": 2, "task": {"name": "example", "version": task["version"], "type": "local",
                "digest": task["harborDigest"], "source": "tasks", "path": task_path},
                "agent": copy.deepcopy(agent), "environment": environment.copy(), "verifier": {"environment_mode": "shared"}}
        result = {"id": str(uuid4()), "task_name": task["name"], "trial_name": "example__authored",
                  "trial_uri": "file:///private/never-retained", "task_id": {"path": task_path}, "source": "tasks",
                  "task_checksum": "0" * 64,
                  "config": {"task": {"path": task_path, "source": "tasks"}, "trial_name": "example__authored",
                             "job_id": self.job_id, "agent": copy.deepcopy(agent), "environment": environment.copy(), "verifier": {}},
                  "agent_info": {"name": "codex", "version": "1.0.0", "model_info": {"name": "model", "provider": "provider"}},
                  "agent_result": {"n_input_tokens": 10, "n_cache_tokens": 2, "n_output_tokens": 3, "cost_usd": 0.001,
                                   "metadata": {"private": "raw-token-never-retained"}},
                  "verifier_result": {"rewards": {"reward": 1}}, "exception_info": None,
                  "started_at": "2026-10-28T12:00:00+00:00", "finished_at": "2026-10-28T12:00:02+00:00", "step_results": None}
        return result, lock

    def persist(self, *, results=None, locks=None):
        results = [self.result] if results is None else results
        locks = [self.lock] if locks is None else locks
        self.write(self.job / "result.json", {"id": self.job_id, "n_total_trials": len(results), "stats": {}})
        self.write(self.job / "lock.json", {"schema_version": 3, "harbor": {"version": "authored-fixture", "git_commit_hash": HARBOR_SOURCE_COMMIT},
                   "n_concurrent_trials": 1, "retry": {"max_retries": 0}, "trials": locks})
        for index, (result, lock) in enumerate(zip(results, locks)):
            directory = self.job / f"trial-{index}"
            directory.mkdir(exist_ok=True)
            self.write(directory / "result.json", result)
            self.write(directory / "lock.json", lock)

    def imported(self):
        return import_job(self.bundle, self.plan, self.job)

    def test_valid_trial_binds_seal_plan_and_real_harbor_result_shape(self):
        run = self.imported()
        row = run["trials"][0]
        self.assertEqual((row["status"], row["reward"], row["durationSeconds"]), ("valid", 1, 2))
        self.assertEqual(row["taskId"], "example")
        self.assertEqual(row["errors"], [])
        self.assertEqual(row["reasons"], [])
        self.assertEqual(run["planId"], self.plan["planId"])
        self.assertEqual(run["runId"], digest({key: value for key, value in run.items() if key != "runId"}))
        self.assertEqual(row["sourceHashes"]["result"], sha256((self.job / "trial-0/result.json").read_bytes()))
        self.assertEqual(row["sourceHashes"]["lock"], sha256((self.job / "trial-0/lock.json").read_bytes()))

    def test_normalized_output_omits_paths_tokens_metadata_and_traces(self):
        self.result["exception_info"] = {"exception_type": "ApiError", "exception_message": "raw-token-never-retained",
                                         "exception_traceback": "/private/authored-only", "occurred_at": "2026-10-28T12:00:01Z"}
        self.persist()
        text = json.dumps(self.imported())
        for private in ("/private/", "raw-token-never-retained", "exception_message", "exception_traceback", "metadata", "trial_uri"):
            self.assertNotIn(private, text)

    def test_missing_lock_excludes_reward_without_inventing_provenance(self):
        (self.job / "trial-0/lock.json").unlink()
        row = self.imported()["trials"][0]
        self.assertEqual(row["status"], "excluded")
        self.assertIn("lock_missing", row["reasons"])
        self.assertEqual(row["reward"], 1)
        self.assertIsNone(row["sourceHashes"]["lock"])

    def test_malformed_lock_keeps_its_bytes_hash_but_never_validates(self):
        data = b"{not-json"
        (self.job / "trial-0/lock.json").write_bytes(data)
        row = self.imported()["trials"][0]
        self.assertIn("lock_invalid", row["reasons"])
        self.assertEqual(row["sourceHashes"]["lock"], sha256(data))

    def test_task_digest_version_and_local_name_must_match_the_sealed_bundle(self):
        original = copy.deepcopy(self.lock)
        for key, value in (("digest", "sha256:" + "f" * 64), ("version", "different"), ("name", "different")):
            with self.subTest(key=key):
                self.lock = copy.deepcopy(original)
                self.lock["task"][key] = value
                self.persist()
                self.assertIn("task_provenance_mismatch", self.imported()["trials"][0]["reasons"])

    def test_bundle_file_tampering_is_rejected_before_reading_results(self):
        (self.bundle / "tasks/example/instruction.md").write_text("Changed task after sealing")
        with self.assertRaises(UserError):
            self.imported()

    def test_root_harbor_pin_schema_concurrency_and_retry_are_required(self):
        path = self.job / "lock.json"
        original = json.loads(path.read_text())
        for key, value in (("schema_version", 2), ("n_concurrent_trials", 2), ("retry", {"max_retries": 1}),
                           ("harbor", {"version": "fixture", "git_commit_hash": "0" * 40})):
            with self.subTest(key=key):
                changed = copy.deepcopy(original); changed[key] = value
                self.write(path, changed)
                with self.assertRaises(UserError):
                    self.imported()

    def test_trial_lock_must_be_recorded_in_the_root_job_lock(self):
        self.persist(locks=[])
        # Preserve the existing independently written trial files.
        self.assertIn("lock_invalid", self.imported()["trials"][0]["reasons"])

    def test_config_job_and_model_and_reported_identity_cannot_cross_plans(self):
        original = copy.deepcopy(self.result)
        changes = [("job_mismatch", lambda row: row["config"].update(job_id=str(uuid4()))),
                   ("model_mismatch", lambda row: row["config"]["agent"].update(model_name="other/model")),
                   ("model_mismatch", lambda row: row["agent_info"]["model_info"].update(provider="other")),
                   ("agent_mismatch", lambda row: row["agent_info"].update(version="different"))]
        for reason, change in changes:
            with self.subTest(reason=reason):
                self.result = copy.deepcopy(original); change(self.result); self.persist()
                self.assertIn(reason, self.imported()["trials"][0]["reasons"])

    def test_unknown_task_and_missing_model_are_explicit_excluded_evidence(self):
        self.result["task_name"] = "authored/unknown"
        self.result["agent_info"]["model_info"] = None
        self.persist()
        row = self.imported()["trials"][0]
        self.assertIsNone(row["taskId"])
        self.assertEqual(row["reportedModel"], {"name": "unknown", "provider": None})
        self.assertTrue({"unknown_task", "model_mismatch"}.issubset(row["reasons"]))

    def test_duplicate_trial_uuid_is_rejected_across_directories(self):
        self.persist(results=[self.result, copy.deepcopy(self.result)], locks=[self.lock, copy.deepcopy(self.lock)])
        with self.assertRaisesRegex(UserError, "harbor_duplicate_trial"):
            self.imported()

    def test_raw_trial_and_step_errors_are_preserved_without_becoming_zero(self):
        self.result["exception_info"] = {"exception_type": "AgentTimeoutError"}
        self.result["step_results"] = [{"exception_info": {"exception_type": "VerifierTimeoutError"}}]
        self.persist()
        row = self.imported()["trials"][0]
        self.assertEqual(row["reward"], 1)
        self.assertEqual(row["status"], "excluded")
        self.assertEqual(row["errors"], [{"type": "AgentTimeoutError", "stage": "trial"}, {"type": "VerifierTimeoutError", "stage": "step"}])

    def test_missing_out_of_range_and_boolean_rewards_stay_unknown(self):
        for value in (None, -0.1, 1.1, True, "1"):
            with self.subTest(value=value):
                self.result["verifier_result"] = {"rewards": {"reward": value}}
                self.persist()
                row = self.imported()["trials"][0]
                self.assertEqual(row["status"], "excluded")
                self.assertIsNone(row["reward"])

    def test_workload_overrides_are_excluded_even_when_reward_is_present(self):
        original = copy.deepcopy(self.result)
        for key, value in (("extra_instructions", ["Change the question"]), ("source_trial", {"action": "regrade"}),
                           ("timeout_multiplier", 2), ("unrecognized_future_option", True)):
            with self.subTest(key=key):
                self.result = copy.deepcopy(original)
                self.result["config"][key] = value; self.persist()
                self.assertIn("workload_override", self.imported()["trials"][0]["reasons"])

    def test_unknown_usage_is_not_zero_and_input_already_contains_cache(self):
        self.result["agent_result"] = {"n_input_tokens": 10, "n_cache_tokens": 4}
        self.persist()
        usage = self.imported()["trials"][0]["usage"]
        self.assertEqual(usage, {"inputTokens": 10, "cacheTokens": 4, "outputTokens": None, "costUsd": None})
        self.result["agent_result"]["n_cache_tokens"] = 20; self.persist()
        row = self.imported()["trials"][0]
        self.assertIn("usage_invalid", row["reasons"])
        self.assertIsNone(row["usage"]["inputTokens"])
        self.assertIsNone(row["usage"]["cacheTokens"])
        self.result["agent_result"] = {"n_input_tokens": 10**400, "cost_usd": True}; self.persist()
        row = self.imported()["trials"][0]
        self.assertIn("usage_invalid", row["reasons"])
        self.assertIsNone(row["usage"]["inputTokens"])
        self.assertIsNone(row["usage"]["costUsd"])

    def test_usage_chooses_top_level_or_steps_without_double_counting(self):
        self.result["step_results"] = [{"agent_result": {"n_input_tokens": 100, "cost_usd": 0.2}}]
        self.persist()
        self.assertEqual(self.imported()["trials"][0]["usage"]["inputTokens"], 10)
        self.result["agent_result"] = None
        self.result["step_results"].append({"agent_result": {"n_input_tokens": 20}})
        self.persist()
        usage = self.imported()["trials"][0]["usage"]
        self.assertEqual(usage["inputTokens"], 120)
        self.assertIsNone(usage["costUsd"])

    def test_missing_and_naive_or_reversed_trial_times_are_not_invented(self):
        for value, reason in ((None, "result_incomplete"), ("2026-10-28T12:00:02", "timings_invalid"),
                              ("2026-10-28T11:59:59Z", "timings_invalid")):
            with self.subTest(value=value):
                self.result["finished_at"] = value; self.persist()
                row = self.imported()["trials"][0]
                self.assertIn(reason, row["reasons"])
                self.assertIsNone(row["durationSeconds"])

    def test_symlinked_trial_directory_and_oversized_raw_file_are_rejected(self):
        link = self.job / "linked"
        link.symlink_to(self.job / "trial-0", target_is_directory=True)
        with self.assertRaises(UserError):
            self.imported()
        link.unlink()
        (self.job / "trial-0/result.json").write_bytes(b" " * (2 * 1024 * 1024 + 1))
        with self.assertRaises(UserError):
            self.imported()

    def test_provider_neutral_terminus_adapter_has_its_real_pinned_version(self):
        self.plan = build_plan(self.manifest, model="provider/model", agent="terminus-2", agent_version="2.0.0", attempts=1)
        for agent in (self.result["config"]["agent"], self.lock["agent"]):
            agent["name"] = "terminus-2"; agent["kwargs"] = {}
        self.result["agent_info"].update(name="terminus-2", version="2.0.0")
        self.persist()
        self.assertEqual(self.imported()["trials"][0]["status"], "valid")
        self.result["config"]["agent"]["kwargs"] = {"version": "2.0.0"}; self.persist()
        self.assertIn("workload_override", self.imported()["trials"][0]["reasons"])

    def test_reported_model_match_is_literal_and_does_not_infer_provider_aliases(self):
        self.assertTrue(reported_model_matches("provider/model", {"name": "model", "provider": "provider"}))
        self.assertTrue(reported_model_matches("provider/model", {"name": "provider/model", "provider": None}))
        self.assertFalse(reported_model_matches("provider/model", {"name": "model", "provider": None}))
        self.assertFalse(reported_model_matches("provider/model", {"name": "model", "provider": "alias"}))
        self.assertFalse(reported_model_matches("provider/model", {"name": "model", "provider": "p" * 129}))
