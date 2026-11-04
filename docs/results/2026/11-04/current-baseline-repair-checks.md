# Corrected owned-Git timeout case — passed

4 November 2026. **One case passed once**, exit **0**, at immutable source
`696d13cc8131d7a39c453f25e14f3de91387be40`. The [JSON receipt](current-baseline-repair-checks.json)
retains the exact case ID/status, complete raw bounded output, stream hashes,
51 source fingerprints and supervision evidence.

```text
tests.unit.test_repository.RepositoryTests.test_owned_git_deadline_kills_and_reaps_only_its_process
```

The selected case exercised the real `Popen` spy, required exactly one captured
process, the unchanged `repository_git_timeout` at a **0.2-second** product
deadline, the unchanged **1.5-second** elapsed assertion, a non-null
`-SIGKILL` return code and `ProcessLookupError` from its actual PID probe. The
PID came from the kernel-issued process object rather than a child-created
file. The stub PID and measured operation duration were not separately emitted.

Actual profile: **CPython 3.14.7 / Git 2.55.0 on macOS**. Unittest reported
**0.312 seconds**; supervised child duration was **0.579 seconds**. The child
ran with bytecode disabled, a fresh owned private temp root, a 120-second cap
and 128 KiB per-stream caps. Stdout was empty; stderr was 263 bytes, SHA-256
`c8353e660c77a1fa67ea2d91747a03afcdc31d51a83941a002438ab065d0e51f`. No supervisor timeout, interruption, forced kill or
truncation occurred. The fixture's deliberate stub SIGKILL remains distinct
from supervisor cleanup.

All **51 complete non-results inputs**, index paths/modes/blob IDs, working
bytes/hashes and [seal bytes](current-baseline-repair-source.json) matched before
and after. Pinned HEAD and the original failure receipt pair also remained
unchanged. The supervised child was reaped, its process group was gone, no
fixture children remained and the identity-checked parent root was removed.

**Remote main publication remains pending.** Parent verified the public
`696d13cc…` commit/tree objects and native checkout before this run, while the
last observed canonical `main` remained `d2c17713…` after UNKNOWN ref updates.
This is immutable-commit test proof, not a main-sync claim; the check author made
no network request or ref mutation.

The [original full-run failure](current-baseline-checks.md) remains **127 passes
and one error** at its original source. The other 127 cases were not rerun, and
this receipt does not claim a full 128-case pass at the repaired source. The [proposal](../../../proposals/current-baseline-repair.md)
records the one-method correction and unchanged case identities. Offline20,
inactive 24, older pinned 76/52 and all live account/provider/Harbor/remote-delivery
acceptance remain separate. No publisher activation, source edit, commit or
publication was performed while collecting this result.

The later status-document edition changes **four of the 51 sealed fingerprints**:
`AGENTS.md`, `README.md`, `docs/proposals/current-baseline-repair.md` and
`docs/proposals/github-publisher.md`. The other **47 inputs**, including all
product code, fixtures and inactive candidates, remain byte-for-byte unchanged.
The JSON evidence retains the source snapshot checked before those documentation
edits; the historical seal and failed receipt pair remain exact. This later
edition does not establish a single successful 128-case invocation or a remote-main update.
