# Owned-Git timeout fixture identity repair

4 November 2026. **The single corrected case passed once** at immutable
`696d13cc8131d7a39c453f25e14f3de91387be40`; the
[canonical result](../results/2026/11-04/current-baseline-repair-checks.md) and
[actual output](../results/2026/11-04/current-baseline-repair-checks.json)
record its exact identity, exit, 51 source guards and owned cleanup. This was
not a full 128-case rerun or a remote main-synchronization check.

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

The preparation commit containing the
[new source seal](../results/2026/11-04/current-baseline-repair-source.json)
was verified as an immutable commit, and only this command ran once:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest -v tests.unit.test_repository.RepositoryTests.test_owned_git_deadline_kills_and_reaps_only_its_process
```

It used existing CPython 3.14.7/Git 2.55.0, a fresh owned private temporary root,
a 120-second cap, 128 KiB per-stream caps, bounded process termination/reaping
and identity-checked cleanup. Pinned HEAD, seal bytes and all source
fingerprints/modes matched before and after. No retry or other suite rerun
occurred. The original 127-pass/one-error result remains preserved;
the other 127 case bodies and product runtime were unchanged.

The new complete non-results inventory has **51 inputs**: the prior 50 tracked
non-results files plus this proposal. The historical 43-entry hash manifest
omitted seven tracked metadata/reference files; it remains intact and is not
relabeled as a complete tree. The new seal includes those seven as well as all
product code, fixtures and inactive publisher proposals. Only `docs/results/`
is excluded. The completed check used Git only in its tiny owned fixture; no
install, CI, publisher activation, real account, remote Git, Harbor/container,
provider/model or paid service was used.

The later status edition changes four of these 51 input fingerprints: AGENTS,
README, this proposal and the publisher proposal. The other 47, including product
code and the repaired fixture, remain unchanged. The seal still identifies the
exact checked preparation source; it was not rewritten for documentation edits.
