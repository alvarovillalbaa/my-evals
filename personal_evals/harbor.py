"""Read a restricted, pinned Harbor job without executing tasks or following logs."""

from datetime import datetime
import math
import os
from pathlib import Path
import re
import stat
from uuid import UUID

from .errors import UserError
from .jsonio import MAX_JSON_BYTES, digest, parse_json, sha256
from .planning import validate_plan
from .suite import verify_bundle

HARBOR_SOURCE_COMMIT = "3095f96e5cc813783dc50c9c7970bc225fb7627b"
MAX_TRIALS = 2000
EXCLUSION_REASONS = frozenset({
    "unknown_task", "lock_missing", "lock_invalid", "task_provenance_mismatch",
    "job_mismatch", "model_mismatch", "agent_mismatch", "workload_override",
    "result_incomplete", "reward_missing", "reward_invalid", "trial_error",
    "timings_invalid", "usage_invalid", "result_invalid",
})
_ERROR_TYPE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]{0,127}$")
_MAX_SAFE_INT = 2**53 - 1

# Missing optional fields mean only these pinned Pydantic defaults, never a
# guessed workload. Unknown fields or any nondefault value exclude a trial.
_AGENT_DEFAULTS = {
    "import_path": None, "base_url": None, "model_api_key_name": None,
    "model_api_format": None, "skip_model_parsing": False, "n_concurrent": None,
    "concurrency_group": None, "skills": [], "override_timeout_sec": None,
    "override_setup_timeout_sec": None, "max_timeout_sec": None,
    "resume_trajectory": False, "load_trajectory": None, "extra_allowed_hosts": [],
    "include_logs": [], "exclude_logs": [], "kwargs": {}, "env": {}, "mcp_servers": [],
}
_ENV_DEFAULTS = {
    "import_path": None, "force_build": False, "delete": True, "stream": False,
    "cpu_enforcement_policy": "auto", "memory_enforcement_policy": "auto",
    "override_cpus": None, "override_memory_mb": None, "override_storage_mb": None,
    "override_gpus": None, "override_tpu": None, "mounts": None,
    "extra_docker_compose": [], "env": {}, "kwargs": {}, "extra_allowed_hosts": [],
}
_VERIFIER_DEFAULTS = {
    "override_timeout_sec": None, "max_timeout_sec": None, "include_logs": [],
    "exclude_logs": [], "env": {}, "import_path": None, "kwargs": {},
    "disable": False, "extra_allowed_hosts": [],
}
_TRIAL_DEFAULTS = {
    "install_only": False, "timeout_multiplier": 1.0,
    "agent_timeout_multiplier": None, "verifier_timeout_multiplier": None,
    "agent_setup_timeout_multiplier": None, "environment_build_timeout_multiplier": None,
    "user_agent": None, "artifacts": [], "extra_instruction_paths": [],
    "extra_instructions": [], "source_trial": None,
}
_LOCK_DEFAULTS = {
    key: value for key, value in _TRIAL_DEFAULTS.items()
    if key not in {"artifacts", "extra_instruction_paths", "extra_instructions"}
}
_LOCK_DEFAULTS.update({
    "extra_instructions": None, "user_persona": None, "user_prompt_template": None,
    "bridge_prompt": None, "bridge_inputs": {}, "skills": [], "extra_docker_compose": None,
})


def _text(value, maximum=256):
    return (isinstance(value, str) and 0 < len(value) <= maximum
            and value.strip() != "" and not any(ord(char) < 32 or ord(char) == 127 for char in value))


def _uuid(value):
    if not isinstance(value, str):
        raise UserError("harbor_invalid_identity")
    try:
        return str(UUID(value))
    except (ValueError, AttributeError) as error:
        raise UserError("harbor_invalid_identity") from error


def _number(value):
    return (type(value) in (int, float) and 0 <= value <= _MAX_SAFE_INT
            and (type(value) is int or math.isfinite(value)))


def _same(value, expected):
    # Booleans are not interchangeable with Python's integer defaults.
    if type(expected) is bool:
        return type(value) is bool and value == expected
    if type(expected) in (int, float):
        return type(value) in (int, float) and value == expected
    return type(value) is type(expected) and value == expected


def _defaults(value, defaults, required):
    if not isinstance(value, dict) or set(value) - set(defaults) - set(required):
        return False
    if any(key not in value or not _same(value[key], expected) for key, expected in required.items()):
        return False
    return all(key not in value or _same(value[key], expected) for key, expected in defaults.items())


def reported_model_matches(requested: str, reported: dict) -> bool:
    """Compare recorded identity without aliases, guessing a provider or coercion."""
    if not isinstance(requested, str) or not isinstance(reported, dict):
        return False
    if set(reported) != {"name", "provider"} or not _text(reported["name"]):
        return False
    if reported["provider"] is not None and not _text(reported["provider"], 128):
        return False
    if reported == {"name": requested, "provider": None}:
        return True
    if "/" in requested:
        provider, name = requested.split("/", 1)
        return reported == {"name": name, "provider": provider}
    return reported["name"] == requested


def _open_directory(path: Path):
    """Hold directory descriptors; later child replacement cannot redirect reads."""
    absolute = Path(os.path.abspath(path))
    descriptor = None
    try:
        descriptor = os.open(absolute.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        for part in absolute.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except OSError as error:
        if descriptor is not None:
            os.close(descriptor)
        raise UserError("harbor_job_unreadable") from error


def _read_at(directory, name):
    descriptor = None
    try:
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_JSON_BYTES:
            raise UserError("harbor_input_invalid")
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = None
            data = stream.read(MAX_JSON_BYTES + 1)
        if len(data) > MAX_JSON_BYTES:
            raise UserError("harbor_input_invalid")
        return data
    except OSError as error:
        raise UserError("harbor_input_unreadable") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _profile(config, plan, *, lock=False):
    defaults = _LOCK_DEFAULTS if lock else _TRIAL_DEFAULTS
    required = {"schema_version": 2} if lock else {}
    containers = {"task", "agent", "environment", "verifier"}
    identity = set() if lock else {"trial_name", "trials_dir", "job_id"}
    if not isinstance(config, dict) or set(config) - set(defaults) - containers - identity - set(required):
        return False
    simple = {key: value for key, value in config.items() if key not in containers | identity}
    if not _defaults(simple, defaults, required):
        return False
    agent_defaults = {key: value for key, value in _AGENT_DEFAULTS.items() if key != "kwargs"}
    if plan["agent"]["name"] == "codex":
        kwargs = {"version": plan["agent"]["version"]}
    elif plan["agent"] == {"name": "terminus-2", "version": "2.0.0"}:
        kwargs = {}
    else:
        return False
    if not _defaults(config.get("agent"), agent_defaults,
                     {"name": plan["agent"]["name"], "model_name": plan["model"],
                      "kwargs": kwargs}):
        return False
    if not _defaults(config.get("environment"), _ENV_DEFAULTS, {"type": "docker"}):
        return False
    verifier = dict(config.get("verifier", {})) if isinstance(config.get("verifier"), dict) else None
    if verifier is None:
        return False
    if lock and verifier.pop("environment_mode", None) != "shared":
        return False
    return _defaults(verifier, _VERIFIER_DEFAULTS, {})


def _task_source(config):
    task = config.get("task")
    return (isinstance(task, dict) and set(task) <= {
        "path", "git_url", "git_commit_id", "name", "ref", "overwrite", "download_dir", "source"
    } and _text(task.get("path"), 4096)
        and task.get("source") == "tasks"
        and all(task.get(key) is None for key in ("git_url", "git_commit_id", "name", "ref", "download_dir"))
        and _same(task.get("overwrite", False), False))


def _task_lock(lock, task):
    record = lock.get("task")
    return (isinstance(record, dict) and set(record) <= {
        "name", "version", "type", "digest", "source", "path", "git_url", "git_commit_id"
    } and record.get("type") == "local" and record.get("name") == task["id"]
        and record.get("version") == task["version"] and record.get("digest") == task["harborDigest"]
        and record.get("source") == "tasks"
        and all(record.get(key) is None for key in ("git_url", "git_commit_id"))
        and (record.get("path") is None or _text(record["path"], 4096)))


def _error_records(result, reasons):
    errors = []
    sources = [(result.get("exception_info"), "trial")]
    steps = result.get("step_results")
    if steps is not None:
        if not isinstance(steps, list) or len(steps) > 64:
            reasons.add("result_invalid")
        else:
            if steps:
                reasons.add("workload_override")
            sources.extend((step.get("exception_info") if isinstance(step, dict) else {}, "step") for step in steps)
    for record, stage in sources:
        if record is None:
            continue
        raw = record.get("exception_type") if isinstance(record, dict) else None
        if not isinstance(raw, str) or not _ERROR_TYPE.fullmatch(raw):
            raw = "unknown"
            reasons.add("result_invalid")
        errors.append({"type": raw, "stage": stage})
    if len(errors) > 64:
        raise UserError("harbor_too_many_errors")
    if errors:
        reasons.add("trial_error")
    return errors


def _usage(result, reasons):
    contexts = []
    if result.get("agent_result") is not None:
        contexts = [result["agent_result"]]
    elif isinstance(result.get("step_results"), list):
        contexts = [step["agent_result"] for step in result["step_results"]
                    if isinstance(step, dict) and step.get("agent_result") is not None]
    output = {}
    for source, target in (("n_input_tokens", "inputTokens"), ("n_cache_tokens", "cacheTokens"),
                           ("n_output_tokens", "outputTokens"), ("cost_usd", "costUsd")):
        values = []
        invalid = False
        for context in contexts:
            if not isinstance(context, dict):
                invalid = True
                continue
            value = context.get(source)
            if value is None:
                continue
            if not _number(value) or (source != "cost_usd" and type(value) is not int):
                invalid = True
            else:
                values.append(value)
        # A known subtotal is not a complete observation for a multi-context run.
        total = sum(values) if values and len(values) == len(contexts) else None
        if invalid or (total is not None and not _number(total)):
            reasons.add("usage_invalid")
            total = None
        output[target] = total
    if output["inputTokens"] is not None and output["cacheTokens"] is not None and output["cacheTokens"] > output["inputTokens"]:
        reasons.add("usage_invalid")
        output["inputTokens"] = output["cacheTokens"] = None
    return output


def _duration(result, reasons):
    values = [result.get("started_at"), result.get("finished_at")]
    if any(value is None for value in values):
        reasons.add("result_incomplete")
        return None
    try:
        if not all(_text(value, 64) for value in values):
            raise ValueError
        start, finish = (datetime.fromisoformat(value.replace("Z", "+00:00")) for value in values)
        if start.utcoffset() is None or finish.utcoffset() is None:
            raise ValueError
        duration = (finish - start).total_seconds()
        if not _number(duration):
            raise ValueError
        return duration
    except (ValueError, OverflowError):
        reasons.add("timings_invalid")
        return None


def _trial(result, lock, result_hash, lock_hash, manifest, plan, job_id, root_locks):
    if not isinstance(result, dict):
        raise UserError("harbor_result_invalid")
    trial_id = _uuid(result.get("id"))
    reasons = set()
    tasks = {task["name"]: task for task in manifest["tasks"]}
    task = tasks.get(result.get("task_name")) if isinstance(result.get("task_name"), str) else None
    if task is None:
        reasons.add("unknown_task")
    config = result.get("config")
    if not isinstance(config, dict):
        reasons.add("result_invalid")
        config = {}
    if config.get("job_id") != job_id:
        reasons.add("job_mismatch")
    if not _profile(config, plan) or not _task_source(config):
        reasons.add("workload_override")
    if not _text(result.get("trial_name")) or config.get("trial_name") != result.get("trial_name"):
        reasons.add("result_invalid")
    agent = result.get("agent_info")
    if not isinstance(agent, dict):
        agent = {}
    if agent.get("name") != plan["agent"]["name"] or agent.get("version") != plan["agent"]["version"]:
        reasons.add("agent_mismatch")
    reported = agent.get("model_info")
    if not isinstance(reported, dict) or not _text(reported.get("name")) or (reported.get("provider") is not None and not _text(reported["provider"], 128)):
        reported = {"name": "unknown", "provider": None}
        reasons.add("model_mismatch")
    else:
        reported = {"name": reported["name"], "provider": reported.get("provider")}
    config_agent = config.get("agent") if isinstance(config.get("agent"), dict) else {}
    if not reported_model_matches(plan["model"], reported) or config_agent.get("model_name") != plan["model"]:
        reasons.add("model_mismatch")
    if lock is None:
        reasons.add("lock_missing" if lock_hash is None else "lock_invalid")
    elif not isinstance(lock, dict) or type(lock.get("schema_version")) is not int or lock["schema_version"] != 2:
        reasons.add("lock_invalid")
    else:
        if not _profile(lock, plan, lock=True):
            reasons.add("workload_override")
        if digest(lock) not in root_locks:
            reasons.add("lock_invalid")
        if task is not None and not _task_lock(lock, task):
            reasons.add("task_provenance_mismatch")
    verifier = result.get("verifier_result")
    rewards = verifier.get("rewards") if isinstance(verifier, dict) else None
    value = rewards.get(task["rewardKey"]) if task is not None and isinstance(rewards, dict) else None
    if value is None:
        reasons.add("reward_missing")
        reward = None
    elif not _number(value) or value > 1:
        reasons.add("reward_invalid")
        reward = None
    else:
        reward = float(value)
    errors = _error_records(result, reasons)
    duration = _duration(result, reasons)
    usage = _usage(result, reasons)
    return {"trialId": trial_id, "taskId": task["id"] if task is not None else None,
            "status": "excluded" if reasons else "valid", "reasons": sorted(reasons),
            "reward": reward, "errors": errors, "reportedModel": reported,
            "durationSeconds": duration, "usage": usage,
            "sourceHashes": {"result": result_hash, "lock": lock_hash}}


def import_job(bundle: Path, plan: dict, job: Path) -> dict:
    """Project actual local Harbor files; file hashes attest input bytes, not execution."""
    manifest = verify_bundle(bundle)
    plan = validate_plan(plan, manifest)
    directory = _open_directory(job)
    try:
        root_result = parse_json(_read_at(directory, "result.json"))
        root_lock = parse_json(_read_at(directory, "lock.json"))
        if not isinstance(root_result, dict):
            raise UserError("harbor_job_invalid")
        job_id = _uuid(root_result.get("id"))
        if type(root_result.get("n_total_trials")) is not int or not 0 <= root_result["n_total_trials"] <= MAX_TRIALS:
            raise UserError("harbor_job_invalid")
        if (not isinstance(root_lock, dict) or type(root_lock.get("schema_version")) is not int
                or root_lock["schema_version"] != 3 or not isinstance(root_lock.get("harbor"), dict)
                or root_lock["harbor"].get("git_commit_hash") != HARBOR_SOURCE_COMMIT
                or not _text(root_lock["harbor"].get("version"))
                or type(root_lock.get("n_concurrent_trials")) is not int or root_lock["n_concurrent_trials"] != 1
                or not isinstance(root_lock.get("retry"), dict)
                or type(root_lock["retry"].get("max_retries")) is not int or root_lock["retry"]["max_retries"] != 0
                or not isinstance(root_lock.get("trials"), list) or len(root_lock["trials"]) > MAX_TRIALS):
            raise UserError("harbor_job_provenance_invalid")
        root_locks = {digest(lock) for lock in root_lock["trials"] if isinstance(lock, dict)}
        with os.scandir(directory) as entries:
            children = []
            for entry in entries:
                if entry.is_symlink():
                    raise UserError("harbor_symlink_forbidden")
                if entry.is_dir(follow_symlinks=False):
                    children.append(entry.name)
                    if len(children) > MAX_TRIALS:
                        raise UserError("harbor_too_many_trials")
        trials, identities = [], set()
        for child in sorted(children):
            trial_dir = None
            try:
                trial_dir = os.open(child, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
                result_bytes = _read_at(trial_dir, "result.json")
                result = parse_json(result_bytes)
                lock, lock_hash = None, None
                try:
                    lock_bytes = _read_at(trial_dir, "lock.json")
                    lock_hash = sha256(lock_bytes)
                    lock = parse_json(lock_bytes)
                except UserError:
                    pass
                row = _trial(result, lock, sha256(result_bytes), lock_hash, manifest, plan, job_id, root_locks)
                if row["trialId"] in identities:
                    raise UserError("harbor_duplicate_trial")
                identities.add(row["trialId"])
                trials.append(row)
            except OSError as error:
                raise UserError("harbor_input_unreadable") from error
            finally:
                if trial_dir is not None:
                    os.close(trial_dir)
    finally:
        os.close(directory)
    output = {"schemaVersion": 1, "kind": "personal-evals-import",
              **{key: plan[key] for key in ("bundleId", "sampleManifestId", "dataPolicyFingerprint", "planId", "protocolId", "model", "attempts")},
              "jobId": job_id, "harborSourceCommit": HARBOR_SOURCE_COMMIT,
              "agent": dict(plan["agent"]), "trials": trials}
    output["runId"] = digest(output)
    return output
