"""Local artifact commands. No implicit network, process, provider or task run."""

import argparse
from pathlib import Path
import shlex
import sys

from .archive import write_archive
from .comparison import compare_runs
from .errors import UserError
from .harbor import import_job
from .jsonio import MAX_REPORT_BYTES, canonical, read_json, write_json
from .planning import build_plan, render_command
from .suite import prepare_suite, verify_bundle, write_bundle


class Parser(argparse.ArgumentParser):
    def error(self, _message):
        raise UserError("arguments_invalid")


def parser():
    root = Parser(prog="personal-evals", description="Seal personal Harbor tasks and compare imported evidence locally.")
    commands = root.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="Validate an explicit suite without writing or running tasks")
    validate.add_argument("suite", type=Path)
    bundle = commands.add_parser("bundle", help="Create an exclusive portable task bundle")
    bundle.add_argument("suite", type=Path)
    bundle.add_argument("--out", required=True, type=Path)
    for name in ("verify", "archive", "plan", "command", "import", "compare"):
        command = commands.add_parser(name)
        command.add_argument("bundle", type=Path)
        if name in ("archive", "plan", "import", "compare"):
            command.add_argument("--out", required=True, type=Path)
        if name == "plan":
            command.add_argument("--model", required=True)
            command.add_argument("--agent", required=True)
            command.add_argument("--agent-version", required=True)
            command.add_argument("--attempts", required=True, type=int)
        if name in ("command", "import"):
            command.add_argument("--plan", required=True, type=Path)
        if name == "command":
            command.add_argument("--jobs", required=True, type=Path)
            command.add_argument("--job-name", required=True)
        if name == "import":
            command.add_argument("--job", required=True, type=Path)
        if name == "compare":
            command.add_argument("--baseline", required=True, type=Path)
            command.add_argument("--candidate", required=True, type=Path)
    return root


def main(argv=None):
    try:
        args = parser().parse_args(argv)
        if args.command == "validate":
            manifest, _files = prepare_suite(args.suite)
            result = {"bundleId": manifest["bundleId"], "tasks": len(manifest["tasks"]), "writes": False}
        elif args.command == "bundle":
            manifest = write_bundle(args.suite, args.out)
            result = {"bundleId": manifest["bundleId"], "tasks": len(manifest["tasks"])}
        else:
            manifest = verify_bundle(args.bundle)
            if args.command == "verify":
                result = {"bundleId": manifest["bundleId"], "tasks": len(manifest["tasks"]), "verified": True}
            elif args.command == "archive":
                result = write_archive(args.bundle, args.out)
            elif args.command == "plan":
                result = build_plan(manifest, model=args.model, agent=args.agent, agent_version=args.agent_version, attempts=args.attempts)
                write_json(args.out, result)
            elif args.command == "command":
                command = render_command(read_json(args.plan), manifest, bundle=args.bundle, jobs=args.jobs, job_name=args.job_name)
                result = {"argv": command, "shell": shlex.join(command), "executes": False}
            elif args.command == "import":
                result = import_job(args.bundle, read_json(args.plan), args.job)
                write_json(args.out, result)
                result = {"runId": result["runId"], "model": result["model"], "trials": len(result["trials"])}
            else:
                result = compare_runs(manifest, read_json(args.baseline, MAX_REPORT_BYTES), read_json(args.candidate, MAX_REPORT_BYTES))
                write_json(args.out, result)
                result = {key: result[key] for key in ("reportId", "meanEffect", "interval", "decision")}
        print(canonical(result).decode("utf-8"))
        return 0
    except UserError as error:
        print(f"error: {error.code}", file=sys.stderr)
        return 2
    except (OSError, ValueError, RecursionError):
        print("error: local_operation_failed", file=sys.stderr)
        return 2
