"""T2: explicitly authored files and values; no network, model or container."""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import shlex
import shutil
import stat
import tempfile
import unittest
from zipfile import ZipFile

from personal_evals.archive import write_archive
from personal_evals.cli import main
from personal_evals.errors import UserError
from personal_evals.jsonio import parse_json, read_bytes, write_json
from personal_evals.planning import build_plan, render_command, validate_plan
from personal_evals.suite import prepare_suite, verify_bundle, write_bundle


class LocalArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="personal-evals-authored-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "explicit source"
        shutil.copytree(Path(__file__).resolve().parents[2] / "examples", self.source)
        self.suite = self.source / "suite.json"

    def bundle(self):
        destination = self.root / "portable bundle"
        manifest = write_bundle(self.suite, destination)
        return destination, manifest

    def plan(self, manifest, **changes):
        values = {"model": "authored/baseline", "agent": "codex", "agent_version": "1.2.3", "attempts": 2} | changes
        return build_plan(manifest, **values)

    def test_duplicate_json_keys_are_rejected(self):
        with self.assertRaises(UserError):
            parse_json(b'{"schemaVersion":1,"schemaVersion":2}')

    def test_nonfinite_and_invalid_unicode_are_rejected(self):
        for value in (b'{"value":NaN}', b'{"value":1e999}', b'{"value":"\\ud800"}', b'\xff'):
            with self.subTest(value=value), self.assertRaises(UserError):
                parse_json(value)

    def test_link_and_oversized_regular_inputs_are_rejected(self):
        target = self.root / "target"
        target.write_bytes(b"authored")
        link = self.root / "link"
        link.symlink_to(target)
        with self.assertRaises(UserError):
            read_bytes(link)
        with self.assertRaises(UserError):
            read_bytes(target, 2)

    def test_json_publication_is_private_complete_and_refuses_overwrite(self):
        target = self.root / "receipt.json"
        write_json(target, {"owned": True})
        original = target.read_bytes()
        self.assertEqual(json.loads(original), {"owned": True})
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
        with self.assertRaises(UserError):
            write_json(target, {"replacement": True})
        self.assertEqual(target.read_bytes(), original)
        self.assertFalse(list(self.root.glob(".personal-evals-*")))

    def test_model_change_preserves_protocol_but_changes_plan_identity(self):
        _bundle, manifest = self.bundle()
        first = self.plan(manifest)
        second = self.plan(manifest, model="authored/candidate")
        self.assertEqual(first["protocolId"], second["protocolId"])
        self.assertNotEqual(first["planId"], second["planId"])
        self.assertNotIn(str(self.root), json.dumps(first))

    def test_agent_version_and_attempts_are_part_of_protocol(self):
        _bundle, manifest = self.bundle()
        first = self.plan(manifest)
        for changes in ({"agent_version": "1.2.4"}, {"attempts": 3}):
            self.assertNotEqual(first["protocolId"], self.plan(manifest, **changes)["protocolId"])

    def test_provider_neutral_terminus_uses_its_pinned_framework_version(self):
        bundle, manifest = self.bundle()
        plan = self.plan(manifest, agent="terminus-2", agent_version="2.0.0", model="anthropic/authored-model")
        command = render_command(plan, manifest, bundle=bundle, jobs=self.root / "jobs", job_name="authored")
        self.assertNotIn("--agent-kwarg", command)
        for values in ({"agent": "unknown"}, {"agent": "terminus-2", "agent_version": "3.0.0"}):
            with self.assertRaises(UserError):
                self.plan(manifest, **values)

    def test_edited_plan_or_wrong_bundle_cannot_reuse_identity(self):
        _bundle, manifest = self.bundle()
        plan = self.plan(manifest)
        plan["model"] = "authored/changed"
        with self.assertRaises(UserError):
            validate_plan(plan, manifest)
        plan = self.plan(manifest)
        plan["bundleId"] = "0" * 64
        with self.assertRaises(UserError):
            validate_plan(plan, manifest)

    def test_boolean_attempts_and_ambiguous_model_are_rejected(self):
        _bundle, manifest = self.bundle()
        for changes in ({"attempts": True}, {"attempts": 0}, {"model": "ambiguous-name"}, {"model": "authored/value --extra"},
                        {"agent_version": "latest"}, {"agent_version": "beta"}, {"agent_version": "1"},
                        {"agent_version": "true"}, {"agent_version": "null"}):
            with self.subTest(changes=changes), self.assertRaises(UserError):
                self.plan(manifest, **changes)

    def test_real_harbor_command_is_an_argv_with_no_shell_execution(self):
        bundle, manifest = self.bundle()
        plan = self.plan(manifest)
        command = render_command(plan, manifest, bundle=bundle, jobs=self.root / "jobs with spaces", job_name="authored-job")
        self.assertEqual(command[:2], ["harbor", "run"])
        self.assertEqual(shlex.split(shlex.join(command)), command)
        self.assertEqual(command[command.index("--model") + 1], "authored/baseline")
        self.assertEqual(command[command.index("--max-retries") + 1], "0")
        self.assertEqual(command[command.index("--n-concurrent") + 1], "1")
        self.assertEqual(command[command.index("--agent-kwarg") + 1], 'version="1.2.3"')
        self.assertEqual(json.loads(command[command.index("--agent-kwarg") + 1].split("=", 1)[1]), "1.2.3")
        with self.assertRaises(UserError):
            render_command(plan, manifest, bundle=bundle, jobs=bundle / "jobs", job_name="authored-job")

    def test_archive_transfer_preserves_sealed_identity(self):
        bundle, manifest = self.bundle()
        target = self.root / "owned.zip"
        receipt = write_archive(bundle, target)
        transfer = self.root / "transferred"
        with ZipFile(target) as archive:
            self.assertTrue(all(not name.startswith("/") and ".." not in Path(name).parts for name in archive.namelist()))
            archive.extractall(transfer)
        self.assertEqual(verify_bundle(transfer)["bundleId"], manifest["bundleId"])
        self.assertEqual(receipt["bytes"], target.stat().st_size)

    def test_archive_is_deterministic_and_refuses_overwrite(self):
        bundle, _manifest = self.bundle()
        first, second = self.root / "first.zip", self.root / "second.zip"
        self.assertEqual(write_archive(bundle, first)["sha256"], write_archive(bundle, second)["sha256"])
        original = first.read_bytes()
        with self.assertRaises(UserError):
            write_archive(bundle, first)
        self.assertEqual(first.read_bytes(), original)

    def test_changed_task_cannot_be_archived_under_old_manifest(self):
        bundle, _manifest = self.bundle()
        (bundle / "tasks/demo-text/instruction.md").write_text("changed after sealing", encoding="utf-8")
        target = self.root / "changed.zip"
        with self.assertRaises(UserError):
            write_archive(bundle, target)
        self.assertFalse(target.exists())

    def test_validate_cli_has_no_writes_or_task_execution(self):
        before = sorted(str(path.relative_to(self.root)) for path in self.root.rglob("*"))
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["validate", str(self.suite)]), 0)
        self.assertFalse(json.loads(output.getvalue())["writes"])
        self.assertEqual(before, sorted(str(path.relative_to(self.root)) for path in self.root.rglob("*")))

    def test_cli_errors_do_not_echo_unknown_private_values(self):
        output = StringIO()
        with redirect_stderr(output):
            self.assertEqual(main(["--token", "authored-private-value"]), 2)
        self.assertEqual(output.getvalue(), "error: arguments_invalid\n")

    def test_empty_suite_does_not_invent_example_tasks(self):
        value = json.loads(self.suite.read_text())
        value["tasks"] = []
        self.suite.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(UserError):
            prepare_suite(self.suite)
