# Proposed repository and generation checks

Last updated: 2026-10-28

Status: **52 authored cases; execution approval pending**. This is a new scope,
separate from the [initial 76-case request](local-checks.md) frozen at
`1081ca8c3aca64ea02e0818b8e27fbd855bb7e2c`. Neither request authorizes the other,
a broad discovery run, provider execution or PR submission.

## Exact proposed command

Use the existing Python 3.12+ and Git installations from this repository:

```sh
python3 -m unittest -v tests.unit.test_repository tests.unit.test_generation tests.unit.test_generation_cli
```

The three files contain exactly **20 repository + 20 generation + 12 CLI cases
= 52**. They import actual source. Native Git runs only against tiny owned
disposable repositories; all other inputs are authored JSON/text/TOML fixtures.
No existing user repository, personal task corpus, real provider response,
credential, Harbor job or account is used. Fixtures are T2 authored data.

| File | Cases | Proposed evidence |
| --- | --- | --- |
| [test_repository.py](../../tests/unit/test_repository.py) | 20 | Committed bytes/OID/content hashes, explicit selection/order, preserved dirty worktree/index, old revision, literal and benign config paths, credential/traversal/link/gitlink/size fences, SHA-256 objects, bare/local missing objects, replacement/config isolation and bounded subprocess cleanup |
| [test_generation.py](../../tests/unit/test_generation.py) | 20 | Complete request/source/owner identities, policy and grading metadata, multiline goals, by-ID supplied responses, missing/blank/invalid files, exact task identity, review-required private outputs, no overwrites/owned cleanup, tampering and explicit acceptance of captured reviewed bytes |
| [test_generation_cli.py](../../tests/unit/test_generation_cli.py) | 12 | Actual snapshot/request/import/accept CLI flow on authored committed source, dirty/unselected preservation, no provider transmission, stable bytes/IDs, declared response binding, owner review gate, missing graders, no-overwrite behavior, finite errors and no task/provider/PR subprocess |

Repository fixtures create and remove only their own temporary directories.
One test makes a local bare clone of its own tiny fixture; it does not clone or
fetch any external repository. Process fixtures are bounded and owned. File-size
cases use small authored files or lowered configured limits; no environment,
large worktree, dependency tree or database is installed/provisioned. Use
`PYTHONDONTWRITEBYTECODE=1` for the process to avoid bytecode residue.

Record actual test/error/failure/skip totals, command, source commit and
fingerprints, Python/Git versions, same-process runtime attribution, exit code
and exact output hash in the owning results folder. Expected discovery is 52;
report actual failures and corrections. Do not add a retry or broaden the run
without a source-backed reason and applicable approval.

No browser, server, database, CI job, provider/model call, Harbor/container/agent
or verifier launch, remote Git operation, Auth configuration, PR submission or
paid service is proposed. Future live provider generation, task quality, license/
privacy suitability, authentic provider identity, real Harbor compatibility,
calibrated personal evals and repository PR delivery are not proved by these
fixtures. The original 76 cases remain unexecuted under their own pending scope.

The supplied AGENTS.md §7 requires explicit approval before this new domain run.
AST/reference/whitespace checks performed during source preparation execute none
of these cases.
