# Personal Evals

Portable personal evaluations for deciding whether a new model or provider works
better on your own tasks, using the real Harbor framework.

**Local CLI source.** This implementation captures explicitly selected committed
repository files, prepares a generation handoff, validates supplied tasks for
owner review, seals portable task bundles and imports/compares Harbor evidence.
No provider is called by the handoff commands. Live provider integration and PR
delivery remain unfinished requirements in the [owning brief](docs/spec.md).

Python 3.12+ on macOS/Linux; the local artifact tools use only the standard
library; repository capture also uses the existing Git executable. No package
installation, server, database or web hosting is required.
Harbor and its container/agent dependencies are separate: this tool does not
install, replace or silently execute them.

## Build tasks from selected repository source

The [repository generation workflow](docs/references/generation.md) captures an
explicit revision and file selection, freezes source/task/grader metadata into a
request, imports a supplied response as a review-required draft, and seals it
only through explicit owner acceptance. Working-tree changes are preserved;
source capture reads the selected committed bytes. No remote connection, model
call, credential lookup or PR creation is implicit.

The request is a provider-neutral local interchange artifact. It does not claim
native provider integration, authentic provider output or semantically correct
graders. Generated files remain subject to owner review and real execution
acceptance. This is progress on the repository path, not a completed live
generation service.

## Own the task population

Write a suite file with explicit task directories and file lists. Declare its
data policy, validation/holdout role, reward metric, success thresholds and the
model-switch decision **before** collecting results. Only selected files enter
the portable artifact. No repository scan or example benchmark is loaded for you.

[examples/suite.json](examples/suite.json) is an authored format demonstration,
with one deliberately trivial task. It cannot meet its ten-task comparison
requirement and is not evidence for choosing a model. Replace it with your own
representative, authorized tasks; the [format reference](docs/references/formats.md)
describes the contract.

```sh
mkdir -p artifacts
python3 -m personal_evals validate path/to/suite.json
python3 -m personal_evals bundle path/to/suite.json --out artifacts/my-suite
python3 -m personal_evals verify artifacts/my-suite
python3 -m personal_evals archive artifacts/my-suite --out artifacts/my-suite.zip
```

Output parents must already exist. Outputs refuse overwrites; bundles and JSON
files are private local artifacts. Keep private task bundles out of public Git
repositories. A bundle includes exact task files and graders; its manifest
preserves order, stable task IDs, versions, file hashes and the policy fingerprint.
Transferring and verifying it does not execute its code.

## Plan and import real Harbor evidence

Create one plan per model with identical agent, agent version, suite and attempts:

```sh
python3 -m personal_evals plan artifacts/my-suite \
  --agent terminus-2 --agent-version 2.0.0 \
  --model PROVIDER/BASELINE_MODEL --attempts 3 --out artifacts/baseline-plan.json
python3 -m personal_evals plan artifacts/my-suite \
  --agent terminus-2 --agent-version 2.0.0 \
  --model PROVIDER/CANDIDATE_MODEL --attempts 3 --out artifacts/candidate-plan.json
python3 -m personal_evals command artifacts/my-suite \
  --plan artifacts/baseline-plan.json --jobs artifacts/jobs --job-name baseline
```

`command` returns an argument array and a shell-quoted rendering. **It does not
run the command.** Review the selected framework, task code, credentials,
container setup and execution cost separately before running Harbor. No budget
enforcement, dependency installation or provider authorization is implied by a
plan. Model names above are placeholders; no provider/model is selected for you.
The admitted agents are Harbor's provider-neutral `terminus-2` at its pinned
`2.0.0` implementation and `codex` with an explicit numeric release version
(the `MAJOR.MINOR.PATCH` form, with optional prerelease). Mutable tags
such as `latest` cannot establish a frozen comparison protocol.
The latter renders Harbor's version kwarg; the former is bound by the Harbor
source commit. Other/custom agent implementations are not silently admitted.

The supported Harbor source profile is pinned in the
[framework contract](docs/references/harbor.md). An unsupported version or override
cannot be silently imported as an equivalent run. After separately authorized
real runs, import their job directories:

```sh
python3 -m personal_evals import artifacts/my-suite \
  --plan artifacts/baseline-plan.json --job artifacts/jobs/baseline --out artifacts/baseline.json
python3 -m personal_evals import artifacts/my-suite \
  --plan artifacts/candidate-plan.json --job artifacts/jobs/candidate --out artifacts/candidate.json
python3 -m personal_evals compare artifacts/my-suite \
  --baseline artifacts/baseline.json --candidate artifacts/candidate.json --out artifacts/comparison.json
```

Comparison joins by stable task ID, checks suite/protocol identities and reports
coverage, errors, paired task effects, uncertainty and critical regressions.
Missing/errored results stay missing/errored. Unknown cost or latency stays null.
Insufficient or incompatible evidence cannot recommend a switch. A supported
candidate is a bounded personal decision signal, not automatic model promotion
or a population-wide performance claim. Local hashes preserve supplied evidence;
they do not authenticate a provider or attest that a submitted file is truthful.

## Verification and files

```sh
python3 scripts/check.py
git diff --check
```

This parses source and checks references without importing product modules or
executing tests, tasks, Harbor or Docker. The [initial check proposal](docs/proposals/local-checks.md)
keeps its 76 authored cases pinned to the initial source; it does not authorize
the subsequent repository/generation scope. Both remain separate from real
framework/provider acceptance. The [repository/generation proposal](docs/proposals/repository-generation-checks.md)
separately scopes its 52 new authored cases, which are also unexecuted.
The [initial receipt](docs/results/2026/10-28/initial-source.md) and
[repository handoff receipt](docs/results/2026/10-28/repository-generation.md)
record actual checks, publication and proof limits.

- `personal_evals/suite.py`: explicit selection, task/manifest identity and bundle verification.
- `personal_evals/repository.py`, `generation.py`: committed source capture, generation handoff and explicit draft review.
- `personal_evals/planning.py`, `harbor.py`: real framework plans and provenance-bound imports.
- `personal_evals/comparison.py`: paired evidence and inconclusive decisions.
- `personal_evals/archive.py`, `jsonio.py`, `cli.py`: portable output and local commands.
- `tests/unit/`: authored T2 fixtures only, pending execution approval.

MIT licensed. The full product remains active until its required integrations
and approved real-run acceptance are complete.
