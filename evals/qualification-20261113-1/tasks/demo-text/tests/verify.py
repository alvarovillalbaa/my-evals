"""Deterministic grader for the explicitly labelled, authored format example."""

from pathlib import Path

try:
    correct = Path("/app/output.txt").read_bytes() == b"portable\n"
except OSError:
    correct = False
Path("/logs/verifier/reward.txt").write_text("1\n" if correct else "0\n", encoding="utf-8")
