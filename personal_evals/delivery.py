"""Binary-safe offline GitHub delivery plans. Nothing authenticates or publishes.

Consent, destination visibility and account ownership are declared inputs, not
remote observations. Base/ref/path preconditions remain for an approved future
publisher. Source capture has the suite reader's trusted-directory boundary.
"""

import base64
import binascii
from datetime import datetime
import hashlib
from pathlib import Path
import re
import unicodedata

from .errors import UserError
from .jsonio import MAX_JSON_BYTES, canonical, digest, parse_json, read_json, sha256, write_bytes
from .suite import (MAX_FILE_BYTES, MAX_TOTAL_BYTES, _read_file, _relative,
                    _task_header, validate_manifest, verify_bundle)

MAX_DELIVERY_BYTES = 64 * 1024 * 1024
MAX_BLOBS = 10001
MAX_ID = 2**53 - 1
_LOGIN = re.compile(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*\Z")
_REPOSITORY = re.compile(r"[A-Za-z0-9_.-]{1,100}\Z")
_SEGMENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
_SHA1 = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_TARGET_KEYS = {"repository", "repositoryId", "visibility", "baseBranch", "baseCommit", "newBranch", "pathPrefix"}
_INTENT_KEYS = {"schemaVersion", "target", "actor", "createdAt", "pullRequest", "purpose"}
_PLAN_KEYS = {"schemaVersion", "kind", "bundleId", "target", "actor", "createdAt", "pullRequest", "publication", "preconditions", "files", "planId"}
_PRECONDITIONS = {"baseUnchanged": True, "visibilityMatches": True, "newBranchAbsent": True, "pathPrefixAbsent": True}


def _fail(code="delivery_invalid"):
    raise UserError(code)


def _record(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        _fail()
    return value


def _identifier(value):
    if type(value) is not int or not 1 <= value <= MAX_ID:
        _fail("delivery_identity_invalid")
    return value


def _login(value):
    if type(value) is not str or not 1 <= len(value) <= 39 or not _LOGIN.fullmatch(value):
        _fail("delivery_identity_invalid")
    return value


def _text(value, maximum, *, blank=False, multiline=False):
    if type(value) is not str or len(value) > maximum or not blank and not value.strip():
        _fail()
    if any((ord(char) < 32 and (not multiline or char not in "\n\r\t"))
           or 0x7F <= ord(char) <= 0x9F or 0xD800 <= ord(char) <= 0xDFFF
           or not multiline and char in "\u2028\u2029" for char in value):
        _fail()
    return value


def _safe_segments(value):
    if type(value) is not str or not 1 <= len(value) <= 120 or ".." in value:
        _fail("delivery_path_invalid")
    parts = value.split("/")
    if any(not _SEGMENT.fullmatch(part) or part.endswith(".") or part.lower().endswith(".lock") for part in parts):
        _fail("delivery_path_invalid")
    return value


def _branch(value):
    value = _safe_segments(value)
    if value.startswith("refs/"):
        _fail("delivery_branch_invalid")
    return value


def validate_target(value) -> dict:
    row = _record(value, _TARGET_KEYS)
    if type(row["repository"]) is not str or len(row["repository"].split("/")) != 2:
        _fail("delivery_repository_invalid")
    owner, repository = row["repository"].split("/")
    _login(owner)
    if not _REPOSITORY.fullmatch(repository) or repository in (".", ".."):
        _fail("delivery_repository_invalid")
    if row["visibility"] not in ("private", "public"):
        _fail("delivery_repository_invalid")
    if type(row["baseCommit"]) is not str or not _SHA1.fullmatch(row["baseCommit"]):
        _fail("delivery_base_invalid")
    base, branch = _branch(row["baseBranch"]), _branch(row["newBranch"])
    if base == branch:
        _fail("delivery_branch_invalid")
    return {"repository": row["repository"], "repositoryId": _identifier(row["repositoryId"]),
            "visibility": row["visibility"], "baseBranch": base, "baseCommit": row["baseCommit"],
            "newBranch": branch, "pathPrefix": _safe_segments(row["pathPrefix"])}


def validate_actor(value) -> dict:
    row = _record(value, {"login", "id"})
    return {"login": _login(row["login"]), "id": _identifier(row["id"])}


def validate_timestamp(value) -> str:
    if type(value) is not str or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", value):
        _fail("delivery_timestamp_invalid")
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as error:
        raise UserError("delivery_timestamp_invalid") from error
    return value


def _pull_request(value):
    row = _record(value, {"title", "body", "draft"})
    if type(row["draft"]) is not bool:
        _fail()
    return {"title": _text(row["title"], 120), "body": _text(row["body"], 8000, blank=True, multiline=True), "draft": row["draft"]}


def validate_delivery_intent(value) -> dict:
    row = _record(value, _INTENT_KEYS)
    if type(row["schemaVersion"]) is not int or row["schemaVersion"] != 1:
        _fail()
    return {"schemaVersion": 1, "target": validate_target(row["target"]), "actor": validate_actor(row["actor"]),
            "createdAt": validate_timestamp(row["createdAt"]), "pullRequest": _pull_request(row["pullRequest"]),
            "purpose": _text(row["purpose"], 1000, multiline=True)}


def _git_blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def _file(path, data):
    return {"path": path, "mode": "100644", "encoding": "base64", "content": base64.b64encode(data).decode("ascii"),
            "bytes": len(data), "sha256": sha256(data), "gitBlob": _git_blob(data)}


def _collisions(paths):
    nodes = {}
    for path in paths:
        parts = path.split("/")
        for length in range(1, len(parts) + 1):
            node = "/".join(parts[:length])
            key = unicodedata.normalize("NFC", node).casefold()
            kind = "file" if length == len(parts) else "directory"
            if key in nodes and nodes[key] != (node, kind):
                _fail("delivery_path_collision")
            nodes[key] = (node, kind)


def _decode_files(value, prefix):
    if type(value) is not list or not 1 <= len(value) <= MAX_BLOBS:
        _fail("delivery_inventory_invalid")
    files, payload, total = [], {}, 0
    for item in value:
        row = _record(item, {"path", "mode", "encoding", "content", "bytes", "sha256", "gitBlob"})
        path = row["path"]
        _relative(path, 512)
        if not path.startswith(prefix + "/"):
            _fail("delivery_inventory_invalid")
        relative = path[len(prefix) + 1:]
        if relative in payload:
            _fail("delivery_inventory_invalid")
        maximum = MAX_JSON_BYTES if relative == "bundle.json" else MAX_FILE_BYTES
        if row["mode"] != "100644" or row["encoding"] != "base64" or type(row["content"]) is not str:
            _fail()
        if type(row["bytes"]) is not int or not 0 <= row["bytes"] <= maximum or len(row["content"]) > 4 * ((maximum + 2) // 3):
            _fail("delivery_blob_invalid")
        try:
            data = base64.b64decode(row["content"].encode("ascii"), validate=True)
        except (UnicodeError, ValueError, binascii.Error) as error:
            raise UserError("delivery_blob_invalid") from error
        total += len(data)
        if total > MAX_TOTAL_BYTES + MAX_JSON_BYTES:
            _fail("delivery_too_large")
        if (len(data) != row["bytes"] or len(data) > maximum or base64.b64encode(data).decode("ascii") != row["content"]
                or type(row["sha256"]) is not str or not _SHA256.fullmatch(row["sha256"]) or sha256(data) != row["sha256"]
                or type(row["gitBlob"]) is not str or not _SHA1.fullmatch(row["gitBlob"]) or _git_blob(data) != row["gitBlob"]):
            _fail("delivery_blob_invalid")
        files.append(_file(path, data))
        payload[relative] = data
    paths = [file["path"] for file in files]
    if paths != sorted(paths):
        _fail("delivery_inventory_invalid")
    _collisions(paths)
    return files, payload


def _embedded_manifest(payload, bundle_id):
    if "bundle.json" not in payload:
        _fail("delivery_inventory_invalid")
    manifest = validate_manifest(parse_json(payload["bundle.json"], MAX_JSON_BYTES))
    if canonical(manifest) + b"\n" != payload["bundle.json"] or manifest["bundleId"] != bundle_id:
        _fail("delivery_bundle_mismatch")
    expected = {"bundle.json"}
    for task in manifest["tasks"]:
        for file in task["files"]:
            path = f"tasks/{task['id']}/{file['path']}"
            expected.add(path)
            if path not in payload or len(payload[path]) != file["bytes"] or sha256(payload[path]) != file["sha256"]:
                _fail("delivery_bundle_mismatch")
            if file["path"] == "task.toml" and _task_header(payload[path]) != (task["name"], task["version"]):
                _fail("delivery_bundle_mismatch")
    if set(payload) != expected:
        _fail("delivery_inventory_invalid")
    return manifest


def _privacy(manifest, target):
    policy = manifest["dataPolicy"]
    if target["visibility"] == "public" and (policy["classification"] == "private" or policy["containsPersonalData"]):
        _fail("delivery_publication_disallowed")


def _validate_plan(value):
    row = _record(value, _PLAN_KEYS)
    if type(row["schemaVersion"]) is not int or row["schemaVersion"] != 1 or row["kind"] != "personal-evals-delivery-plan":
        _fail()
    if len(canonical(row)) + 1 > MAX_DELIVERY_BYTES:
        _fail("delivery_too_large")
    target, actor = validate_target(row["target"]), validate_actor(row["actor"])
    publication = _record(row["publication"], {"operatorConfirmed", "bundleId", "targetFingerprint", "purpose"})
    if (publication["operatorConfirmed"] is not True or publication["bundleId"] != row["bundleId"]
            or publication["targetFingerprint"] != digest(target)):
        _fail("delivery_consent_required")
    preconditions = _record(row["preconditions"], set(_PRECONDITIONS))
    if any(preconditions[key] is not True for key in _PRECONDITIONS):
        _fail("delivery_preconditions_invalid")
    timestamp, pull_request = validate_timestamp(row["createdAt"]), _pull_request(row["pullRequest"])
    purpose = _text(publication["purpose"], 1000, multiline=True)
    files, payload = _decode_files(row["files"], target["pathPrefix"])
    manifest = _embedded_manifest(payload, row["bundleId"])
    _privacy(manifest, target)
    plan = {"schemaVersion": 1, "kind": "personal-evals-delivery-plan", "bundleId": manifest["bundleId"],
            "target": target, "actor": actor, "createdAt": timestamp, "pullRequest": pull_request,
            "publication": {"operatorConfirmed": True, "bundleId": manifest["bundleId"], "targetFingerprint": digest(target),
                            "purpose": purpose},
            "preconditions": dict(_PRECONDITIONS), "files": files}
    plan["planId"] = digest(plan)
    if type(row["planId"]) is not str or row["planId"] != plan["planId"] or canonical(row) != canonical(plan):
        _fail("delivery_identity_mismatch")
    return plan, manifest


def validate_delivery_plan(value) -> dict:
    """Validate detached bytes/identity only; no account or repository request."""
    return _validate_plan(value)[0]


def delivery_manifest(plan) -> dict:
    """Return the independently validated manifest from a complete delivery plan."""
    return _validate_plan(plan)[1]


def build_delivery_plan(bundle: Path, intent: dict, *, publication_consent: bool) -> dict:
    if publication_consent is not True:
        _fail("delivery_consent_required")
    intent = validate_delivery_intent(intent)
    manifest = verify_bundle(Path(bundle))
    _privacy(manifest, intent["target"])
    root = Path(bundle).resolve(strict=True)
    prefix = intent["target"]["pathPrefix"]
    payload = {"bundle.json": canonical(manifest) + b"\n"}
    for task in manifest["tasks"]:
        for file in task["files"]:
            path = f"tasks/{task['id']}/{file['path']}"
            data = _read_file(root, path)
            if len(data) != file["bytes"] or sha256(data) != file["sha256"]:
                _fail("delivery_bundle_changed")
            payload[path] = data
    plan = {"schemaVersion": 1, "kind": "personal-evals-delivery-plan", "bundleId": manifest["bundleId"],
            "target": intent["target"], "actor": intent["actor"], "createdAt": intent["createdAt"], "pullRequest": intent["pullRequest"],
            "publication": {"operatorConfirmed": True, "bundleId": manifest["bundleId"], "targetFingerprint": digest(intent["target"]),
                            "purpose": intent["purpose"]}, "preconditions": dict(_PRECONDITIONS),
            "files": [_file(prefix + "/" + path, data) for path, data in sorted(payload.items())]}
    plan["planId"] = digest(plan)
    return validate_delivery_plan(plan)


def read_delivery_plan(path: Path) -> dict:
    return validate_delivery_plan(read_json(Path(path), MAX_DELIVERY_BYTES))


def write_delivery_plan(plan, destination: Path) -> dict:
    plan = validate_delivery_plan(plan)
    data = canonical(plan) + b"\n"
    if len(data) > MAX_DELIVERY_BYTES:
        _fail("delivery_too_large")
    write_bytes(Path(destination), data)
    return {"planId": plan["planId"], "bundleId": plan["bundleId"], "files": len(plan["files"]), "bytes": len(data), "sha256": sha256(data)}
