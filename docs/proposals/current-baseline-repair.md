# Owned-Git timeout fixture identity repair

4 November 2026. **Source preparation only; the corrected case has not run.**

The [current-source baseline](../results/2026/11-04/current-baseline-checks.md)
ran once at `d2c177131ae79ea02443eddfeb1ecdc726d06271`: 127 cases passed and one
errored. After receiving the expected `repository_git_timeout`, the owned-Git
deadline fixture could not read its child-created `owned.pid` file. Why that
startup acknowledgement was absent remains unproven. Both original failure
receipts remain unchanged.

Only `test_owned_git_deadline_kills_and_reaps_only_its_process` changes. Its local
spy calls the saved real `subprocess.Popen` and returns the same process object.
The PID therefore comes from the actual kernel-issued process handle rather
than a file the child might not create before the deadline. The stub only sleeps
for two seconds. The product's 0.2-second deadline, exact timeout error,
1.5-second elapsed assertion and `os.kill(pid, 0)` / `ProcessLookupError` check
remain. The fixture additionally requires exactly one captured process and a
non-null `-SIGKILL` return code, establishing that its process was reaped.
Product code, shared helpers and the other 127 baseline case bodies are unchanged.

After the preparation commit containing the
[new source seal](../results/2026/11-04/current-baseline-repair-source.json)
is published and its immutable SHA supplied, execute only:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest -v tests.unit.test_repository.RepositoryTests.test_owned_git_deadline_kills_and_reaps_only_its_process
```

Use the existing Python/Git installations, a fresh owned private temporary root,
a 120-second cap, 128 KiB per-stream caps, bounded process termination/reaping
and identity-checked cleanup. Verify the pinned HEAD, seal bytes and complete
source fingerprints/modes before and after. Record the one actual case ID,
status, exit, runtime, bounded output hashes and cleanup; preserve any failure
before another change. No retry or full128/20/24/76/52 rerun is proposed.

The new complete non-results inventory has **51 inputs**: the prior 50 tracked
non-results files plus this proposal. The historical 43-entry hash manifest
omitted seven tracked metadata/reference files; it remains intact and is not
relabeled as a complete tree. The new seal includes those seven as well as all
product code, fixtures and inactive publisher proposals. Only `docs/results/`
is excluded. No tests, imports, installs, CI, publisher activation, real account,
remote Git, Harbor/container, provider/model or paid service run during this
preparation. Future one-case setup may use Git only in its tiny owned fixture.
