# GitHub publisher activation and focused checks

Last updated: 2026-11-04

Status: **source-enabled; 51 selected local checks passed once** at
`79088442419bdddf9cdad156450e019a53376364`. The
[canonical receipt](../results/2026/11-04/publisher-activation-checks.md) and
[actual identities/output](../results/2026/11-04/publisher-activation-checks.json)
record one invocation: all 51 exact unique IDs `ok`, no skip/nonpassing case,
child exit zero, all 55 source guards and verified owned cleanup. Unittest
reported 4.239 seconds; the supervised child took 4.490 seconds, with no outer
timeout, termination or stream truncation. The owner's
repeated “approve everything / keep going / do all the work” instructions
authorized the source repair and bounded local verification. Independent review
and immutable source publication preceded this one execution.

This authorization permits no real account lookup, bundle export, branch/PR
write, notification, credential change or paid action. The operator-invoked
capability requires an exact reviewed plan and explicit live-use authorization
before this agent may use an existing account. Fixtures establish no live acceptance.

## Source change

- Activate the reviewed candidate as `personal_evals/github_delivery.py` and
  wire `publish PLAN --journal PRIVATE_DIRECTORY --execute`, optionally
  `--resume`. The CLI imports the publisher only in its publish dispatch.
- Guard Unix-only `fcntl`. In `publish_delivery`, after literal execute and
  boolean resume checks, unsupported platforms return
  `github_platform_unavailable` before its internal plan validation, journal
  access or client construction. The CLI may first read/verify the explicit
  local artifact. Offline commands remain importable without `fcntl`.
- Fence an absent `branch_pending` ref as uncertain. A lost creation
  acknowledgement followed by owner deletion cannot cause a second ref POST.
  Positive exact PR recovery, including a closed PR, remains available.
- Name the unchanged 30-second transport deadline so one owned deadline fixture
  can temporarily use 0.2 seconds without relying on a child-written PID file.

The original [publisher candidate](github_delivery.py.proposed),
[activation patch](github-delivery-activation.patch) and
[24-case candidate](../../tests/unit/test_github_delivery.py.proposed) remain
unchanged historical inputs. The active 24 case bodies are unchanged copies;
the repaired active publisher supersedes the old patch. `scripts/check.py`
separates active and historical AST declarations without claiming execution
status or unique coverage.

## Completed local verification

The [complete source inventory](../results/2026/11-04/publisher-activation-source.json)
freezes every tracked non-results path, mode, Git blob, byte count and SHA-256,
including preserved candidates. Its literal case IDs define this selection:

| Module | Cases | Meaning |
| --- | ---: | --- |
| `tests.unit.test_delivery` | 20 | Offline accepted-bundle and delivery-plan regressions |
| `tests.unit.test_github_delivery` | 24 | Existing stateful fake-API destination/object/journal/recovery cases |
| `tests.unit.test_github_delivery_regressions` | 3 | Missing `fcntl` cold CLI, ordered platform refusal and absent pending-ref recovery |
| `tests.unit.test_github_transport` | 4 | Actual owned fake-gh framing, finite errors, cap and deadline cleanup |
| Total | 51 | One serial unittest invocation; no other suites |

The receipt records the actual Python version/profile and executable. The
single supervised child used these exact arguments:

```sh
python3 -B -S -m unittest -v \
  tests.unit.test_delivery \
  tests.unit.test_github_delivery \
  tests.unit.test_github_delivery_regressions \
  tests.unit.test_github_transport
```

The run enforced a 120-second process-group wall cap, 128 KiB per captured
stream and TERM/KILL cleanup bounds. It needed no outer termination or retry.
All 51 unique IDs were `ok`, with no failure/error/skip/expected-failure/
unexpected-success. HEAD, the 69-entry index, complete source bytes/modes,
the seal and historical evidence matched before and after; reaping, absence
of the outer process group and owned fixture cleanup passed.

The parent used a nonce-marked temporary root and verified its device/inode
before cleanup. HOME, GH_CONFIG_DIR, XDG_CONFIG_HOME, TMPDIR, TMP and TEMP were
owned paths, with bytecode off and TZ=UTC. Main PATH pointed only to an owned empty
directory, so an accidental default client cannot discover real `gh` or account
configuration. The absolute Python interpreter remained callable. Each fake-gh
case replaced PATH with its own executable directory and no credentials.
Fixture cleanup passed before exact-owned-root removal. No global process or
filesystem cleanup occurred.

The four transport cases exercised six actual owned Python fake-gh children in
total, and the cold offline CLI regression used one isolated Python child.
The fake transport observed the real spawned PID through a pass-through Popen
observer, checked framing/stdin and sanitized errors, and required each child
and process group to be gone. The 0.2-second case did not rely on a child-written
PID file or assume its first statement ran. The production default remains
30 seconds.

No real `gh`, account/config lookup, HTTP request, server, database, browser,
Harbor/container, provider/model call, package install or CI is part of this
packet. Existing Python standard library and small authored temporary files only.

This later edition changes exactly six status documents among the 55 tested
inputs: `AGENTS.md`, `README.md`, this proposal, `docs/spec.md` and the delivery/
GitHub references. The other 49 inputs, including all code, tests, checker and
historical candidates, remain unchanged. The original source seal and complete
checked-source receipt are preserved; this documentation edition was not rerun.

## Runtime behavior and limits

The [GitHub contract](../references/github.md) retains exact actor/destination,
visibility/push/state, SHA1 format and immutable base checks. Only sealed accepted
bundle bytes are eligible; binary blobs and returned tree/commit identities are
verified. Branch creation is create-only: no ref update, force, merge or deletion.
The private bounded hash-linked journal prevents concurrent use. Resume must
match the same verified plan and durable object receipts. A PR is recoverable
only with the exact head/base repositories and refs, desired commit, author,
owner text and plan marker; ambiguous PR POST is never blindly repeated.

Fake-gh checks establish the local subprocess/protocol boundary, not actual
GitHub CLI authentication, redirects, scopes, REST races, draft availability or
remote automation. Destination administrators can change state between requests;
the app has no atomic remote lease or expected-old ref CAS. Partial immutable
objects or a created branch can remain after failure. Live use must explicitly
authorize the exact destination, reviewed data and effects/cleanup separately.

## Separate historical evidence

The [offline 20-case receipt](../results/2026/11-04/delivery-plan-checks.md)
passed once at `d031a159d0baead0a5bac7f38e777f4e1bd03e5f`, with all 43 source
guards and owned cleanup. It does not verify the newly active publisher.
The [current baseline](../results/2026/11-04/current-baseline-checks.md) records
127 passes and one preserved error; the [single corrected case](../results/2026/11-04/current-baseline-repair-checks.md)
then passed on its own pinned source. No one invocation passed all 128.
The original 76/52 pinned executions remain unrun. All historical seals and
failures remain intact; neither the old 43-input nor 51-input seal substitutes
for the new complete activation inventory.

The [full product contract](../spec.md), live provider generation, actual Harbor
acceptance and real repository delivery remain open.
