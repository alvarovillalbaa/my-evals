"""Seal explicit Harbor inputs; never execute a task or discover extra files.

Inputs and outputs must live in trusted local directories that are not being
concurrently modified. Link/identity checks reject observed changes, but this
path-based reader is not a sandbox against hostile directory replacement.
"""

import math
import os
from pathlib import Path
import re
import stat
import tomllib

from .errors import UserError
from .jsonio import MAX_JSON_BYTES, canonical, digest, read_bytes, read_json, sha256

HARBOR_COMMIT = "3095f96e5cc813783dc50c9c7970bc225fb7627b"
MAX_TASKS = 100
MAX_FILES = 100
MAX_FILE_BYTES = 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024
_SLUG = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*\Z")
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*\Z")
_HASH = re.compile(r"[a-f0-9]{64}\Z")
_REQUIRED = {"task.toml", "instruction.md", "environment/Dockerfile", "tests/test.sh"}
_SUITE_KEYS = {"schemaVersion", "id", "version", "split", "decision", "dataPolicy", "tasks"}
_MANIFEST_KEYS = {"schemaVersion", "kind", "suite", "split", "decision", "dataPolicy",
                  "dataPolicyFingerprint", "harbor", "tasks", "sampleManifestId", "bundleId"}
_TASK_KEYS = {"id", "name", "version", "critical", "rewardKey", "successThreshold", "harborDigest", "files"}


def _fail(code="suite_invalid"):
    raise UserError(code)


def _record(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        _fail()
    return value


def _text(value, maximum):
    if type(value) is not str or not value.strip() or len(value) > maximum:
        _fail()
    if any(ord(char) < 32 or 0x7F <= ord(char) <= 0x9F or 0xD800 <= ord(char) <= 0xDFFF for char in value):
        _fail()
    return value


def _slug(value):
    value = _text(value, 64)
    if not _SLUG.fullmatch(value):
        _fail()
    return value


def _integer(value, minimum=0, maximum=None):
    if type(value) is not int or value < minimum or maximum is not None and value > maximum:
        _fail()
    return value


def _ratio(value):
    if type(value) not in (int, float) or not 0 <= value <= 1 or not math.isfinite(value):
        _fail()
    return value


def _boolean(value):
    if type(value) is not bool:
        _fail()
    return value


def _split(value):
    if value not in ("validation", "holdout", "blind_holdout"):
        _fail()
    return value


def _decision(value):
    row = _record(value, {"question", "minimumPairedTasks", "minimumImprovement", "maxCriticalRegressions"})
    return {"question": _text(row["question"], 2000),
            "minimumPairedTasks": _integer(row["minimumPairedTasks"], 2),
            "minimumImprovement": _ratio(row["minimumImprovement"]),
            "maxCriticalRegressions": _integer(row["maxCriticalRegressions"])}


def _policy(value):
    row = _record(value, {"classification", "permission", "containsPersonalData"})
    if row["classification"] not in ("authored", "private") or row["permission"] not in ("owned", "authorized"):
        _fail()
    return {"classification": row["classification"], "permission": row["permission"],
            "containsPersonalData": _boolean(row["containsPersonalData"])}


def _relative(value, maximum=240):
    if type(value) is not str or not value or len(value) > maximum or "\\" in value or ":" in value:
        _fail("path_invalid")
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        _fail("path_invalid")
    if any(ord(char) < 32 or 0x7F <= ord(char) <= 0x9F or 0xD800 <= ord(char) <= 0xDFFF for char in value):
        _fail("path_invalid")
    return parts


def _file_path(value):
    parts = _relative(value)
    if value not in ("task.toml", "instruction.md", "README.md") and not (len(parts) > 1 and parts[0] in ("environment", "tests", "solution")):
        _fail("task_file_forbidden")
    for part in parts:
        lower = part.lower()
        if (lower.startswith(".") or lower in {"credentials", "secrets", "secret", "token", "tokens", "password", "passwords", "kubeconfig", "service_account.json", "service-account.json", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519"}
                or lower == "__pycache__" or lower.endswith((".pyc", ".swp", ".swo", "~"))
                or lower.startswith(("credentials.", "secrets.", "secret.", "token.", "tokens.", "password.", "passwords.", "id_rsa.", "id_dsa.", "id_ecdsa.", "id_ed25519."))
                or re.match(r"(?:api|access|auth|refresh|private|secret|client)[_-](?:key|token|secret)(?:[._-]|$)", lower)
                or lower.endswith((".pem", ".key", ".p12", ".pfx"))):
            _fail("task_file_forbidden")
    return value


def _directory(path):
    try:
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode):
            _fail("symlink_forbidden")
        if not stat.S_ISDIR(info.st_mode):
            _fail("input_unreadable")
        return info
    except OSError as error:
        raise UserError("input_unreadable") from error


def _under(root, relative, *, directory=False):
    parts = _relative(relative, 512)
    path = root
    try:
        for index, part in enumerate(parts):
            path = path / part
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode):
                _fail("symlink_forbidden")
            if index < len(parts) - 1 or directory:
                if not stat.S_ISDIR(info.st_mode):
                    _fail("input_unreadable")
            elif not stat.S_ISREG(info.st_mode):
                _fail("input_unreadable")
        if not path.resolve(strict=True).is_relative_to(root):
            _fail("path_invalid")
        return path
    except OSError as error:
        raise UserError("input_unreadable") from error


def _read_file(root, relative, maximum=MAX_FILE_BYTES):
    try:
        path = _under(root, relative)
        before = path.stat(follow_symlinks=False)
        data = read_bytes(path, maximum)
        _under(root, relative)
        after = path.stat(follow_symlinks=False)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) or len(data) != after.st_size:
            _fail("input_changed")
        return data
    except OSError as error:
        raise UserError("input_unreadable") from error


def _task_header(data):
    try:
        parsed = tomllib.loads(data.decode("utf-8"))
    except (UnicodeError, ValueError, RecursionError) as error:
        raise UserError("task_toml_invalid") from error
    if parsed.get("schema_version") != "1.4" or any(key in parsed for key in ("version", "steps", "multi_step_reward_strategy")):
        _fail("task_profile_unsupported")
    task = parsed.get("task")
    if type(task) is not dict or "name" not in task or "version" not in task:
        _fail("task_toml_invalid")
    name = _text(task["name"], 257)
    if not _NAME.fullmatch(name):
        _fail("task_toml_invalid")
    return name, _text(task["version"], 128)


def _harbor_digest(files):
    content = "".join(f"{row['path']}\0{row['sha256']}\n" for row in sorted(files, key=lambda row: row["path"]))
    return "sha256:" + sha256(content.encode("utf-8"))


def _hash(value):
    if type(value) is not str or not _HASH.fullmatch(value):
        _fail("bundle_invalid")
    return value


def validate_manifest(value):
    """Validate metadata identities only; verify_bundle also checks actual files."""
    row = _record(value, _MANIFEST_KEYS)
    if type(row["schemaVersion"]) is not int or row["schemaVersion"] != 1 or row["kind"] != "personal-evals-bundle":
        _fail("bundle_invalid")
    suite = _record(row["suite"], {"id", "version"})
    harbor = _record(row["harbor"], {"sourceCommit", "taskSchema", "profile"})
    if harbor != {"sourceCommit": HARBOR_COMMIT, "taskSchema": "1.4", "profile": "single-step-docker-v1"}:
        _fail("bundle_invalid")
    manifest = {"schemaVersion": 1, "kind": "personal-evals-bundle",
                "suite": {"id": _slug(suite["id"]), "version": _text(suite["version"], 128)},
                "split": _split(row["split"]), "decision": _decision(row["decision"]), "dataPolicy": _policy(row["dataPolicy"])}
    manifest["dataPolicyFingerprint"] = digest(manifest["dataPolicy"])
    if _hash(row["dataPolicyFingerprint"]) != manifest["dataPolicyFingerprint"]:
        _fail("bundle_hash_mismatch")
    manifest["harbor"] = dict(harbor)
    if type(row["tasks"]) is not list or not 1 <= len(row["tasks"]) <= MAX_TASKS:
        _fail("bundle_invalid")
    tasks, task_ids, names, total = [], set(), set(), 0
    for value in row["tasks"]:
        task = _record(value, _TASK_KEYS)
        identity, name = _slug(task["id"]), _text(task["name"], 257)
        if identity in task_ids or name in names or not _NAME.fullmatch(name):
            _fail("bundle_invalid")
        task_ids.add(identity)
        names.add(name)
        if type(task["files"]) is not list or not 1 <= len(task["files"]) <= MAX_FILES:
            _fail("bundle_invalid")
        files, paths, portable_paths = [], set(), set()
        for value in task["files"]:
            file = _record(value, {"path", "sha256", "bytes"})
            path = _file_path(file["path"])
            if path in paths or path.casefold() in portable_paths:
                _fail("bundle_invalid")
            paths.add(path)
            portable_paths.add(path.casefold())
            size = _integer(file["bytes"], 0, MAX_FILE_BYTES)
            total += size
            if total > MAX_TOTAL_BYTES:
                _fail("suite_too_large")
            files.append({"path": path, "sha256": _hash(file["sha256"]), "bytes": size})
        if not _REQUIRED.issubset(paths) or [file["path"] for file in files] != sorted(paths):
            _fail("bundle_invalid")
        harbor_digest = _harbor_digest(files)
        if task["harborDigest"] != harbor_digest:
            _fail("bundle_hash_mismatch")
        tasks.append({"id": identity, "name": name, "version": _text(task["version"], 128),
                      "critical": _boolean(task["critical"]), "rewardKey": _slug(task["rewardKey"]),
                      "successThreshold": _ratio(task["successThreshold"]), "harborDigest": harbor_digest, "files": files})
    manifest["tasks"] = tasks
    manifest["sampleManifestId"] = digest(tasks)
    if _hash(row["sampleManifestId"]) != manifest["sampleManifestId"]:
        _fail("bundle_hash_mismatch")
    manifest["bundleId"] = digest(manifest)
    if _hash(row["bundleId"]) != manifest["bundleId"]:
        _fail("bundle_hash_mismatch")
    if len(canonical(manifest)) + 1 > MAX_JSON_BYTES:
        _fail("suite_too_large")
    return manifest


def prepare_suite(suite_file: Path):
    """Read only the explicit selected task files and return a sealed byte payload."""
    suite_file = Path(suite_file)
    try:
        if suite_file.is_symlink():
            _fail("symlink_forbidden")
        base = suite_file.parent.resolve(strict=True)
    except OSError as error:
        raise UserError("input_unreadable") from error
    row = _record(read_json(suite_file), _SUITE_KEYS)
    if type(row["schemaVersion"]) is not int or row["schemaVersion"] != 1:
        _fail()
    manifest = {"schemaVersion": 1, "kind": "personal-evals-bundle",
                "suite": {"id": _slug(row["id"]), "version": _text(row["version"], 128)},
                "split": _split(row["split"]), "decision": _decision(row["decision"]), "dataPolicy": _policy(row["dataPolicy"])}
    manifest["dataPolicyFingerprint"] = digest(manifest["dataPolicy"])
    manifest["harbor"] = {"sourceCommit": HARBOR_COMMIT, "taskSchema": "1.4", "profile": "single-step-docker-v1"}
    if type(row["tasks"]) is not list or not 1 <= len(row["tasks"]) <= MAX_TASKS:
        _fail()
    tasks, payload, task_ids, names, total = [], {}, set(), set(), 0
    for value in row["tasks"]:
        task = _record(value, {"id", "path", "files", "critical", "rewardKey", "successThreshold"})
        identity = _slug(task["id"])
        if identity in task_ids:
            _fail()
        task_ids.add(identity)
        _relative(task["path"])
        task_root = _under(base, task["path"], directory=True)
        if type(task["files"]) is not list or not 1 <= len(task["files"]) <= MAX_FILES:
            _fail()
        paths = [_file_path(path) for path in task["files"]]
        if len(set(path.casefold() for path in paths)) != len(paths) or not _REQUIRED.issubset(paths):
            _fail()
        files, header = [], None
        for path in sorted(paths):
            data = _read_file(task_root, path, min(MAX_FILE_BYTES, MAX_TOTAL_BYTES - total))
            total += len(data)
            if total > MAX_TOTAL_BYTES:
                _fail("suite_too_large")
            files.append({"path": path, "sha256": sha256(data), "bytes": len(data)})
            payload[f"tasks/{identity}/{path}"] = data
            if path == "task.toml":
                header = _task_header(data)
        name, version = header
        if name in names:
            _fail()
        names.add(name)
        tasks.append({"id": identity, "name": name, "version": version, "critical": _boolean(task["critical"]),
                      "rewardKey": _slug(task["rewardKey"]), "successThreshold": _ratio(task["successThreshold"]),
                      "harborDigest": _harbor_digest(files), "files": files})
    manifest["tasks"] = tasks
    manifest["sampleManifestId"] = digest(tasks)
    manifest["bundleId"] = digest(manifest)
    return validate_manifest(manifest), payload


def _inventory(root, expected):
    directories = {""}
    for relative in expected:
        directories.update(str(parent) for parent in Path(relative).parents if str(parent) != ".")
    actual = set()

    def visit(directory, prefix=""):
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    relative = prefix + entry.name
                    if entry.is_symlink():
                        _fail("symlink_forbidden")
                    if entry.is_dir(follow_symlinks=False):
                        if relative not in directories:
                            _fail("bundle_inventory_mismatch")
                        visit(Path(entry.path), relative + "/")
                    elif entry.is_file(follow_symlinks=False) and relative in expected:
                        actual.add(relative)
                    else:
                        _fail("bundle_inventory_mismatch")
        except OSError as error:
            raise UserError("input_unreadable") from error

    visit(root)
    if actual != expected:
        _fail("bundle_inventory_mismatch")


def verify_bundle(bundle: Path):
    """Verify the exact inventory, file bytes, pinned digest and task identities."""
    bundle = Path(bundle)
    _directory(bundle)
    try:
        root = bundle.resolve(strict=True)
    except OSError as error:
        raise UserError("input_unreadable") from error
    _under(root, "bundle.json")
    manifest = validate_manifest(read_json(root / "bundle.json"))
    expected, total = {"bundle.json"}, 0
    for task in manifest["tasks"]:
        files, header = [], None
        for file in task["files"]:
            relative = f"tasks/{task['id']}/{file['path']}"
            expected.add(relative)
            data = _read_file(root, relative, min(MAX_FILE_BYTES, MAX_TOTAL_BYTES - total))
            total += len(data)
            if len(data) != file["bytes"] or sha256(data) != file["sha256"]:
                _fail("bundle_hash_mismatch")
            files.append({"path": file["path"], "sha256": sha256(data), "bytes": len(data)})
            if file["path"] == "task.toml":
                header = _task_header(data)
        if header != (task["name"], task["version"]) or _harbor_digest(files) != task["harborDigest"]:
            _fail("bundle_hash_mismatch")
    _inventory(root, expected)
    return manifest


def write_bundle(suite_file: Path, destination: Path):
    """Create a new private directory; remove only our unchanged outputs on failure."""
    manifest, payload = prepare_suite(suite_file)
    destination = Path(destination)
    owned_files, owned_directories = [], []

    def make_directory(path):
        path.mkdir(mode=0o700)
        info = path.lstat()
        owned_directories.append((path, info.st_dev, info.st_ino))

    def write_file(path, data):
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        info = os.fstat(descriptor)
        owned_files.append((path, info.st_dev, info.st_ino))
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)

    try:
        make_directory(destination)
    except FileExistsError as error:
        raise UserError("output_exists") from error
    except OSError as error:
        raise UserError("output_unwritable") from error
    try:
        created = {destination}
        for relative, data in sorted(payload.items()):
            path = destination / relative
            for parent in reversed(path.parents):
                if parent == destination or destination in parent.parents:
                    if parent not in created:
                        make_directory(parent)
                        created.add(parent)
            write_file(path, data)
        write_file(destination / "bundle.json", canonical(manifest) + b"\n")
        return verify_bundle(destination)
    except BaseException as error:
        for path, device, inode in reversed(owned_files):
            try:
                info = path.lstat()
                if not stat.S_ISLNK(info.st_mode) and (info.st_dev, info.st_ino) == (device, inode):
                    path.unlink()
            except OSError:
                pass
        for path, device, inode in reversed(owned_directories):
            try:
                info = path.lstat()
                if stat.S_ISDIR(info.st_mode) and (info.st_dev, info.st_ino) == (device, inode):
                    path.rmdir()
            except OSError:
                pass
        if not isinstance(error, OSError):
            raise
        raise UserError("output_write_failed") from error
