"""Provider-neutral local handoffs and explicitly reviewed Harbor drafts.

No provider, task, grader or model is executed. Local directories share the
suite reader's trusted, non-concurrent filesystem boundary; hashes are not a
provider attestation or evidence that a generated grader is semantically sound.
"""

import os
from pathlib import Path
import stat
import tempfile

from .errors import UserError
from .jsonio import canonical, digest, parse_json, read_bytes, read_json, sha256
from .planning import MODEL
from .repository import validate_snapshot
from .suite import (HARBOR_COMMIT, MAX_FILES, MAX_FILE_BYTES, MAX_TOTAL_BYTES,
                    _NAME, _REQUIRED, _boolean, _decision, _directory, _file_path,
                    _hash, _inventory, _ratio, _record, _relative, _slug, _split,
                    _task_header, _text, _under, prepare_suite, write_bundle)

MAX_HANDOFF_BYTES = 4 * 1024 * 1024
MAX_GENERATED_TASKS = 20
_HARBOR = {"sourceCommit": HARBOR_COMMIT, "taskSchema": "1.4", "profile": "single-step-docker-v1"}
_INTENT_KEYS = {"schemaVersion", "model", "suite", "split", "decision", "tasks"}
_REQUEST_KEYS = _INTENT_KEYS | {"kind", "snapshot", "harbor", "requestId"}
_TASK_KEYS = {"id", "name", "version", "sourcePaths", "goal", "graderRequirements", "critical", "rewardKey", "successThreshold"}
_REVIEW_KEYS = {"schemaVersion", "kind", "status", "requestId", "snapshotId", "model", "responseSha256", "draftBundleId", "taskIds", "reviewId"}


def _fail(code="generation_invalid"):
    raise UserError(code)


def _bounded(value):
    if len(canonical(value)) + 1 > MAX_HANDOFF_BYTES:
        _fail("generation_too_large")


def _instruction(value, maximum):
    if type(value) is not str or not value.strip() or len(value) > maximum:
        _fail()
    if any((ord(char) < 32 and char not in "\n\r\t") or 0x7F <= ord(char) <= 0x9F
           or 0xD800 <= ord(char) <= 0xDFFF for char in value):
        _fail()
    return value


def _source_paths(value, available):
    if type(value) is not list or not 1 <= len(value) <= len(available):
        _fail()
    if any(type(path) is not str or path not in available for path in value) or len(set(value)) != len(value):
        _fail("generation_source_mismatch")
    return sorted(value)


def build_request(snapshot: dict, intent: dict) -> dict:
    """Seal owner intent and a complete selected-source snapshot; transmit nothing."""
    _bounded(snapshot)
    snapshot = validate_snapshot(snapshot)
    row = _record(intent, _INTENT_KEYS)
    if type(row["schemaVersion"]) is not int or row["schemaVersion"] != 1:
        _fail()
    if type(row["model"]) is not str or not MODEL.fullmatch(row["model"]):
        _fail("generation_model_invalid")
    suite = _record(row["suite"], {"id", "version"})
    request = {"schemaVersion": 1, "kind": "personal-evals-generation-request", "snapshot": snapshot,
               "model": row["model"], "suite": {"id": _slug(suite["id"]), "version": _text(suite["version"], 128)},
               "split": _split(row["split"]), "decision": _decision(row["decision"]), "harbor": dict(_HARBOR)}
    if type(row["tasks"]) is not list or not 1 <= len(row["tasks"]) <= MAX_GENERATED_TASKS:
        _fail()
    available = {file["path"] for file in snapshot["files"]}
    tasks, identifiers, names, used = [], set(), set(), set()
    for value in row["tasks"]:
        task = _record(value, _TASK_KEYS)
        identity, name = _slug(task["id"]), _text(task["name"], 257)
        if identity in identifiers or name in names or not _NAME.fullmatch(name):
            _fail()
        identifiers.add(identity)
        names.add(name)
        paths = _source_paths(task["sourcePaths"], available)
        used.update(paths)
        requirements = task["graderRequirements"]
        if type(requirements) is not list or not 1 <= len(requirements) <= 10:
            _fail()
        tasks.append({"id": identity, "name": name, "version": _text(task["version"], 128), "sourcePaths": paths,
                      "goal": _instruction(task["goal"], 4000), "graderRequirements": [_instruction(value, 1000) for value in requirements],
                      "critical": _boolean(task["critical"]), "rewardKey": _slug(task["rewardKey"]),
                      "successThreshold": _ratio(task["successThreshold"])})
    if used != available:
        _fail("generation_unused_source")
    request["tasks"] = tasks
    request["requestId"] = digest(request)
    _bounded(request)
    return request


def validate_request(value) -> dict:
    """Detach a strict self-contained handoff and verify its full identity."""
    row = _record(value, _REQUEST_KEYS)
    _bounded(row)
    if row["kind"] != "personal-evals-generation-request":
        _fail()
    _record(row["harbor"], set(_HARBOR))
    if row["harbor"] != _HARBOR:
        _fail("generation_harbor_mismatch")
    request = build_request(row["snapshot"], {key: row[key] for key in _INTENT_KEYS})
    if _hash(row["requestId"]) != request["requestId"] or canonical(row) != canonical(request):
        _fail("generation_request_mismatch")
    return request


def _generated_content(value, path):
    if type(value) is not str or len(value) > MAX_FILE_BYTES or "\0" in value:
        _fail("generation_file_invalid")
    try:
        data = value.encode("utf-8")
    except UnicodeError as error:
        raise UserError("generation_file_invalid") from error
    if len(data) > MAX_FILE_BYTES or path in _REQUIRED and not value.strip():
        _fail("generation_file_invalid")
    return data


def _response(request, value):
    row = _record(value, {"schemaVersion", "kind", "requestId", "snapshotId", "model", "tasks"})
    if (type(row["schemaVersion"]) is not int or row["schemaVersion"] != 1 or row["kind"] != "personal-evals-generated-tasks"
            or row["requestId"] != request["requestId"] or row["snapshotId"] != request["snapshot"]["snapshotId"]
            or row["model"] != request["model"]):
        _fail("generation_response_mismatch")
    if type(row["tasks"]) is not list or len(row["tasks"]) != len(request["tasks"]):
        _fail("generation_tasks_mismatch")
    wanted = {task["id"]: task for task in request["tasks"]}
    files_by_task, payload, total = {}, {}, 0
    available = {file["path"] for file in request["snapshot"]["files"]}
    for value in row["tasks"]:
        task = _record(value, {"id", "sourcePaths", "files"})
        identity = _slug(task["id"])
        if identity not in wanted or identity in files_by_task:
            _fail("generation_tasks_mismatch")
        owner = wanted[identity]
        if _source_paths(task["sourcePaths"], available) != owner["sourcePaths"]:
            _fail("generation_source_mismatch")
        if type(task["files"]) is not list or not 1 <= len(task["files"]) <= MAX_FILES:
            _fail()
        paths, portable, header = [], set(), None
        for value in task["files"]:
            file = _record(value, {"path", "content"})
            path = _file_path(file["path"])
            if path.casefold() in portable:
                _fail("generation_file_invalid")
            portable.add(path.casefold())
            data = _generated_content(file["content"], path)
            total += len(data)
            if total > MAX_TOTAL_BYTES:
                _fail("generation_too_large")
            paths.append(path)
            payload[f"tasks/{identity}/{path}"] = data
            if path == "task.toml":
                header = _task_header(data)
        if not _REQUIRED.issubset(paths) or header != (owner["name"], owner["version"]):
            _fail("generation_task_mismatch")
        for path in paths:
            parts = path.split("/")
            if any("/".join(parts[:index]).casefold() in portable for index in range(1, len(parts))):
                _fail("generation_file_invalid")
        files_by_task[identity] = sorted(paths)
    if set(files_by_task) != set(wanted):
        _fail("generation_tasks_mismatch")
    return files_by_task, payload


def _suite(request, files_by_task):
    return {"schemaVersion": 1, "id": request["suite"]["id"], "version": request["suite"]["version"],
            "split": request["split"], "decision": request["decision"], "dataPolicy": request["snapshot"]["dataPolicy"],
            "tasks": [{"id": task["id"], "path": f"tasks/{task['id']}", "files": files_by_task[task["id"]],
                       "critical": task["critical"], "rewardKey": task["rewardKey"], "successThreshold": task["successThreshold"]}
                      for task in request["tasks"]]}


def _owned_suite(value, request):
    row = _record(value, {"schemaVersion", "id", "version", "split", "decision", "dataPolicy", "tasks"})
    if type(row["tasks"]) is not list or len(row["tasks"]) != len(request["tasks"]):
        _fail("generation_owner_metadata_changed")
    files = {}
    for owner, value in zip(request["tasks"], row["tasks"], strict=True):
        task = _record(value, {"id", "path", "files", "critical", "rewardKey", "successThreshold"})
        if task["id"] != owner["id"] or type(task["files"]) is not list or not 1 <= len(task["files"]) <= MAX_FILES:
            _fail("generation_owner_metadata_changed")
        paths = [_file_path(path) for path in task["files"]]
        if len({path.casefold() for path in paths}) != len(paths):
            _fail("generation_file_invalid")
        files[owner["id"]] = sorted(paths)
    expected = _suite(request, files)
    if canonical(row) != canonical(expected):
        _fail("generation_owner_metadata_changed")
    return expected


class _PrivateOutput:
    """Track exact files/inodes, preserving unrelated additions on a failed write."""

    def __init__(self, root):
        self.root = Path(root)
        self.files = []
        self.directories = []
        self.created = set()

    def _mkdir(self, path):
        path.mkdir(mode=0o700)
        info = path.lstat()
        self.directories.append((path, info.st_dev, info.st_ino))
        self.created.add(path)

    def __enter__(self):
        try:
            self._mkdir(self.root)
        except FileExistsError as error:
            raise UserError("output_exists") from error
        except OSError as error:
            raise UserError("output_unwritable") from error
        return self

    def write(self, relative, data):
        _relative(relative, 512)
        path = self.root / relative
        for parent in reversed(path.parents):
            if parent == self.root or self.root in parent.parents:
                if parent not in self.created:
                    self._mkdir(parent)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        info = os.fstat(descriptor)
        self.files.append((path, info.st_dev, info.st_ino))
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)

    def __exit__(self, kind, error, _traceback):
        if error is None:
            return False
        for path, device, inode in reversed(self.files):
            try:
                info = path.lstat()
                if not stat.S_ISLNK(info.st_mode) and (info.st_dev, info.st_ino) == (device, inode):
                    path.unlink()
            except OSError:
                pass
        for path, device, inode in reversed(self.directories):
            try:
                info = path.lstat()
                if stat.S_ISDIR(info.st_mode) and (info.st_dev, info.st_ino) == (device, inode):
                    path.rmdir()
            except OSError:
                pass
        if isinstance(error, OSError):
            raise UserError("output_write_failed") from error
        return False


def _read_draft(draft):
    draft = Path(draft)
    _directory(draft)
    root = draft.resolve(strict=True)
    for name in ("request.json", "review.json", "suite.json"):
        _under(root, name)
    request = validate_request(read_json(root / "request.json", MAX_HANDOFF_BYTES))
    review = _record(read_json(root / "review.json", MAX_HANDOFF_BYTES), _REVIEW_KEYS)
    if (type(review["schemaVersion"]) is not int or review["schemaVersion"] != 1
            or review["kind"] != "personal-evals-generation-review" or review["status"] != "review_required"
            or review["requestId"] != request["requestId"] or review["snapshotId"] != request["snapshot"]["snapshotId"]
            or review["model"] != request["model"] or type(review["taskIds"]) is not list
            or review["taskIds"] != [task["id"] for task in request["tasks"]]):
        _fail("generation_review_mismatch")
    _hash(review["responseSha256"])
    _hash(review["draftBundleId"])
    if _hash(review["reviewId"]) != digest({key: value for key, value in review.items() if key != "reviewId"}):
        _fail("generation_review_mismatch")
    suite = _owned_suite(read_json(root / "suite.json"), request)
    manifest, payload = prepare_suite(root / "suite.json")
    if manifest["bundleId"] != review["draftBundleId"]:
        _fail("generation_draft_changed")
    if [task["id"] for task in manifest["tasks"]] != review["taskIds"]:
        _fail("generation_tasks_mismatch")
    for owner, actual in zip(request["tasks"], manifest["tasks"], strict=True):
        if (actual["name"], actual["version"]) != (owner["name"], owner["version"]):
            _fail("generation_task_mismatch")
    _inventory(root, {"request.json", "review.json", "suite.json", *payload})
    return request, review, manifest, payload, suite


def import_response(request: dict, response_file: Path, destination: Path) -> dict:
    """Validate supplied task contents and create a review-required private draft."""
    request = validate_request(request)
    raw = read_bytes(Path(response_file), MAX_HANDOFF_BYTES)
    files, payload = _response(request, parse_json(raw, MAX_HANDOFF_BYTES))
    suite = _suite(request, files)
    with _PrivateOutput(destination) as output:
        for path, data in sorted(payload.items()):
            output.write(path, data)
        output.write("suite.json", canonical(suite) + b"\n")
        manifest, _payload = prepare_suite(output.root / "suite.json")
        review = {"schemaVersion": 1, "kind": "personal-evals-generation-review", "status": "review_required",
                  "requestId": request["requestId"], "snapshotId": request["snapshot"]["snapshotId"], "model": request["model"],
                  "responseSha256": sha256(raw), "draftBundleId": manifest["bundleId"],
                  "taskIds": [task["id"] for task in request["tasks"]]}
        review["reviewId"] = digest(review)
        _bounded(review)
        output.write("request.json", canonical(request) + b"\n")
        output.write("review.json", canonical(review) + b"\n")
        _read_draft(output.root)
        return review


def accept_draft(draft: Path, destination: Path, *, reviewed: bool) -> dict:
    """Owner attestation only; validation cannot establish grader quality/authorship."""
    if reviewed is not True:
        _fail("generation_review_required")
    request, review, manifest, payload, suite = _read_draft(draft)
    destination = Path(destination)
    root = Path(draft).resolve(strict=True)
    resolved = destination.resolve()
    if resolved == root or root in resolved.parents:
        _fail("output_inside_draft")
    # Seal the captured reviewed bytes, not a second mutable read of the draft.
    with tempfile.TemporaryDirectory(prefix="personal-evals-reviewed-") as temporary:
        with _PrivateOutput(Path(temporary) / "captured") as captured:
            for path, data in sorted(payload.items()):
                captured.write(path, data)
            captured.write("suite.json", canonical(suite) + b"\n")
            accepted = write_bundle(captured.root / "suite.json", destination)
    if accepted["bundleId"] != manifest["bundleId"]:
        _fail("generation_draft_changed")
    return {"reviewId": review["reviewId"], "requestId": request["requestId"],
            "snapshotId": request["snapshot"]["snapshotId"], "bundleId": accepted["bundleId"], "status": "accepted"}
