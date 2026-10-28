"""Explicit committed-file snapshots. No worktree content, checkout or network."""

import hashlib
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import subprocess
import time
import unicodedata

from .errors import UserError
from .jsonio import canonical, digest, sha256

MAX_FILES = 64
MAX_FILE_BYTES = 128 * 1024
MAX_CONTENT_BYTES = 1024 * 1024
MAX_SNAPSHOT_BYTES = 4 * 1024 * 1024
GIT_DEADLINE_SECONDS = 10
_LABEL = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*\Z")
_SECRET_STEMS = {"auth", "credential", "credentials", "secret", "secrets", "token", "tokens",
                 "password", "passwords", "client_secret", "client_secrets", "service-account", "service_account"}
_SECRET_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".jks", ".keystore"}
_DATA_SUFFIXES = {"", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".txt", ".csv", ".properties", ".xml", ".db", ".sqlite"}
_CREDENTIAL_DIRS = {".ssh", ".aws", ".azure", ".kube"}
_CREDENTIAL_FILES = {".netrc", ".git-credentials", ".npmrc", ".pypirc", ".pgpass"}
_FLAGS = ["--no-pager", "--no-replace-objects", "--no-lazy-fetch", "--no-optional-locks", "--literal-pathspecs",
          "-c", "core.fsmonitor=false", "-c", "core.hooksPath=" + os.devnull]


def _fail(code="repository_snapshot_invalid"):
    raise UserError(code)


def _record(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        _fail()
    return value


def _policy(value):
    row = _record(value, {"classification", "permission", "containsPersonalData"})
    if row["classification"] not in ("authored", "private") or row["permission"] not in ("owned", "authorized") or type(row["containsPersonalData"]) is not bool:
        _fail("repository_policy_invalid")
    return dict(row)


def _label(value):
    if type(value) is not str or not 1 <= len(value) <= 64 or not _LABEL.fullmatch(value):
        _fail("repository_label_invalid")
    return value


def _path(value):
    if type(value) is not str or not 1 <= len(value) <= 240 or any(char in value for char in "\\:*?[]{}"):
        _fail("repository_path_invalid")
    if any(unicodedata.category(char) in ("Cc", "Cs") for char in value):
        _fail("repository_path_invalid")
    parts = value.split("/")
    if any(not part or part in (".", "..") for part in parts):
        _fail("repository_path_invalid")
    for part in parts:
        folded = part.casefold()
        if folded == ".git" or folded.startswith(".env") or folded in _CREDENTIAL_DIRS:
            _fail("repository_secret_path")
    folded = parts[-1].casefold()
    stem, suffix = folded.split(".", 1)[0], Path(folded).suffix
    credential_stem = stem in _SECRET_STEMS or stem.startswith(("client_secret", "client-secret", "service-account", "service_account"))
    if (folded in _CREDENTIAL_FILES or suffix in _SECRET_SUFFIXES
            or folded.startswith(("id_rsa", "id_dsa", "id_ecdsa", "id_ed25519"))
            or (credential_stem and suffix in _DATA_SUFFIXES)):
        _fail("repository_secret_path")
    return value


def _paths(values):
    if type(values) is not list or not 1 <= len(values) <= MAX_FILES:
        _fail("repository_paths_invalid")
    result, seen = [], set()
    for value in values:
        path = _path(value)
        if path.casefold() in seen:
            _fail("repository_paths_invalid")
        seen.add(path.casefold())
        result.append(path)
    return result


def _hex(value, length):
    if type(value) is not str or not re.fullmatch(r"[0-9a-f]{" + str(length) + r"}", value):
        _fail()
    return value


def _content(value):
    if type(value) is not str or len(value) > MAX_FILE_BYTES:
        _fail("repository_content_invalid")
    if any(unicodedata.category(char) == "Cc" and char not in "\n\r\t" for char in value):
        _fail("repository_content_invalid")
    try:
        data = value.encode("utf-8", errors="strict")
    except UnicodeError:
        _fail("repository_content_invalid")
    if len(data) > MAX_FILE_BYTES:
        _fail("repository_file_too_large")
    return data


def _blob_digest(data, object_format):
    return hashlib.new(object_format, b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def validate_snapshot(value):
    """Verify a detached artifact's shape and hashes; no Git/provider IO."""
    row = _record(value, {"schemaVersion", "kind", "repository", "dataPolicy", "dataPolicyFingerprint", "files", "snapshotId"})
    if type(row["schemaVersion"]) is not int or row["schemaVersion"] != 1 or row["kind"] != "personal-evals-repository":
        _fail()
    repository = _record(row["repository"], {"label", "commit", "objectFormat"})
    object_format = repository["objectFormat"]
    if object_format not in ("sha1", "sha256"):
        _fail()
    oid_length = 40 if object_format == "sha1" else 64
    output = {"schemaVersion": 1, "kind": "personal-evals-repository",
              "repository": {"label": _label(repository["label"]), "commit": _hex(repository["commit"], oid_length), "objectFormat": object_format},
              "dataPolicy": _policy(row["dataPolicy"])}
    output["dataPolicyFingerprint"] = digest(output["dataPolicy"])
    if row["dataPolicyFingerprint"] != output["dataPolicyFingerprint"]:
        _fail("repository_identity_mismatch")
    if type(row["files"]) is not list or not 1 <= len(row["files"]) <= MAX_FILES:
        _fail()
    files, total = [], 0
    for item in row["files"]:
        file = _record(item, {"path", "mode", "gitBlob", "sha256", "bytes", "content"})
        path = _path(file["path"])
        if file["mode"] not in ("100644", "100755") or type(file["bytes"]) is not int:
            _fail()
        data = _content(file["content"])
        total += len(data)
        if total > MAX_CONTENT_BYTES:
            _fail("repository_content_too_large")
        blob = _blob_digest(data, object_format)
        if file["bytes"] != len(data) or _hex(file["sha256"], 64) != sha256(data) or _hex(file["gitBlob"], oid_length) != blob:
            _fail("repository_identity_mismatch")
        files.append({"path": path, "mode": file["mode"], "gitBlob": blob, "sha256": sha256(data), "bytes": len(data), "content": file["content"]})
    _paths([file["path"] for file in files])
    output["files"] = files
    output["snapshotId"] = digest(output)
    if row["snapshotId"] != output["snapshotId"]:
        _fail("repository_identity_mismatch")
    if len(canonical(output)) + 1 > MAX_SNAPSHOT_BYTES:
        _fail("repository_snapshot_too_large")
    return output


def _git_environment():
    # Do not inherit repository redirection, configuration injection or trace IO.
    return {"PATH": os.defpath, "LANG": "C", "LC_ALL": "C",
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_NO_REPLACE_OBJECTS": "1", "GIT_NO_LAZY_FETCH": "1", "GIT_OPTIONAL_LOCKS": "0",
            "GIT_LITERAL_PATHSPECS": "1", "GIT_TERMINAL_PROMPT": "0", "GIT_ALLOW_PROTOCOL": ""}


def _stop(process):
    # Every process starts its own POSIX session; only that owned group is killed.
    failed = False
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except OSError:
        failed = True
    for stream in (process.stdout, process.stderr):
        if stream is not None:
            try:
                stream.close()
            except OSError:
                failed = True
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        failed = True
    if failed:
        _fail("repository_git_cleanup_failed")


def _git(repo, arguments, maximum):
    executable = shutil.which("git")
    if executable is None or os.name != "posix":
        _fail("repository_git_unavailable")
    process = None
    finished = False
    try:
        process = subprocess.Popen([executable, *_FLAGS, "-C", str(repo), *arguments], stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=_git_environment(),
                                   close_fds=True, start_new_session=True)
        deadline = time.monotonic() + GIT_DEADLINE_SECONDS
        buffers = {"stdout": bytearray(), "stderr": bytearray()}
        with selectors.DefaultSelector() as selector:
            for name, stream in (("stdout", process.stdout), ("stderr", process.stderr)):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, name)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    _fail("repository_git_timeout")
                for key, _events in selector.select(min(remaining, 0.2)):
                    cap = maximum if key.data == "stdout" else 16 * 1024
                    chunk = os.read(key.fd, min(65536, cap - len(buffers[key.data]) + 1))
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    buffers[key.data].extend(chunk)
                    if len(buffers[key.data]) > cap:
                        _fail("repository_git_output_too_large")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _fail("repository_git_timeout")
            try:
                returncode = process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                _fail("repository_git_timeout")
        finished = True
        if returncode != 0:
            _fail("repository_git_failed")
        return bytes(buffers["stdout"])
    except (OSError, ValueError):
        _fail("repository_git_failed")
    finally:
        if process is not None:
            if not finished:
                _stop(process)
            else:
                process.stdout.close()
                process.stderr.close()


def capture_repository(repo: Path, revision: str, paths: list[str], *, label: str, data_policy: dict):
    """Read only chosen committed blobs, never source content from the worktree."""
    label, policy, paths = _label(label), _policy(data_policy), _paths(paths)
    if type(revision) is not str or not 1 <= len(revision) <= 256 or any(unicodedata.category(char) in ("Cc", "Cs") for char in revision):
        _fail("repository_revision_invalid")
    try:
        root = Path(repo).resolve(strict=True)
        if not root.is_dir():
            _fail("repository_path_invalid")
    except (OSError, RuntimeError, TypeError, ValueError):
        _fail("repository_path_invalid")
    metadata = _git(root, ["rev-parse", "--show-object-format=storage", "--is-bare-repository", "--is-inside-work-tree", "--show-prefix"], 4096).splitlines()
    if (len(metadata) != 4 or metadata[0] not in (b"sha1", b"sha256") or metadata[3] != b""
            or (metadata[1:3] not in ([b"true", b"false"], [b"false", b"true"]))):
        _fail("repository_root_required")
    object_format = metadata[0].decode("ascii")
    oid_length = 40 if object_format == "sha1" else 64
    resolved = _git(root, ["rev-parse", "--verify", "--quiet", "--output-object-format=storage", "--end-of-options", revision + "^{commit}"], 256)
    try:
        commit = _hex(resolved.decode("ascii").removesuffix("\n"), oid_length)
    except UnicodeError:
        _fail("repository_revision_invalid")
    files, total = [], 0
    for path in paths:
        entry = _git(root, ["ls-tree", "--full-tree", "-z", "-l", commit, "--", path], 4096)
        rows = entry.split(b"\0")
        if len(rows) != 2 or rows[1] != b"":
            _fail("repository_file_unavailable")
        header, separator, name = rows[0].partition(b"\t")
        fields = header.split()
        if separator != b"\t" or name != path.encode("utf-8") or len(fields) != 4 or fields[0] not in (b"100644", b"100755") or fields[1] != b"blob":
            _fail("repository_file_unavailable")
        try:
            blob = _hex(fields[2].decode("ascii"), oid_length)
            size_text = fields[3].decode("ascii")
            if not re.fullmatch(r"0|[1-9][0-9]*", size_text):
                _fail("repository_file_unavailable")
            size = int(size_text)
        except (UnicodeError, ValueError):
            _fail("repository_file_unavailable")
        if size > MAX_FILE_BYTES:
            _fail("repository_file_too_large")
        total += size
        if total > MAX_CONTENT_BYTES:
            _fail("repository_content_too_large")
        data = _git(root, ["cat-file", "blob", blob], MAX_FILE_BYTES)
        if len(data) != size or _blob_digest(data, object_format) != blob:
            _fail("repository_identity_mismatch")
        try:
            content = data.decode("utf-8", errors="strict")
        except UnicodeError:
            _fail("repository_content_invalid")
        _content(content)
        files.append({"path": path, "mode": fields[0].decode("ascii"), "gitBlob": blob,
                      "sha256": sha256(data), "bytes": len(data), "content": content})
    snapshot = {"schemaVersion": 1, "kind": "personal-evals-repository",
                "repository": {"label": label, "commit": commit, "objectFormat": object_format},
                "dataPolicy": policy, "dataPolicyFingerprint": digest(policy), "files": files}
    snapshot["snapshotId"] = digest(snapshot)
    return validate_snapshot(snapshot)
