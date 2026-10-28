"""Authored T2 cases; Git/process fixtures run only after separate approval."""

import copy
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from personal_evals.errors import UserError
from personal_evals.jsonio import canonical, digest, sha256
from personal_evals.repository import capture_repository, validate_snapshot, _git


POLICY = {"classification": "authored", "permission": "owned", "containsPersonalData": False}


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.repo = self.root / "repository"
        self.init_repo(self.repo)
        self.write("source.py", b"print('authored')\n")
        self.write("read me.txt", "Caf\u00e9\r\n".encode())
        self.commit()

    def git(self, *arguments, repo=None):
        environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        environment.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                            "GIT_CONFIG_SYSTEM": os.devnull, "LC_ALL": "C"})
        result = subprocess.run([shutil.which("git"), "-c", "core.hooksPath=" + os.devnull,
                                 "-c", "commit.gpgsign=false", "-C", str(repo or self.repo), *arguments],
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env=environment, timeout=10, check=True)
        return result.stdout

    def init_repo(self, path, object_format="sha1"):
        path.mkdir()
        self.git("init", "--quiet", "--initial-branch=main", "--object-format=" + object_format, repo=path)
        self.git("config", "user.name", "Authored Fixture", repo=path)
        self.git("config", "user.email", "fixture@example.invalid", repo=path)

    def write(self, name, content):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def commit(self):
        self.git("add", "--all")
        self.git("commit", "--quiet", "--message", "Authored fixture")
        return self.git("rev-parse", "HEAD").decode().strip()

    def capture(self, paths=None, revision="HEAD", repo=None):
        return capture_repository(repo or self.repo, revision, paths or ["source.py"], label="authored", data_policy=POLICY)

    def test_snapshot_reads_committed_bytes_and_binds_git_header_hash(self):
        result = self.capture()
        row = result["files"][0]
        data = b"print('authored')\n"
        self.assertEqual(row["content"].encode(), data)
        self.assertEqual(row["bytes"], len(data))
        self.assertEqual(row["sha256"], sha256(data))
        self.assertEqual(row["gitBlob"], hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest())
        self.assertEqual(result["snapshotId"], digest({key: value for key, value in result.items() if key != "snapshotId"}))
        self.assertNotIn(str(self.root), canonical(result).decode())

    def test_dirty_worktree_untracked_files_and_index_are_preserved(self):
        index = (self.repo / ".git/index").read_bytes()
        self.write("source.py", b"private unsaved change\n")
        self.write("untracked.txt", b"unsaved\n")
        result = self.capture()
        self.assertEqual(result["files"][0]["content"], "print('authored')\n")
        self.assertEqual((self.repo / "source.py").read_bytes(), b"private unsaved change\n")
        self.assertEqual((self.repo / "untracked.txt").read_bytes(), b"unsaved\n")
        self.assertEqual((self.repo / ".git/index").read_bytes(), index)

    def test_old_commit_selection_does_not_follow_later_branch_changes(self):
        first = self.git("rev-parse", "HEAD").decode().strip()
        self.write("source.py", b"new committed content\n")
        second = self.commit()
        snapshot = self.capture(revision=first)
        self.assertEqual(snapshot["repository"]["commit"], first)
        self.assertNotEqual(first, second)
        self.assertEqual(snapshot["files"][0]["content"], "print('authored')\n")

    def test_explicit_file_order_and_executable_mode_are_preserved(self):
        (self.repo / "source.py").chmod(0o755)
        self.commit()
        result = self.capture(["read me.txt", "source.py"])
        self.assertEqual([row["path"] for row in result["files"]], ["read me.txt", "source.py"])
        self.assertEqual(result["files"][0]["content"], "Caf\u00e9\r\n")
        self.assertEqual(result["files"][1]["mode"], "100755")

    def test_literal_option_looking_and_space_paths_never_become_flags(self):
        self.write("--name.txt", b"selected literal\n")
        self.write("src/auth.py", b"def authorized(): return True\n")
        self.write("src/tokens.py", b"TOKEN_KIND = 'identifier'\n")
        self.write("src/auth/route.py", b"ROUTE = '/auth/login'\n")
        self.write(".github/workflows/test.yml", b"name: Authored source\n")
        self.write(".gitignore", b"__pycache__/\n")
        self.commit()
        paths = ["--name.txt", "read me.txt", "src/auth.py", "src/tokens.py", "src/auth/route.py", ".github/workflows/test.yml", ".gitignore"]
        result = self.capture(paths)
        self.assertEqual(result["files"][0]["content"], "selected literal\n")
        self.assertEqual([row["path"] for row in result["files"]], paths)
        with self.assertRaises(UserError):
            self.capture(revision="--help")

    def test_secret_dot_traversal_glob_and_control_paths_fail_before_git(self):
        for path in (".env", ".env.example", ".git/config", "nested/.aws/config", ".ssh/config", ".azure/token.json", ".kube/config",
                     "secrets.json", "auth.json", "tokens.yaml", "passwords", "id_ed25519", "private.key", ".netrc",
                     "../source.py", "/source.py", "a//b", "a/./b", "a\\b", "*.py", ":(glob)*", "x?", "x[1]", "x\n"):
            with self.subTest(path=path), patch("personal_evals.repository._git") as runner:
                with self.assertRaises(UserError):
                    self.capture([path])
                runner.assert_not_called()

    def test_duplicate_and_casefold_paths_are_rejected(self):
        for paths in (["source.py", "source.py"], ["Source.py", "source.py"], [], [f"file{index}.txt" for index in range(65)]):
            with self.subTest(paths=paths), self.assertRaises(UserError):
                capture_repository(self.repo, "HEAD", paths, label="authored", data_policy=POLICY)

    def test_missing_selected_and_untracked_only_files_are_not_read_from_disk(self):
        self.write("untracked.txt", b"not committed\n")
        for name in ("missing.txt", "untracked.txt"):
            with self.subTest(name=name), self.assertRaises(UserError):
                self.capture([name])

    def test_committed_links_directories_and_gitlinks_are_rejected(self):
        (self.repo / "link.py").symlink_to("source.py")
        self.write("directory/entry.txt", b"nested\n")
        commit = self.commit()
        self.git("update-index", "--add", "--cacheinfo", "160000," + commit + ",submodule")
        self.git("commit", "--quiet", "--message", "Authored gitlink")
        for name in ("link.py", "directory", "submodule"):
            with self.subTest(name=name), self.assertRaises(UserError):
                self.capture([name])

    def test_byte_and_total_limits_are_enforced_before_blob_capture(self):
        self.write("large.txt", b"x" * (128 * 1024 + 1))
        for index in range(9):
            self.write(f"part{index}.txt", b"x" * (128 * 1024))
        self.commit()
        with self.assertRaisesRegex(UserError, "repository_file_too_large"):
            self.capture(["large.txt"])
        with self.assertRaisesRegex(UserError, "repository_content_too_large"):
            self.capture([f"part{index}.txt" for index in range(9)])

    def test_non_utf8_nul_and_disallowed_controls_are_rejected(self):
        for index, content in enumerate((b"\xff", b"a\0b", b"a\x1bb", b"a\x7fb")):
            self.write(f"invalid{index}.txt", content)
        self.commit()
        for index in range(4):
            with self.subTest(index=index), self.assertRaisesRegex(UserError, "repository_content_invalid"):
                self.capture([f"invalid{index}.txt"])

    def test_sha256_repository_uses_sha256_git_object_headers(self):
        repository = self.root / "sha256-repository"
        self.init_repo(repository, "sha256")
        (repository / "text.txt").write_bytes(b"sha256 fixture\n")
        self.git("add", "--all", repo=repository)
        self.git("commit", "--quiet", "--message", "Authored SHA256", repo=repository)
        snapshot = self.capture(["text.txt"], repo=repository)
        self.assertEqual(snapshot["repository"]["objectFormat"], "sha256")
        self.assertEqual(len(snapshot["repository"]["commit"]), 64)
        self.assertEqual(snapshot["files"][0]["gitBlob"], hashlib.sha256(b"blob 15\0sha256 fixture\n").hexdigest())

    def test_replace_refs_do_not_substitute_a_different_committed_tree(self):
        original = self.git("rev-parse", "HEAD").decode().strip()
        self.write("source.py", b"replacement\n")
        replacement = self.commit()
        self.git("replace", original, replacement)
        snapshot = self.capture(revision=original)
        self.assertEqual(snapshot["repository"]["commit"], original)
        self.assertEqual(snapshot["files"][0]["content"], "print('authored')\n")

    def test_ambient_git_redirection_and_trace_settings_do_not_escape_the_explicit_repo(self):
        other = self.root / "other"
        self.init_repo(other)
        marker = self.root / "trace-should-not-exist"
        filter_marker = self.root / "filter-should-not-run"
        filter_program = self.root / "owned-filter"
        filter_program.write_text(f"#!{sys.executable}\nfrom pathlib import Path\nPath({str(filter_marker)!r}).write_text('ran')\n")
        filter_program.chmod(0o700)
        self.write(".gitattributes", b"*.py filter=owned diff=owned\n")
        self.commit()
        for setting in ("filter.owned.smudge", "filter.owned.clean", "diff.owned.textconv"):
            self.git("config", setting, str(filter_program))
        with patch.dict(os.environ, {"GIT_DIR": str(other / ".git"), "GIT_WORK_TREE": str(other),
                                    "GIT_INDEX_FILE": str(marker), "GIT_TRACE": str(marker), "GIT_NO_LAZY_FETCH": "0",
                                    "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "invalid.setting", "GIT_CONFIG_VALUE_0": "raw-secret"}):
            snapshot = self.capture()
        self.assertEqual(snapshot["files"][0]["content"], "print('authored')\n")
        self.assertFalse(marker.exists())
        self.assertFalse(filter_marker.exists())

    def test_missing_local_blob_fails_without_fetching_or_altering_the_repository(self):
        oid = self.git("rev-parse", "HEAD:source.py").decode().strip()
        (self.repo / ".git/objects" / oid[:2] / oid[2:]).unlink()
        self.git("config", "remote.authored.promisor", "true")
        self.git("config", "remote.authored.url", str(self.root / "missing-owned-local-remote"))
        self.git("config", "extensions.partialClone", "authored")
        index = (self.repo / ".git/index").read_bytes()
        with self.assertRaises(UserError):
            self.capture()
        self.assertFalse((self.repo / ".git/FETCH_HEAD").exists())
        self.assertEqual((self.repo / ".git/index").read_bytes(), index)

    def test_strict_validation_checks_all_identities_and_detaches_caller_objects(self):
        snapshot = self.capture()
        detached = validate_snapshot(snapshot)
        snapshot["files"][0]["content"] = "caller mutation"
        self.assertEqual(detached["files"][0]["content"], "print('authored')\n")
        for mutate in (lambda value: value.update(extra=True), lambda value: value["repository"].update(commit="f" * 64),
                       lambda value: value["files"][0].update(gitBlob="f" * 40), lambda value: value["files"][0].update(sha256="f" * 64),
                       lambda value: value["files"][0].update(bytes=True), lambda value: value.update(snapshotId="0" * 64),
                       lambda value: value.update(dataPolicyFingerprint="0" * 64)):
            value = copy.deepcopy(detached); mutate(value)
            with self.subTest(value=value), self.assertRaises(UserError):
                validate_snapshot(value)

    def test_data_policy_label_and_empty_selection_cannot_be_defaulted(self):
        for policy in ({}, {**POLICY, "containsPersonalData": "false"}, {**POLICY, "permission": "unknown"}, {**POLICY, "extra": True}):
            with self.subTest(policy=policy), self.assertRaises(UserError):
                capture_repository(self.repo, "HEAD", ["source.py"], label="authored", data_policy=policy)
        for label in ("", "UPPER", "private/path", "a" * 65):
            with self.subTest(label=label), self.assertRaises(UserError):
                capture_repository(self.repo, "HEAD", ["source.py"], label=label, data_policy=POLICY)

    def test_bare_repositories_are_supported_and_nested_worktree_roots_are_rejected(self):
        bare = self.root / "bare.git"
        self.git("clone", "--quiet", "--bare", "--no-hardlinks", str(self.repo), str(bare))
        self.assertEqual(self.capture(repo=bare)["files"][0]["content"], "print('authored')\n")
        (self.repo / "nested").mkdir()
        with self.assertRaisesRegex(UserError, "repository_root_required"):
            self.capture(repo=self.repo / "nested")

    def test_owned_git_deadline_kills_and_reaps_only_its_process(self):
        stub = self.root / "owned-git"
        pidfile = self.root / "owned.pid"
        stub.write_text(f"#!{sys.executable}\nimport os,time\nfrom pathlib import Path\nPath({str(pidfile)!r}).write_text(str(os.getpid()))\ntime.sleep(2)\n")
        stub.chmod(0o700)
        started = time.monotonic()
        with patch("personal_evals.repository.shutil.which", return_value=str(stub)), patch("personal_evals.repository.GIT_DEADLINE_SECONDS", 0.2):
            with self.assertRaisesRegex(UserError, "repository_git_timeout"):
                _git(self.repo, ["rev-parse", "HEAD"], 4096)
        self.assertLess(time.monotonic() - started, 1.5)
        with self.assertRaises(ProcessLookupError):
            os.kill(int(pidfile.read_text()), 0)

    def test_process_output_is_bounded_and_raw_stderr_never_enters_errors(self):
        stub = self.root / "owned-output-git"
        for stream in ("stdout", "stderr"):
            stub.write_text(f"#!{sys.executable}\nimport sys\nsys.{stream}.write('raw-secret-'*10000)\nsys.{stream}.flush()\n")
            stub.chmod(0o700)
            with self.subTest(stream=stream), patch("personal_evals.repository.shutil.which", return_value=str(stub)):
                with self.assertRaises(UserError) as caught:
                    _git(self.repo, ["rev-parse", "HEAD"], 8)
                self.assertEqual(caught.exception.code, "repository_git_output_too_large")
                self.assertNotIn("raw-secret", str(caught.exception))
