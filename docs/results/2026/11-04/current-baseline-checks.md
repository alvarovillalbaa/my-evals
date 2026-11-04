# Current-source baseline — 127 passed, one error

4 November 2026. One invocation ran exactly **128 cases** at current source
`d2c177131ae79ea02443eddfeb1ecdc726d06271`: **127 passed, one error, zero failures/skips**.
Child exit was **1**; the supervisor completed cleanup and exited 0. This is a
failed baseline, not a passing result. The [JSON receipt](current-baseline-checks.json)
retains all 128 actual IDs/statuses, full bounded output projections, original
stream hashes and 43 current source fingerprints.

| Module | Passed / observed |
| --- | ---: |
| `test_suite` | 20/20 |
| `test_harbor` | 20/20 |
| `test_comparison` | 20/20 |
| `test_local` | 16/16 |
| `test_repository` | 19/20; one error |
| `test_generation` | 20/20 |
| `test_generation_cli` | 12/12 |

The error is `RepositoryTests.test_owned_git_deadline_kills_and_reaps_only_its_process`.
After the expected `repository_git_timeout`, its PID assertion at
`tests/unit/test_repository.py:256` tried to read `owned.pid`; that file was absent,
raising `FileNotFoundError`. The fixture's 0.2-second deadline begins before the
stub acknowledges startup. The reason no PID acknowledgement was recorded is
**unproven**; this is not evidence that the platform or process cleanup is
unavailable. No repair, deadline change or rerun was performed.

Actual runtime was **CPython 3.14.7 / Git 2.55.0 on macOS**. Unittest reported
**87.776 seconds**; supervised child duration was **90.541 seconds**. The
120-second cap and 128 KiB per-stream caps were not reached. Stdout was empty;
stderr was **24,935 bytes**, SHA-256
`3c00b1fe0b400fd96c98c688b7c630288ed202097aa91a38e077a97b212d343e`. Exact original hashes are retained; committed text replaces
only absolute repository/runtime/owned-temp prefixes with portable markers.

All **43 current input bytes/modes** and HEAD passed pre/post guards. The child
was reaped, its original process group was gone, no fixture directories remained,
and the identity-checked parent root was deleted. This is not an independent
inventory of separately sessioned Git descendants, and the failing case did not
complete its PID assertion. No timeout, interruption, forced supervisor kill or
output truncation occurred.

This was a **new current-source scope**. All seven fixture files are unchanged,
but the initial76 seal has **21/23** unchanged entries and the repository52 seal
**28/30**; both differ in `personal_evals/cli.py` and `scripts/check.py`. The old76
runtime closure grows from 15 to 18 files through the changed CLI (adding delivery,
generation and repository); old52 grows from 16 to 17 (adding delivery). The
combined current static closure has 21 files. Neither old pinned commit was run,
and both historical seals remain intact.

The [separately passed offline20 packet](delivery-plan-checks.md), inactive24
publisher cases and publisher activation were excluded. All real Git activity
was confined to tiny authored local repositories. No live account, remote Git,
provider/model, Harbor/container/task, install, CI, server/browser or database
action occurred. Only these two result files were written; the first failure is
preserved for review before further work.
