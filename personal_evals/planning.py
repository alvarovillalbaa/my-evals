"""Explicit real-Harbor run plans; this module never executes a process."""

from pathlib import Path
import json
import re

from .errors import UserError
from .jsonio import canonical, digest, parse_json
from .suite import validate_manifest

HARBOR_COMMIT = "3095f96e5cc813783dc50c9c7970bc225fb7627b"
PROFILE = "single-step-docker-v1"
MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}/[A-Za-z0-9][A-Za-z0-9._:/-]{0,190}\Z")
SUPPORTED_AGENTS = {"codex", "terminus-2"}
CODEX_VERSION = re.compile(r"v?(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*)?\Z")
HEX = re.compile(r"[a-f0-9]{64}\Z")
PLAN_KEYS = {"schemaVersion", "kind", "bundleId", "sampleManifestId", "dataPolicyFingerprint", "model",
             "attempts", "agent", "harborSourceCommit", "protocolId", "planId"}


def _protocol(plan):
    return {key: plan[key] for key in ("bundleId", "sampleManifestId", "dataPolicyFingerprint", "attempts", "agent", "harborSourceCommit")} | {"profile": PROFILE}


def validate_plan(value, manifest):
    manifest = validate_manifest(manifest)
    if not isinstance(value, dict) or set(value) != PLAN_KEYS:
        raise UserError("plan_invalid")
    if type(value["schemaVersion"]) is not int or value["schemaVersion"] != 1 or value["kind"] != "personal-evals-plan":
        raise UserError("plan_invalid")
    if not isinstance(value["model"], str) or not MODEL.fullmatch(value["model"]):
        raise UserError("plan_model_invalid")
    agent = value["agent"]
    if not isinstance(agent, dict) or set(agent) != {"name", "version"}:
        raise UserError("plan_agent_invalid")
    if not isinstance(agent["name"], str) or agent["name"] not in SUPPORTED_AGENTS:
        raise UserError("plan_agent_invalid")
    if not isinstance(agent["version"], str) or not 1 <= len(agent["version"]) <= 128 or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+:-]*", agent["version"]):
        raise UserError("plan_agent_invalid")
    if agent["name"] == "terminus-2" and agent["version"] != "2.0.0":
        raise UserError("plan_agent_invalid")
    if agent["name"] == "codex" and not CODEX_VERSION.fullmatch(agent["version"]):
        raise UserError("plan_agent_invalid")
    if type(value["attempts"]) is not int or not 1 <= value["attempts"] <= 20:
        raise UserError("plan_attempts_invalid")
    if value["harborSourceCommit"] != HARBOR_COMMIT or manifest["harbor"]["sourceCommit"] != HARBOR_COMMIT:
        raise UserError("plan_harbor_unsupported")
    for key in ("bundleId", "sampleManifestId", "dataPolicyFingerprint"):
        if value[key] != manifest[key]:
            raise UserError("plan_bundle_mismatch")
    for key in ("protocolId", "planId"):
        if not isinstance(value[key], str) or not HEX.fullmatch(value[key]):
            raise UserError("plan_invalid")
    if value["protocolId"] != digest(_protocol(value)) or value["planId"] != digest({key: child for key, child in value.items() if key != "planId"}):
        raise UserError("plan_identity_mismatch")
    return parse_json(canonical(value))


def build_plan(manifest, *, model: str, agent: str, agent_version: str, attempts: int):
    manifest = validate_manifest(manifest)
    value = {"schemaVersion": 1, "kind": "personal-evals-plan", "bundleId": manifest["bundleId"],
             "sampleManifestId": manifest["sampleManifestId"], "dataPolicyFingerprint": manifest["dataPolicyFingerprint"],
             "model": model, "attempts": attempts, "agent": {"name": agent, "version": agent_version}, "harborSourceCommit": HARBOR_COMMIT}
    value["protocolId"] = digest(_protocol(value))
    value["planId"] = digest(value)
    return validate_plan(value, manifest)


def render_command(plan, manifest, *, bundle: Path, jobs: Path, job_name: str):
    plan = validate_plan(plan, manifest)
    if not isinstance(job_name, str) or not re.fullmatch(r"[a-z0-9]+(?:[-_][a-z0-9]+)*", job_name) or len(job_name) > 64:
        raise UserError("job_name_invalid")
    bundle = bundle.resolve(strict=True)
    jobs = jobs.resolve()
    if jobs == bundle or bundle in jobs.parents:
        raise UserError("jobs_inside_bundle")
    command = ["harbor", "run", "--path", str(bundle / "tasks"), "--agent", plan["agent"]["name"],
            "--model", plan["model"], "--env", "docker", "--n-concurrent", "1", "--n-attempts", str(plan["attempts"]),
            "--max-retries", "0", "--jobs-dir", str(jobs), "--job-name", job_name]
    if plan["agent"]["name"] == "codex":
        command.extend(["--agent-kwarg", "version=" + json.dumps(plan["agent"]["version"])])
    return command
