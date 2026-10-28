"""Authored T2 comparison values only; not execution evidence for any model."""

from copy import deepcopy
import unittest
from uuid import NAMESPACE_URL, uuid5

from personal_evals.comparison import compare_runs
from personal_evals.errors import UserError
from personal_evals.jsonio import digest, sha256
from personal_evals.planning import HARBOR_COMMIT, build_plan


def manifest(*, count=3, decision=None, critical=True):
    tasks = []
    for index in range(count):
        task_id = f"task-{index}"
        files = [{"path": path, "sha256": digest({"authoredTask": task_id, "path": path}), "bytes": 10}
                 for path in sorted(("task.toml", "instruction.md", "environment/Dockerfile", "tests/test.sh"))]
        content = "".join(f"{row['path']}\0{row['sha256']}\n" for row in files)
        tasks.append({"id": task_id, "name": f"authored/{task_id}", "version": "1.0.0", "critical": critical and index == 0,
                      "rewardKey": "reward", "successThreshold": 0.6, "harborDigest": "sha256:" + sha256(content.encode()), "files": files})
    policy = {"classification": "authored", "permission": "owned", "containsPersonalData": False}
    value = {"schemaVersion": 1, "kind": "personal-evals-bundle", "suite": {"id": "authored-suite", "version": "1.0.0"},
             "split": "holdout", "decision": {"question": "Authored comparison protocol example, not a model claim.",
              "minimumPairedTasks": 2, "minimumImprovement": 0.1, "maxCriticalRegressions": 0} | (decision or {}),
             "dataPolicy": policy, "dataPolicyFingerprint": digest(policy),
             "harbor": {"sourceCommit": HARBOR_COMMIT, "taskSchema": "1.4", "profile": "single-step-docker-v1"}, "tasks": tasks,
             "sampleManifestId": digest(tasks)}
    value["bundleId"] = digest(value)
    return value


def seal(run):
    run["runId"] = digest({key: value for key, value in run.items() if key != "runId"})
    return run


def run_record(bundle, model, *, rewards=None, attempts=2, tag=None, agent_version="1.0.0"):
    tag = tag or model
    plan = build_plan(bundle, model=model, agent="codex", agent_version=agent_version, attempts=attempts)
    provider, name = model.split("/", 1)
    trials = []
    for task in bundle["tasks"]:
        selected = rewards.get(task["id"], [0.2] * attempts) if rewards is not None else [0.2] * attempts
        for index, reward in enumerate(selected):
            identity = str(uuid5(NAMESPACE_URL, f"authored:{tag}:{task['id']}:{index}"))
            trials.append({"trialId": identity, "taskId": task["id"], "status": "valid", "reasons": [], "reward": reward,
                           "errors": [], "reportedModel": {"name": name, "provider": provider}, "durationSeconds": 1.5,
                           "usage": {"inputTokens": 100, "cacheTokens": 25, "outputTokens": 10, "costUsd": 0.2},
                           "sourceHashes": {"result": digest({"authoredResult": identity}), "lock": digest({"authoredLock": identity})}})
    return seal({"schemaVersion": 1, "kind": "personal-evals-import",
                 **{key: plan[key] for key in ("bundleId", "sampleManifestId", "dataPolicyFingerprint", "planId", "protocolId",
                                               "model", "attempts", "harborSourceCommit", "agent")},
                 "jobId": str(uuid5(NAMESPACE_URL, f"authored-job:{tag}")), "trials": trials})


def pair(bundle=None, *, before=0.2, after=0.8):
    bundle = bundle or manifest()
    baseline = run_record(bundle, "authored/baseline", rewards={task["id"]: [before, before] for task in bundle["tasks"]})
    candidate = run_record(bundle, "authored/candidate", rewards={task["id"]: [after, after] for task in bundle["tasks"]})
    return bundle, baseline, candidate


class PairedComparisonTests(unittest.TestCase):
    def test_complete_positive_evidence_is_deterministic_and_seals_the_report(self):
        bundle, baseline, candidate = pair()
        originals = deepcopy((bundle, baseline, candidate))
        first = compare_runs(bundle, baseline, candidate)
        self.assertEqual(first, compare_runs(bundle, baseline, candidate))
        self.assertEqual(first["decision"]["status"], "candidate_supported")
        self.assertTrue(first["coverage"]["complete"])
        self.assertEqual(first["pairedN"], 3)
        self.assertEqual(first["decisionPolicy"], bundle["decision"])
        self.assertEqual(first["agent"], baseline["agent"])
        self.assertEqual(first["harborSourceCommit"], HARBOR_COMMIT)
        self.assertAlmostEqual(first["meanEffect"], 0.6)
        self.assertEqual(first["interval"]["resamples"], 2000)
        self.assertEqual(first["interval"]["confidence"], 0.95)
        self.assertGreater(first["interval"]["lower"], 0)
        self.assertEqual(first["reportId"], digest({key: value for key, value in first.items() if key != "reportId"}))
        first["suite"]["id"] = "detached-output"
        first["coverage"]["baseline"]["tasks"][0]["validTrials"] = 999
        self.assertEqual((bundle, baseline, candidate), originals)

    def test_pairing_uses_task_ids_and_preserves_manifest_order_after_result_reordering(self):
        bundle = manifest(critical=False)
        baseline = run_record(bundle, "authored/baseline", rewards={"task-0": [0.1, 0.3], "task-1": [0.5, 0.7], "task-2": [0.8, 1.0]})
        candidate = run_record(bundle, "authored/candidate", rewards={"task-0": [0.5, 0.7], "task-1": [0.7, 0.9], "task-2": [0.7, 0.9]})
        candidate["trials"].reverse(); seal(candidate)
        baseline["trials"] = baseline["trials"][2:] + baseline["trials"][:2]; seal(baseline)
        report = compare_runs(bundle, baseline, candidate)
        self.assertEqual([row["taskId"] for row in report["pairedTasks"]], ["task-0", "task-1", "task-2"])
        for row, before, after in zip(report["pairedTasks"], (0.2, 0.6, 0.9), (0.6, 0.8, 0.8), strict=True):
            self.assertAlmostEqual(row["baselineMean"], before)
            self.assertAlmostEqual(row["candidateMean"], after)

    def test_attempts_are_averaged_within_tasks_rather_than_counted_as_extra_pairs(self):
        bundle = manifest(critical=False)
        baseline = run_record(bundle, "authored/baseline", rewards={task["id"]: [0.0, 1.0] for task in bundle["tasks"]})
        candidate = run_record(bundle, "authored/candidate", rewards={task["id"]: [0.6, 1.0] for task in bundle["tasks"]})
        report = compare_runs(bundle, baseline, candidate)
        self.assertEqual(report["coverage"]["baseline"]["expectedTrials"], 6)
        self.assertEqual(report["coverage"]["baseline"]["validTrials"], 6)
        self.assertEqual(report["pairedN"], 3)
        self.assertAlmostEqual(report["meanEffect"], 0.3)

    def test_missing_attempts_stay_missing_and_never_become_zero_rewards(self):
        bundle, baseline, candidate = pair()
        candidate["trials"].pop(0); seal(candidate)
        report = compare_runs(bundle, baseline, candidate)
        self.assertEqual(report["decision"]["status"], "inconclusive")
        self.assertEqual(report["coverage"]["candidate"]["missingTrials"], 1)
        self.assertEqual(report["pairedN"], 2)
        self.assertIsNone(report["pairedTasks"][0]["candidateMean"])
        self.assertIsNone(report["pairedTasks"][0]["effect"])
        self.assertAlmostEqual(report["meanEffect"], 0.6)
        self.assertIsNone(report["metrics"]["candidate"]["costUsd"]["total"])

    def test_excluded_error_evidence_is_separate_from_missing_or_zero_scores(self):
        bundle, baseline, candidate = pair()
        candidate["trials"][0].update(status="excluded", reasons=["reward_missing", "trial_error"], reward=None,
                                       errors=[{"type": "RuntimeError", "stage": "trial"}])
        seal(candidate)
        report = compare_runs(bundle, baseline, candidate)
        coverage = report["coverage"]["candidate"]
        self.assertEqual(coverage["missingTrials"], 0)
        self.assertEqual(coverage["excludedTrials"], 1); self.assertEqual(coverage["errorTrials"], 1)
        self.assertEqual(coverage["validTrials"], 5)
        self.assertEqual(coverage["excludedEvidence"][0]["errors"], [{"type": "RuntimeError", "stage": "trial"}])
        self.assertIsNone(report["pairedTasks"][0]["candidateMean"])
        self.assertEqual(report["decision"]["status"], "inconclusive")

    def test_extra_valid_attempts_are_not_cherry_picked_into_a_task_mean(self):
        bundle, baseline, candidate = pair()
        extra = deepcopy(candidate["trials"][0]); extra["trialId"] = str(uuid5(NAMESPACE_URL, "authored-extra"))
        extra["sourceHashes"]["result"] = digest({"authoredExtraResult": extra["trialId"]})
        candidate["trials"].append(extra); seal(candidate)
        report = compare_runs(bundle, baseline, candidate)
        self.assertEqual(report["coverage"]["candidate"]["extraTrials"], 1)
        self.assertEqual(report["coverage"]["candidate"]["duplicateTrials"], 0)
        self.assertIsNone(report["pairedTasks"][0]["candidateMean"])
        self.assertEqual(report["pairedN"], 2)
        self.assertEqual(report["decision"]["status"], "inconclusive")

    def test_unmapped_imported_evidence_is_visible_and_blocks_a_complete_comparison(self):
        bundle, baseline, candidate = pair()
        extra = deepcopy(candidate["trials"][0]); extra.update(trialId=str(uuid5(NAMESPACE_URL, "authored-unmapped")),
            taskId=None, status="excluded", reasons=["unknown_task", "reward_missing"], reward=None)
        extra["sourceHashes"]["result"] = digest({"authoredUnmappedResult": extra["trialId"]})
        candidate["trials"].append(extra); seal(candidate)
        report = compare_runs(bundle, baseline, candidate)
        self.assertEqual(report["coverage"]["candidate"]["unmappedTrialIds"], [extra["trialId"]])
        self.assertEqual(report["coverage"]["candidate"]["extraTrials"], 1)
        self.assertEqual(report["pairedN"], 3)
        self.assertEqual(report["decision"]["status"], "inconclusive")

    def test_duplicate_trial_ids_within_or_across_runs_are_rejected(self):
        for across in (False, True):
            bundle, baseline, candidate = pair()
            candidate["trials"][1]["trialId"] = baseline["trials"][0]["trialId"] if across else candidate["trials"][0]["trialId"]
            seal(candidate)
            with self.subTest(across=across), self.assertRaises(UserError) as caught:
                compare_runs(bundle, baseline, candidate)
            self.assertEqual(caught.exception.code, "comparison_duplicate_trial")

    def test_edited_run_and_manifest_identities_are_not_trusted(self):
        bundle, baseline, candidate = pair()
        candidate["trials"][0]["reward"] = 0.7
        with self.assertRaises(UserError) as caught:
            compare_runs(bundle, baseline, candidate)
        self.assertEqual(caught.exception.code, "comparison_run_identity_mismatch")
        bundle, baseline, candidate = pair()
        bundle["decision"]["minimumImprovement"] = 0
        with self.assertRaises(UserError):
            compare_runs(bundle, baseline, candidate)

    def test_unknown_fields_boolean_numbers_and_nonfinite_values_are_rejected(self):
        changes = [lambda run: run.update(extra=True), lambda run: run["trials"][0].update(extra=True),
                   lambda run: run["trials"][0]["usage"].update(extra=1), lambda run: run.update(schemaVersion=True),
                   lambda run: run.update(attempts=True), lambda run: run["trials"][0].update(reward=True),
                   lambda run: run["trials"][0].update(reward=float("nan")),
                   lambda run: run["trials"][0].update(durationSeconds=float("inf")),
                   lambda run: run["trials"][0]["usage"].update(inputTokens=True),
                   lambda run: run["trials"][0]["usage"].update(costUsd=float("nan"))]
        for change in changes:
            bundle, baseline, candidate = pair(); change(candidate)
            with self.subTest(change=change), self.assertRaises(UserError) as caught:
                compare_runs(bundle, baseline, candidate)
            self.assertEqual(caught.exception.code, "comparison_invalid_run")

    def test_status_reward_model_and_provenance_correspondences_are_strict(self):
        changes = [lambda row: row.update(status="finished"), lambda row: row.update(reward=None), lambda row: row.update(durationSeconds=None),
                   lambda row: row.update(reasons=["reward_missing"]), lambda row: row.update(status="excluded"),
                   lambda row: row.update(taskId="unknown-task"), lambda row: row.update(taskId=None),
                   lambda row: row["reportedModel"].update(provider=None),
                   lambda row: row["sourceHashes"].update(lock=None), lambda row: row["sourceHashes"].update(result="bad"),
                   lambda row: row.update(errors=[{"type": "RuntimeError", "stage": "trial"}]),
                   lambda row: row["usage"].update(cacheTokens=101), lambda row: row["usage"].update(inputTokens=2**53)]
        for change in changes:
            bundle, baseline, candidate = pair(); change(candidate["trials"][0]); seal(candidate)
            with self.subTest(change=change), self.assertRaises(UserError):
                compare_runs(bundle, baseline, candidate)
        bundle, baseline, candidate = pair()
        for row in candidate["trials"]:
            row["reportedModel"] = {"name": candidate["model"], "provider": None}
        seal(candidate)
        self.assertEqual(compare_runs(bundle, baseline, candidate)["decision"]["status"], "candidate_supported")

    def test_frozen_protocol_attempt_agent_and_bundle_mismatches_reject_comparison(self):
        bundle, baseline, _candidate = pair()
        for candidate in (run_record(bundle, "authored/candidate", attempts=3),
                          run_record(bundle, "authored/candidate", agent_version="2.0.0")):
            with self.subTest(protocol=candidate["protocolId"]), self.assertRaises(UserError) as caught:
                compare_runs(bundle, baseline, candidate)
            self.assertEqual(caught.exception.code, "comparison_incompatible_runs")
        for key in ("bundleId", "sampleManifestId", "dataPolicyFingerprint", "protocolId", "planId", "harborSourceCommit"):
            _bundle, _baseline, candidate = pair()
            candidate[key] = "0" * (40 if key == "harborSourceCommit" else 64); seal(candidate)
            with self.subTest(key=key), self.assertRaises(UserError):
                compare_runs(bundle, baseline, candidate)

    def test_same_requested_model_or_reused_job_identity_is_not_a_model_switch(self):
        bundle, baseline, candidate = pair()
        same = run_record(bundle, "authored/baseline", tag="separate-authored-job")
        with self.assertRaises(UserError) as caught:
            compare_runs(bundle, baseline, same)
        self.assertEqual(caught.exception.code, "comparison_same_model")
        candidate["jobId"] = baseline["jobId"]; seal(candidate)
        with self.assertRaises(UserError) as caught:
            compare_runs(bundle, baseline, candidate)
        self.assertEqual(caught.exception.code, "comparison_same_job")

    def test_positive_effect_below_the_declared_practical_improvement_is_inconclusive(self):
        bundle, baseline, candidate = pair(manifest(decision={"minimumImprovement": 0.9}))
        report = compare_runs(bundle, baseline, candidate)
        self.assertGreater(report["interval"]["lower"], 0)
        self.assertEqual(report["decision"]["status"], "inconclusive")
        self.assertIn("practical_improvement_not_met", report["decision"]["reasons"])

    def test_uncertainty_crossing_zero_does_not_support_a_switch(self):
        bundle = manifest(critical=False, decision={"minimumImprovement": 0})
        baseline = run_record(bundle, "authored/baseline", rewards={task["id"]: [0.5, 0.5] for task in bundle["tasks"]})
        candidate = run_record(bundle, "authored/candidate", rewards={"task-0": [0.1, 0.1], "task-1": [0.9, 0.9], "task-2": [0.5, 0.5]})
        report = compare_runs(bundle, baseline, candidate)
        self.assertLessEqual(report["interval"]["lower"], 0); self.assertGreaterEqual(report["interval"]["upper"], 0)
        self.assertEqual(report["decision"]["status"], "inconclusive")

    def test_complete_sufficiently_sized_negative_interval_reports_regression(self):
        bundle, baseline, candidate = pair(manifest(critical=False), before=0.8, after=0.2)
        report = compare_runs(bundle, baseline, candidate)
        self.assertLess(report["interval"]["upper"], 0)
        self.assertEqual(report["decision"]["status"], "regression")
        self.assertIn("negative_effect_interval", report["decision"]["reasons"])

    def test_critical_threshold_regression_vetoes_a_positive_average(self):
        bundle = manifest()
        baseline = run_record(bundle, "authored/baseline", rewards={"task-0": [0.8, 0.8], "task-1": [0.1, 0.1], "task-2": [0.1, 0.1]})
        candidate = run_record(bundle, "authored/candidate", rewards={"task-0": [0.4, 0.4], "task-1": [1.0, 1.0], "task-2": [1.0, 1.0]})
        report = compare_runs(bundle, baseline, candidate)
        self.assertGreater(report["meanEffect"], 0)
        self.assertEqual(report["criticalRegressions"], ["task-0"])
        self.assertEqual(report["decision"]["status"], "regression")

    def test_critical_threshold_equality_and_explicit_regression_allowance_are_preserved(self):
        bundle, baseline, candidate = pair(before=0.6, after=0.6)
        self.assertEqual(compare_runs(bundle, baseline, candidate)["criticalRegressions"], [])
        bundle = manifest(decision={"maxCriticalRegressions": 1})
        baseline = run_record(bundle, "authored/baseline", rewards={"task-0": [0.8, 0.8], "task-1": [0.1, 0.1], "task-2": [0.1, 0.1]})
        candidate = run_record(bundle, "authored/candidate", rewards={"task-0": [0.4, 0.4], "task-1": [1.0, 1.0], "task-2": [1.0, 1.0]})
        report = compare_runs(bundle, baseline, candidate)
        self.assertEqual(report["criticalRegressions"], ["task-0"])
        self.assertEqual(report["decision"]["status"], "inconclusive")
        self.assertNotIn("critical_regression_limit_exceeded", report["decision"]["reasons"])

    def test_a_single_pair_or_no_pairs_has_no_interval_and_cannot_recommend(self):
        bundle, baseline, candidate = pair(manifest(count=1))
        report = compare_runs(bundle, baseline, candidate)
        self.assertTrue(report["coverage"]["complete"])
        self.assertEqual(report["pairedN"], 1); self.assertIsNone(report["interval"])
        self.assertEqual(report["decision"]["status"], "inconclusive")
        baseline["trials"] = []; candidate["trials"] = []; seal(baseline); seal(candidate)
        empty = compare_runs(bundle, baseline, candidate)
        self.assertIsNone(empty["meanEffect"]); self.assertIsNone(empty["interval"])
        self.assertEqual(empty["pairedN"], 0); self.assertEqual(empty["decision"]["status"], "inconclusive")

    def test_usage_totals_preserve_unknowns_and_never_add_cached_input_twice(self):
        bundle, baseline, candidate = pair()
        report = compare_runs(bundle, baseline, candidate)
        metrics = report["metrics"]["baseline"]
        self.assertEqual(metrics["inputTokens"]["total"], 600)
        self.assertEqual(metrics["cacheTokens"]["total"], 150)
        self.assertEqual(metrics["outputTokens"]["total"], 60)
        self.assertAlmostEqual(metrics["costUsd"]["total"], 1.2)
        self.assertEqual(metrics["summedTrialDurationSeconds"]["total"], 9)
        candidate["trials"][0]["usage"].update(costUsd=None, inputTokens=None)
        candidate["trials"][0].update(durationSeconds=None, status="excluded", reasons=["result_incomplete"])
        seal(candidate)
        unknown = compare_runs(bundle, baseline, candidate)["metrics"]["candidate"]
        for key in ("costUsd", "inputTokens", "summedTrialDurationSeconds"):
            self.assertIsNone(unknown[key]["total"])
            self.assertFalse(unknown[key]["complete"])
            self.assertEqual(unknown[key]["knownTrials"], 5)
        self.assertEqual(unknown["cacheTokens"]["total"], 150)
