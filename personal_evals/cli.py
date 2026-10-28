"""Local artifacts and explicit committed Git reads; no provider or task run."""

import argparse
from pathlib import Path
import shlex
import sys

from .archive import write_archive
from .comparison import compare_runs
from .errors import UserError
from .generation import accept_draft, build_request, import_response
from .harbor import import_job
from .jsonio import MAX_REPORT_BYTES, canonical, read_json, write_json
from .planning import build_plan, render_command
from .repository import capture_repository
from .suite import prepare_suite, verify_bundle, write_bundle


class Parser(argparse.ArgumentParser):
    def error(self, _message):
        raise UserError("arguments_invalid")


def parser():
    root = Parser(prog="personal-evals", description="Seal personal Harbor tasks and compare imported evidence locally.")
    commands = root.add_subparsers(dest="command", required=True)
    snapshot = commands.add_parser("snapshot", help="Capture only explicitly selected committed repository files")
    snapshot.add_argument("--repo", required=True, type=Path)
    snapshot.add_argument("--revision", required=True)
    snapshot.add_argument("--file", required=True, action="append", dest="files")
    snapshot.add_argument("--label", required=True)
    snapshot.add_argument("--policy", required=True, type=Path)
    snapshot.add_argument("--out", required=True, type=Path)
    request = commands.add_parser("generation-request", help="Prepare a provider-neutral handoff without sending it")
    request.add_argument("snapshot", type=Path)
    request.add_argument("--intent", required=True, type=Path)
    request.add_argument("--out", required=True, type=Path)
    imported = commands.add_parser("generation-import", help="Validate supplied task files into a review-required draft")
    imported.add_argument("request", type=Path)
    imported.add_argument("--response", required=True, type=Path)
    imported.add_argument("--out", required=True, type=Path)
    accepted = commands.add_parser("generation-accept", help="Seal a draft only after explicit owner review")
    accepted.add_argument("draft", type=Path)
    accepted.add_argument("--reviewed", action="store_true")
    accepted.add_argument("--out", required=True, type=Path)
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
        if args.command == "snapshot":
            snapshot = capture_repository(args.repo, args.revision, args.files, label=args.label, data_policy=read_json(args.policy))
            write_json(args.out, snapshot)
            result = {"snapshotId": snapshot["snapshotId"], "commit": snapshot["repository"]["commit"], "files": len(snapshot["files"])}
        elif args.command == "generation-request":
            request = build_request(read_json(args.snapshot, MAX_REPORT_BYTES), read_json(args.intent))
            write_json(args.out, request)
            result = {"requestId": request["requestId"], "snapshotId": request["snapshot"]["snapshotId"], "tasks": len(request["tasks"]), "sent": False}
        elif args.command == "generation-import":
            review = import_response(read_json(args.request, MAX_REPORT_BYTES), args.response, args.out)
            result = {key: review[key] for key in ("reviewId", "requestId", "snapshotId", "status")}
        elif args.command == "generation-accept":
            result = accept_draft(args.draft, args.out, reviewed=args.reviewed)
        elif args.command == "validate":
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
