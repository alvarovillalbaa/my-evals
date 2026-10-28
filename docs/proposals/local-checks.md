# Proposed focused local checks

Date: 2026-10-28. Status: **76 authored cases; execution approval pending**.
This document records a concrete source-level scope, not a passing result or
permission to install/run Harbor, execute tasks or call a model/provider.

## Exact command

Use the existing Python 3.12+ installation, from this repository:

```sh
python3 -m unittest -v tests.unit.test_suite tests.unit.test_harbor tests.unit.test_comparison tests.unit.test_local
```

The source contains exactly **20 suite + 20 Harbor-import + 20 comparison +
16 local artifact/CLI cases = 76**. They import actual product modules and use
Python's standard unittest/tempfile/mock facilities. No dependency installation,
server, browser, database, framework/container/agent launch, model/provider call,
account connection, GitHub mutation, CI job or paid service is involved.

All inputs are T2 authored fixtures: local task files, fake Harbor job/result/lock
records, invented model identities, numbers and UUIDs. No personal task corpus,
private repository, real credentials or actual model output is read. Only owned
temporary directories/files are created and removed by their test cleanup.
Tests are sequential. The largest per-file boundary fixture is about 2 MiB;
the aggregate-size case lowers its configured limit and uses real small files,
instead of creating a 32 MiB corpus. Source review bounds fixture storage to
less than 5 MiB at a time. No new environment or large checkout is created.

## Behavior covered

| File | Cases | Focus |
| --- | --- | --- |
| [test_suite.py](../../tests/unit/test_suite.py) | 20 | Explicit selection/order, strict suite fields, data/task/file identities, pinned task profile/digest, path/link/secret/ignored-file fences, size boundaries, exact inventory, private exclusive writes and owned cleanup |
| [test_harbor.py](../../tests/unit/test_harbor.py) | 20 | Actual pinned result/lock shapes, job/task/model/agent bindings, missing/mismatched provenance, workload overrides, step/trial errors, nullable usage/timing, safe projections, duplicate/invalid/oversized/link inputs |
| [test_comparison.py](../../tests/unit/test_comparison.py) | 20 | Identity/protocol validation, task-ID pairing, complete attempts, missing/excluded/extra/duplicate evidence, practical improvement, critical regressions, uncertainty/inconclusive decisions and unknown metrics |
| [test_local.py](../../tests/unit/test_local.py) | 16 | Strict bounded JSON, no-overwrite/private outputs, model versus protocol identity, admitted framework agent versions, real command argv rendering without execution, archive transfer/tamper/reproducibility, CLI no-write/error behavior and no invented tasks |

Expected discovery is 76 cases. Record actual pass/fail/error/skip totals, source
commit and product/test SHA256 values, runtime version and executable attribution
from the same repository process, exact command, exit code and raw output hash
under `docs/results/2026/10-28/`. Do not broaden the scope or disguise a failure
by removing a case, changing its contract, adding a retry or running live inputs.
Preserve failures and any required corrections with their evidence.

These cases do not establish real Harbor compatibility, successful Docker builds,
agent/provider authentication, live model execution or cost, representative
personal benchmark quality, calibrated graders, trustworthy external evidence,
actual provider switching, remote repository generation or PR delivery. Those
remain separate product and execution requirements in the [owning brief](../spec.md).
Workspace/AGENTS.md §7 requires explicit approval before executing this new
domain scope. Static AST/import/link/whitespace checks do not execute it.
