"""T2 real subprocess boundary with an owned Python fake gh; never real GitHub."""

import json
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from personal_evals import github_delivery as publisher


class GitHubTransportTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="personal-evals-fake-gh-")).resolve()
        info = self.root.lstat()
        self.identity = (info.st_dev, info.st_ino)
        self.nonce = uuid4().hex
        (self.root / "owner").write_text(self.nonce, encoding="ascii")
        self.processes = []
        self.addCleanup(self.cleanup_owned)
        self.bin = self.root / "bin"
        self.home, self.config, self.xdg = (self.root / name for name in ("home", "gh-config", "xdg"))
        for directory in (self.bin, self.home, self.config, self.xdg):
            directory.mkdir(mode=0o700)
        self.settings, self.trace = self.root / "response.json", self.root / "trace.jsonl"
        self.fake = self.bin / "gh"
        source = f"#!{sys.executable} -BS\n" + """import json, os, sys, time
from pathlib import Path
settings = json.loads(Path(SETTINGS).read_text())
body = sys.stdin.buffer.read()
record = {'argv': sys.argv[1:], 'stdin': body.decode('utf-8'),
          'home': os.environ.get('HOME'), 'config': os.environ.get('GH_CONFIG_DIR'),
          'xdg': os.environ.get('XDG_CONFIG_HOME'), 'keys': sorted(os.environ),
          'bytecodeDisabled': sys.dont_write_bytecode, 'siteDisabled': sys.flags.no_site}
descriptor = os.open(TRACE, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
with os.fdopen(descriptor, 'w') as stream:
    stream.write(json.dumps(record) + '\\n')
mode = settings['mode']
if mode == 'deadline':
    time.sleep(10)
elif mode == 'overflow':
    sys.stderr.write('AUTHORED_RAW_SECRET_' * 2000)
    sys.stderr.flush()
    time.sleep(10)
else:
    if mode == 'denied':
        header = b'HTTP/2.0 403 Forbidden\\r\\nContent-Type: application/json\\r\\n\\r\\n'
        data = b'{"message":"AUTHORED_RAW_SECRET"}'
        sys.stderr.write('AUTHORED_RAW_SECRET diagnostic that must not escape')
    else:
        header = b'HTTP/2.0 200 OK\\r\\nContent-Type: application/json\\r\\n\\r\\n'
        data = b'not-json' if mode == 'malformed' else json.dumps(settings['body']).encode()
    for part in (header[:8], header[8:], data[:4], data[4:]):
        sys.stdout.buffer.write(part)
        sys.stdout.buffer.flush()
    raise SystemExit(1 if mode == 'denied' else 0)
"""
        source = source.replace("SETTINGS", repr(str(self.settings))).replace("TRACE", repr(str(self.trace)))
        self.fake.write_text(source, encoding="utf-8")
        self.fake.chmod(0o700)
        self.env = {"PATH": str(self.bin), "HOME": str(self.home),
                    "GH_CONFIG_DIR": str(self.config), "XDG_CONFIG_HOME": str(self.xdg)}

    def cleanup_owned(self):
        for process in self.processes:
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=3)
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None and not stream.closed:
                    stream.close()
        info = self.root.lstat()
        marker = self.root / "owner"
        self.assertTrue(stat.S_ISDIR(info.st_mode))
        self.assertEqual((info.st_dev, info.st_ino), self.identity)
        self.assertTrue(marker.is_file() and not marker.is_symlink())
        self.assertEqual(marker.read_text(encoding="ascii"), self.nonce)
        shutil.rmtree(self.root)

    def response(self, mode, body=None):
        self.settings.write_text(json.dumps({"mode": mode, "body": body}), encoding="utf-8")

    def request(self, method, path, body=None):
        original = subprocess.Popen

        def observe(argv, *args, **kwargs):
            self.assertEqual(Path(argv[0]), self.fake)
            self.assertIs(kwargs.get("start_new_session"), True)
            process = original(argv, *args, **kwargs)
            self.processes.append(process)
            return process

        with patch.dict(os.environ, self.env, clear=True), \
                patch.object(publisher.subprocess, "Popen", side_effect=observe):
            self.assertEqual(Path(shutil.which("gh")), self.fake)
            return publisher.GhApi().request(method, path, body)

    def records(self):
        return [json.loads(line) for line in self.trace.read_text(encoding="utf-8").splitlines()]

    def assert_owned_processes_gone(self):
        self.assertTrue(self.processes)
        for process in self.processes:
            self.assertIsNotNone(process.poll())
            with self.assertRaises(ProcessLookupError):
                os.kill(process.pid, 0)
            with self.assertRaises(ProcessLookupError):
                os.killpg(process.pid, 0)

    def test_owned_fake_gh_frames_get_and_post_with_isolated_configuration(self):
        self.assertEqual(publisher.REQUEST_DEADLINE_SECONDS, 30)
        self.response("success", {"id": 202, "login": "authored-owner"})
        self.assertEqual(self.request("GET", "/user"), {"id": 202, "login": "authored-owner"})
        payload = {"encoding": "base64", "content": "AAH/"}
        self.response("success", {"sha": "1" * 40})
        self.assertEqual(self.request("POST", "/repos/authored-owner/authored-repo/git/blobs", payload),
                         {"sha": "1" * 40})
        get, post = self.records()
        self.assertEqual(get["stdin"], "")
        self.assertEqual(post["stdin"], '{"content":"AAH/","encoding":"base64"}')
        for record, method, endpoint in ((get, "GET", "/user"),
                                         (post, "POST", "/repos/authored-owner/authored-repo/git/blobs")):
            argv = record["argv"]
            self.assertEqual(argv[0], "api")
            self.assertEqual(argv[argv.index("--hostname") + 1], "github.com")
            self.assertEqual(argv[argv.index("--method") + 1], method)
            self.assertIn("--include", argv)
            self.assertIn("Accept: application/vnd.github+json", argv)
            self.assertIn("X-GitHub-Api-Version: 2026-03-10", argv)
            self.assertEqual(argv[-1], "https://api.github.com" + endpoint)
            self.assertEqual(record["home"], str(self.home))
            self.assertEqual(record["config"], str(self.config))
            self.assertEqual(record["xdg"], str(self.xdg))
            self.assertTrue(record["bytecodeDisabled"])
            self.assertEqual(record["siteDisabled"], 1)
            self.assertFalse({"GH_TOKEN", "GITHUB_TOKEN", "GH_DEBUG"} & set(record["keys"]))
        self.assertEqual(post["argv"][post["argv"].index("--input") + 1], "-")
        self.assertNotIn("--input", get["argv"])
        self.assert_owned_processes_gone()

    def test_http_and_malformed_json_errors_are_finite_without_stderr_leak_or_retry(self):
        for mode, code, status in (("denied", "github_http_error", 403),
                                   ("malformed", "github_protocol_invalid", 0)):
            with self.subTest(response=mode):
                self.response(mode)
                before = len(self.processes)
                with self.assertRaises(publisher.GitHubError) as rejected:
                    self.request("GET", "/user")
                self.assertEqual(rejected.exception.code, code)
                self.assertEqual(rejected.exception.status, status)
                self.assertNotIn("AUTHORED_RAW_SECRET", str(rejected.exception))
                self.assertNotIn(str(self.root), str(rejected.exception))
                self.assertEqual(len(self.processes), before + 1)
        self.assertEqual(len(self.records()), 2)
        self.assert_owned_processes_gone()

    def test_output_limit_kills_and_reaps_the_real_owned_transport(self):
        self.response("overflow")
        with self.assertRaises(publisher.GitHubError) as rejected:
            self.request("GET", "/user")
        self.assertEqual(rejected.exception.code, "github_output_too_large")
        self.assertNotIn("AUTHORED_RAW_SECRET", str(rejected.exception))
        self.assertEqual(len(self.processes), 1)
        self.assert_owned_processes_gone()

    def test_small_deadline_kills_and_reaps_observed_child_without_pid_file(self):
        self.assertEqual(publisher.REQUEST_DEADLINE_SECONDS, 30)
        self.response("deadline")
        with patch.object(publisher, "REQUEST_DEADLINE_SECONDS", 0.2):
            with self.assertRaises(publisher.GitHubError) as rejected:
                self.request("GET", "/user")
        self.assertEqual(rejected.exception.code, "github_timeout")
        self.assertEqual(publisher.REQUEST_DEADLINE_SECONDS, 30)
        self.assertEqual(len(self.processes), 1)
        self.assert_owned_processes_gone()
