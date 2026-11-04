# Publisher activation checks — 51 passed

4 November 2026. **51/51 passed**, with no failures, errors, skips,
expected failures or unexpected successes, in one serial invocation at
`79088442419bdddf9cdad156450e019a53376364`. Child and supervisor exits were **0**. The
[JSON receipt](publisher-activation-checks.json) retains all actual IDs/statuses,
complete raw bounded stdout/stderr, their hashes and source/evidence guards.

| Selected module | Passed |
| --- | ---: |
| `tests.unit.test_delivery` | 20 |
| `tests.unit.test_github_delivery` | 24 |
| `tests.unit.test_github_delivery_regressions` | 3 |
| `tests.unit.test_github_transport` | 4 |

The defects' regressions passed: optional `fcntl`/ordered direct-function refusal,
lazy offline CLI import, and absent pending-ref uncertainty without recreating
an owner-deleted branch. The four transport cases exercised an actual **owned
Python fake-gh executable**, including stdin/HTTP framing, finite HTTP/JSON
errors, output bounds and deadline cleanup. The production request default
remains 30 seconds; one fixture temporarily used 0.2 seconds. These are local
protocol checks, not live GitHub delivery.

Actual runtime: **CPython 3.14.7 on macOS**, invoked through the existing absolute
interpreter with `-B -S`. Unittest reported **4.239 seconds**; supervised child
wall time was **4.490 seconds**. The child received only owned empty PATH/HOME/
config/temp directories, bytecode disabled and UTC; no account/provider
credentials were inherited. Real `gh` and Git were absent from that test PATH.
The supervisor used local Git metadata reads solely to verify source identity.

The [source seal](publisher-activation-source.json), SHA-256
`d85affab531ebf822ff27a1f2acdf6fd9fef5e5aa83701e0d5577d4dc17f4636`, matched its pinned Git bytes. All **55 source inputs /
509,261 bytes**, complete **69-leaf** index/tree identity, and **14 existing
result/evidence blobs** matched before and after. Parent confirmed the exact
main publication before execution; the check author made no remote/ref action.
Historical failures and earlier seals remain unchanged.

Stdout was empty; stderr was **10,321 bytes**, SHA-256
`fadd707a46ea5e0a6e0ab208c3efb9029602edc050b08f1a587af529517e3bae`. Neither stream was truncated. No supervisor timeout,
interruption or forced kill occurred. The main child was reaped and its group
was absent; owned directories retained their identities and were empty before
the exact parent root was removed. The six fake-gh and one cold-CLI child counts
come from the reviewed fixtures and their passing assertions, **not a global
process inventory**. Deliberate fake-gh deadline/overflow kills are distinct
from supervisor cleanup.

The [proposal](../../../proposals/github-publisher.md) owns scope and runtime
limits. No real account/config lookup, HTTP/provider/model call, bundle export,
remote Git, branch/PR write, notification, Harbor/task/container, install, CI,
server/browser/database or paid service was involved. Live authentication,
redirects, permissions, REST races, actual provider generation and full product
acceptance remain open. No other suites were run, source repaired, retry made,
or commit/publication performed by this check author.

The later status edition changes **six of the 55 sealed fingerprints**:
`AGENTS.md`, `README.md`, `docs/spec.md`, `docs/proposals/github-publisher.md`,
`docs/references/delivery.md` and `docs/references/github.md`. The other **49
inputs**, including all code, tests, the checker and historical candidates,
remain unchanged. The raw JSON and immutable source seal retain the exact
checked snapshot at `79088442419bdddf9cdad156450e019a53376364`; neither was
rewritten for these documentation edits. No additional execution or live
acceptance is implied by that later edition.
