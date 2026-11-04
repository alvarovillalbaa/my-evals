"""Syntax, relative imports, local documentation links and authored case counts."""

import ast
import json
from pathlib import Path
import re
import sys
import tomllib
from urllib.parse import unquote

root = Path(__file__).resolve().parents[1]
files = sorted(path for directory in ("personal_evals", "tests", "scripts", "examples") for path in (root / directory).rglob("*.py"))
proposed = sorted([*(root / "docs/proposals").glob("*.py.proposed"), *(root / "tests").rglob("*.py.proposed")])
active_cases, historical_cases = {}, {}
for path in [*files, *proposed]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    if path.name.startswith("test_"):
        declarations = historical_cases if path.name.endswith(".proposed") else active_cases
        declarations[str(path.relative_to(root))] = sum(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_") for node in ast.walk(tree))
    if path.parent == root / "personal_evals":
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module:
                target = path.parent.joinpath(*node.module.split("."))
                if not target.with_suffix(".py").is_file() and not (target / "__init__.py").is_file():
                    raise SystemExit("unresolved_relative_import")
links = 0
for path in [root / "README.md", root / "AGENTS.md", *(root / "docs").rglob("*.md")]:
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise SystemExit("empty_required_document")
    for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
        target = target.split(" ", 1)[0].strip("<>")
        if target.startswith(("https:", "http:", "mailto:", "#")):
            continue
        if not (path.parent / unquote(target.split("#", 1)[0])).exists():
            raise SystemExit(f"broken_local_link:{path.name}")
        links += 1
for path in (root / "examples").rglob("*.json"):
    json.loads(path.read_text(encoding="utf-8"))
tomllib.loads((root / "examples/demo-text/task.toml").read_text(encoding="utf-8"))
print(json.dumps({"pythonVersion": sys.version.split()[0], "pythonExecutable": sys.executable, "modulesParsed": len(files),
                  "historicalProposalsParsed": len(proposed),
                  "localMarkdownLinks": links, "activeCaseDeclarations": active_cases,
                  "historicalProposedCaseDeclarations": historical_cases,
                  "activeCaseDeclarationCount": sum(active_cases.values()),
                  "historicalProposedCaseDeclarationCount": sum(historical_cases.values()),
                  "caseCountMeaning": "AST declarations only; historical copies overlap active source. No execution-status or unique-coverage claim.",
                  "execution": "syntax and references only; no product import or test executed"}))
