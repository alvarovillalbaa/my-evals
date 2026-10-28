# Personal Evals

Portable personal evaluations for deciding whether a new model or provider works
better on your own tasks, using the real Harbor framework.

**Initial local CLI source.** This implementation seals selected task files,
exports a downloadable bundle, prepares Harbor commands and imports/compares
result evidence. No Harbor/container/model execution has been performed for
this delivery. Provider/repository-driven generation and PR delivery remain
unfinished requirements in the [owning brief](docs/spec.md).

Python 3.12+ on macOS/Linux; the local artifact tools use only the standard
library. No package installation, server, database or web hosting is required.
Harbor and its container/agent dependencies are separate: this tool does not
install, replace or silently execute them.

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
executing tests, tasks, Harbor or Docker. The [focused check proposal](docs/proposals/local-checks.md)
keeps the authored unit cases separate from real framework/provider acceptance.
The [delivery receipt](docs/results/2026/10-28/initial-source.md) records actual
checks, publication and proof limits.

- `personal_evals/suite.py`: explicit selection, task/manifest identity and bundle verification.
- `personal_evals/planning.py`, `harbor.py`: real framework plans and provenance-bound imports.
- `personal_evals/comparison.py`: paired evidence and inconclusive decisions.
- `personal_evals/archive.py`, `jsonio.py`, `cli.py`: portable output and local commands.
- `tests/unit/`: authored T2 fixtures only, pending execution approval.

MIT licensed. The full product remains active until its required integrations
and approved real-run acceptance are complete.
