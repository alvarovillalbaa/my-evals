"""Paired evidence comparison; never executes Harbor or promotes a model."""

import math
import random
import re
from uuid import UUID

from .errors import UserError
from .harbor import EXCLUSION_REASONS, reported_model_matches
from .jsonio import canonical, digest
from .planning import MODEL, validate_plan
from .suite import validate_manifest

RUN_KEYS = {"schemaVersion", "kind", "bundleId", "sampleManifestId", "dataPolicyFingerprint",
            "planId", "protocolId", "model", "attempts", "jobId", "harborSourceCommit", "agent", "trials", "runId"}
TRIAL_KEYS = {"trialId", "taskId", "status", "reasons", "reward", "errors", "reportedModel",
              "durationSeconds", "usage", "sourceHashes"}
PLAN_FIELDS = ("bundleId", "sampleManifestId", "dataPolicyFingerprint", "planId", "protocolId",
               "model", "attempts", "harborSourceCommit", "agent")
HEX = re.compile(r"[a-f0-9]{64}\Z")
ERROR_TYPE = re.compile(r"[A-Za-z_][A-Za-z0-9_.]{0,127}\Z")
RESAMPLES = 2000
MAX_SAFE_INTEGER = 2**53 - 1


def _invalid():
    raise UserError("comparison_invalid_run")


def _record(value, keys):
    if type(value) is not dict or set(value) != keys:
        _invalid()


def _text(value, maximum):
    return (type(value) is str and 1 <= len(value) <= maximum and bool(value.strip())
            and all(ord(char) >= 32 and ord(char) != 127 and not 0xD800 <= ord(char) <= 0xDFFF for char in value))


def _number(value, *, optional=False, ratio=False):
    if value is None:
        if optional:
            return
        _invalid()
    if type(value) not in (int, float):
        _invalid()
    try:
        valid = math.isfinite(value) and value >= 0 and value <= (1 if ratio else MAX_SAFE_INTEGER)
    except (OverflowError, TypeError):
        valid = False
    if not valid:
        _invalid()


def _uuid(value):
    if type(value) is not str or len(value) != 36:
        _invalid()
    try:
        if str(UUID(value)) != value:
            _invalid()
    except (ValueError, AttributeError):
        _invalid()


def _hash(value):
    if type(value) is not str or not HEX.fullmatch(value):
        _invalid()


def _validate_run(run, manifest):
    _record(run, RUN_KEYS)
    if type(run["schemaVersion"]) is not int or run["schemaVersion"] != 1 or run["kind"] != "personal-evals-import":
        _invalid()
    if type(run["model"]) is not str or not MODEL.fullmatch(run["model"]):
        _invalid()
    if type(run["attempts"]) is not int or not 1 <= run["attempts"] <= 20:
        _invalid()
    _uuid(run["jobId"])
    _hash(run["runId"])
    # Reconstruct the sealed plan: matching-looking protocol hashes alone are insufficient.
    plan = {"schemaVersion": 1, "kind": "personal-evals-plan"} | {key: run[key] for key in PLAN_FIELDS}
    validate_plan(plan, manifest)
    if type(run["trials"]) is not list or len(run["trials"]) > 2000:
        _invalid()
    known = {task["id"] for task in manifest["tasks"]}
    trial_ids = set()
    for trial in run["trials"]:
        _record(trial, TRIAL_KEYS)
        _uuid(trial["trialId"])
        if trial["trialId"] in trial_ids:
            raise UserError("comparison_duplicate_trial")
        trial_ids.add(trial["trialId"])
        if trial["taskId"] is not None and (type(trial["taskId"]) is not str or trial["taskId"] not in known):
            _invalid()
        if trial["status"] not in ("valid", "excluded"):
            _invalid()
        reasons = trial["reasons"]
        if (type(reasons) is not list or len(reasons) > len(EXCLUSION_REASONS)
                or any(type(reason) is not str or reason not in EXCLUSION_REASONS for reason in reasons)
                or len(set(reasons)) != len(reasons)):
            _invalid()
        _number(trial["reward"], optional=True, ratio=True)
        errors = trial["errors"]
        if type(errors) is not list or len(errors) > 64:
            _invalid()
        for error in errors:
            _record(error, {"type", "stage"})
            if (type(error["type"]) is not str or not ERROR_TYPE.fullmatch(error["type"])
                    or error["stage"] not in ("trial", "step")):
                _invalid()
        reported = trial["reportedModel"]
        _record(reported, {"name", "provider"})
        if not _text(reported["name"], 256) or (reported["provider"] is not None and not _text(reported["provider"], 128)):
            _invalid()
        _number(trial["durationSeconds"], optional=True)
        usage = trial["usage"]
        _record(usage, {"inputTokens", "cacheTokens", "outputTokens", "costUsd"})
        for key in ("inputTokens", "cacheTokens", "outputTokens"):
            if usage[key] is not None and (type(usage[key]) is not int or not 0 <= usage[key] <= MAX_SAFE_INTEGER):
                _invalid()
        if (usage["inputTokens"] is not None and usage["cacheTokens"] is not None
                and usage["cacheTokens"] > usage["inputTokens"]):
            _invalid()
        _number(usage["costUsd"], optional=True)
        sources = trial["sourceHashes"]
        _record(sources, {"result", "lock"})
        _hash(sources["result"])
        if sources["lock"] is not None:
            _hash(sources["lock"])
        if trial["status"] == "valid":
            if (reasons or errors or trial["taskId"] is None or trial["reward"] is None or trial["durationSeconds"] is None or sources["lock"] is None
                    or not reported_model_matches(run["model"], reported)):
                _invalid()
        elif not reasons:
            _invalid()
        if trial["taskId"] is None and "unknown_task" not in reasons:
            _invalid()
        if errors and "trial_error" not in reasons:
            _invalid()
    if digest({key: value for key, value in run.items() if key != "runId"}) != run["runId"]:
        raise UserError("comparison_run_identity_mismatch")
    # Canonical serialization also rejects malformed Unicode or unsupported scalar objects.
    canonical(run)
    return trial_ids


def _coverage(run, manifest):
    by_task = {task["id"]: [] for task in manifest["tasks"]}
    unmapped = []
    for trial in run["trials"]:
        if trial["taskId"] is None:
            unmapped.append(trial["trialId"])
        else:
            by_task[trial["taskId"]].append(trial)
    attempts = run["attempts"]
    rows = []
    for task in manifest["tasks"]:
        trials = by_task[task["id"]]
        valid = [trial for trial in trials if trial["status"] == "valid"]
        rows.append({"taskId": task["id"], "expectedAttempts": attempts, "observedTrials": len(trials),
                     "validTrials": len(valid), "excludedTrials": sum(trial["status"] == "excluded" for trial in trials),
                     "errorTrials": sum(bool(trial["errors"]) for trial in trials),
                     "missingTrials": max(0, attempts - len(trials)), "extraTrials": max(0, len(trials) - attempts),
                     "meanReward": math.fsum(trial["reward"] for trial in valid) / attempts if len(valid) == attempts else None})
    expected = len(manifest["tasks"]) * attempts
    excluded = [trial for trial in run["trials"] if trial["status"] == "excluded"]
    complete = not unmapped and not excluded and all(row["observedTrials"] == attempts and row["validTrials"] == attempts for row in rows)
    return {"expectedTasks": len(rows), "expectedTrials": expected, "attemptsPerTask": attempts,
            "observedTrials": len(run["trials"]), "validTrials": sum(row["validTrials"] for row in rows),
            "excludedTrials": len(excluded), "errorTrials": sum(bool(trial["errors"]) for trial in run["trials"]),
            "missingTrials": sum(row["missingTrials"] for row in rows),
            "extraTrials": len(unmapped) + sum(row["extraTrials"] for row in rows),
            "unmappedTrialIds": unmapped, "duplicateTrials": 0, "complete": complete, "tasks": rows,
            "excludedEvidence": [{"trialId": trial["trialId"], "taskId": trial["taskId"],
                                  "reasons": list(trial["reasons"]), "errors": [dict(error) for error in trial["errors"]]} for trial in excluded]}


def _percentile(ordered, fraction):
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _interval(deltas, seed):
    if len(deltas) < 2:
        return None
    generator = random.Random(int(seed, 16))
    count = len(deltas)
    samples = sorted(math.fsum(deltas[generator.randrange(count)] for _ in range(count)) / count for _ in range(RESAMPLES))
    return {"lower": _percentile(samples, 0.025), "upper": _percentile(samples, 0.975),
            "confidence": 0.95, "resamples": RESAMPLES, "seed": seed, "method": "paired-task-percentile-bootstrap"}


def _metrics(run, coverage):
    trials = run["trials"]
    # Missing/extra evidence prevents claiming a complete workload total, even if observed values exist.
    workload_complete = not coverage["missingTrials"] and not coverage["extraTrials"]

    def total(values, *, integer=False):
        known = sum(value is not None for value in values)
        complete = workload_complete and bool(values) and known == len(values)
        value = None
        if complete:
            try:
                value = sum(values) if integer else math.fsum(values)
                if not integer and not math.isfinite(value):
                    raise OverflowError
            except (OverflowError, ValueError):
                raise UserError("comparison_numeric_overflow") from None
        return {"total": value, "knownTrials": known, "complete": complete}

    return {"summedTrialDurationSeconds": total([trial["durationSeconds"] for trial in trials]),
            "costUsd": total([trial["usage"]["costUsd"] for trial in trials]),
            "inputTokens": total([trial["usage"]["inputTokens"] for trial in trials], integer=True),
            "cacheTokens": total([trial["usage"]["cacheTokens"] for trial in trials], integer=True),
            "outputTokens": total([trial["usage"]["outputTokens"] for trial in trials], integer=True)}


def compare_runs(manifest: dict, baseline: dict, candidate: dict) -> dict:
    """Return a reproducible report over matched tasks, with explicit evidence gates."""
    manifest = validate_manifest(manifest)
    baseline_ids = _validate_run(baseline, manifest)
    candidate_ids = _validate_run(candidate, manifest)
    if baseline_ids & candidate_ids:
        raise UserError("comparison_duplicate_trial")
    if baseline["jobId"] == candidate["jobId"]:
        raise UserError("comparison_same_job")
    if baseline["model"] == candidate["model"]:
        raise UserError("comparison_same_model")
    for key in ("bundleId", "sampleManifestId", "dataPolicyFingerprint", "protocolId", "attempts", "agent", "harborSourceCommit"):
        if baseline[key] != candidate[key]:
            raise UserError("comparison_incompatible_runs")
    base_coverage, next_coverage = _coverage(baseline, manifest), _coverage(candidate, manifest)
    paired = []
    regressions = []
    deltas = []
    for task, base, next_row in zip(manifest["tasks"], base_coverage["tasks"], next_coverage["tasks"], strict=True):
        before, after = base["meanReward"], next_row["meanReward"]
        effect = after - before if before is not None and after is not None else None
        regression = bool(task["critical"] and effect is not None and before >= task["successThreshold"] > after)
        row = {"taskId": task["id"], "taskName": task["name"], "taskVersion": task["version"], "critical": task["critical"],
               "successThreshold": task["successThreshold"], "baselineMean": before, "candidateMean": after,
               "effect": effect, "criticalRegression": regression}
        paired.append(row)
        if effect is not None:
            deltas.append(effect)
        if regression:
            regressions.append(task["id"])
    seed = digest({"bundleId": manifest["bundleId"], "baselineRunId": baseline["runId"], "candidateRunId": candidate["runId"]})
    interval = _interval(deltas, seed)
    mean = math.fsum(deltas) / len(deltas) if deltas else None
    full = base_coverage["complete"] and next_coverage["complete"]
    policy = manifest["decision"]
    enough = len(deltas) >= policy["minimumPairedTasks"]
    critical_exceeded = len(regressions) > policy["maxCriticalRegressions"]
    reasons = []
    status = "inconclusive"
    if not full:
        reasons.append("incomplete_or_excluded_evidence")
    if not enough:
        reasons.append("insufficient_paired_tasks")
    if full and enough:
        if critical_exceeded or interval["upper"] < 0:
            status = "regression"
            reasons.append("critical_regression_limit_exceeded" if critical_exceeded else "negative_effect_interval")
        elif mean >= policy["minimumImprovement"] and interval["lower"] > 0:
            status = "candidate_supported"
            reasons.append("practical_improvement_with_positive_interval")
        else:
            if mean < policy["minimumImprovement"]:
                reasons.append("practical_improvement_not_met")
            if interval["lower"] <= 0:
                reasons.append("uncertainty_includes_no_improvement")
    report = {"schemaVersion": 1, "kind": "personal-evals-comparison", "bundleId": manifest["bundleId"],
              "sampleManifestId": manifest["sampleManifestId"], "dataPolicyFingerprint": manifest["dataPolicyFingerprint"],
              "suite": dict(manifest["suite"]), "split": manifest["split"], "question": policy["question"],
              "decisionPolicy": dict(policy), "agent": dict(baseline["agent"]), "harborSourceCommit": baseline["harborSourceCommit"],
              "runs": {label: {key: run[key] for key in ("runId", "planId", "jobId", "model")} for label, run in (("baseline", baseline), ("candidate", candidate))},
              "protocolId": baseline["protocolId"], "attemptsPerTask": baseline["attempts"],
              "coverage": {"complete": full, "baseline": base_coverage, "candidate": next_coverage},
              "pairedTasks": paired, "pairedN": len(deltas), "meanEffect": mean, "interval": interval,
              "criticalRegressions": regressions, "decision": {"status": status, "reasons": reasons},
              "metrics": {"baseline": _metrics(baseline, base_coverage), "candidate": _metrics(candidate, next_coverage)},
              "limitations": ["No automatic model promotion or provider change.",
                              "Effects describe only the paired tasks in this sealed split, not an unobserved task population.",
                              "The bootstrap resamples tasks; attempts are averaged within each task, not treated as independent tasks.",
                              "A small or unrepresentative task sample limits the interval; it does not prove population-wide improvement.",
                              "Imported hashes identify supplied evidence; this comparison does not execute Harbor or authenticate model execution.",
                              "Input token totals already include cached input tokens; cache tokens are never added again.",
                              "Duration is a sum of trial durations, not job wall-clock latency."]}
    report["reportId"] = digest(report)
    return report
