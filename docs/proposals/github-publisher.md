# Proposed authenticated GitHub publisher activation

Last updated: 2026-10-28

Status: **prepared source proposal; not activated**. The active CLI can prepare
a local [delivery plan](../references/delivery.md). It has no `publish` command.
The supplied AGENTS.md §14 requires approval before enabling the account/Auth
integration and external-write path below. New fixture checks also require §7
approval. No permission is inferred from the earlier 76/52-case requests.

## Exact activation surface

- Copy the reviewed [publisher candidate](github_delivery.py.proposed) to
  `personal_evals/github_delivery.py`, preserving its exact bytes.
- Apply the [CLI activation patch](github-delivery-activation.patch), adding
  only the proposed `publish` command and its import.
- Copy the [authored fixture candidate](../../tests/unit/test_github_delivery.py.proposed)
  to `tests/unit/test_github_delivery.py`, preserving its exact bytes.
- Run only the two named modules below: 20 local delivery-plan cases and 24
  publisher cases, **44 total**. The [source fingerprint](../results/2026/10-28/delivery-source.json)
  freezes their exact bytes and the publisher/CLI activation surface. No real
  GitHub request is part of those fixtures.

After separately approved activation, the exact proposed command from this
repository is:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v tests.unit.test_delivery tests.unit.test_github_delivery
```

Record the actual Python version/executable, source commit/hashes, exit status,
raw output and discovered/pass/fail/error/skip totals under the owning results
directory. These fixtures use authored bundles, binary files, fake API responses,
temporary owned directories and an in-process file-lock contention check. They
do not start a child process, call the real `gh` executable or exercise the
product subprocess transport. No browser,
server, database, Harbor/container, provider, model, installation or CI is used.
The earlier 76 and 52 checks are excluded. Approval of just the 20 offline cases
would run `tests.unit.test_delivery` alone and leave the publisher inactive.

No package installation, new account, OAuth app, token grant, role assignment,
provider setting, GitHub repository setting, CI configuration or paid enrollment
is proposed. The existing `gh` executable owns its stored authentication; the
app never requests or prints the raw token. The [pinned reference](../references/github.md)
defines the actual CLI/API boundary and its limits.

## Runtime authorization and checks

The proposed entry point requires a verified, saved delivery plan and literal
`execute=True` before it can construct the real authenticated client. It checks
the exact expected account login/ID, immutable repository ID/name, visibility,
push permission, repository state, SHA1 object format, planned base and absent
namespace/ref. It uses constructed absolute `https://api.github.com/` endpoints;
no caller-selected API host or response-provided next URL is followed by app code.
The GitHub CLI retains its documented HTTP behavior, including redirects.

Content is limited to the sealed accepted bundle. Binary files use base64 blobs;
the generated tree must preserve the base and add only the selected absent
prefix. Commit metadata is explicit, and returned commit identities are verified
and durably journaled before creating the branch. No unsupported locally guessed
commit hash is treated as server proof.

Only ref **creation** is permitted. There is no ref PATCH, force update, branch
replacement, merge or remote deletion path. Requested draft/ready mode is exact;
if the destination cannot support it, publication stops without a plan upgrade
or a silent mode change. A private local journal records bounded immutable
events and prevents concurrent reuse. Resume requires the same verified plan.

PR recovery requires exact head/base repository/ref, head commit, expected PR
author, owner text and plan marker. An existing branch cannot be adopted without
the same journal's durable verified-commit receipt. Closed/merged PR recovery
can report a later owner-converted draft state; open PR mode remains exact.
A PR-create-pending event with no positive exact readback remains
uncertain; it cannot be followed by another blind POST. Mutable `PR.base.sha`
does not replace the planned immutable commit. Permission failures do not trigger
automatic login, retries or grants.

## What approval would and would not cover

Source activation enables an operator-invoked capability; fixture approval tests
it only against authored local state and fake transports. Neither authorizes this
agent to inspect the real login, upload a real bundle, create a branch/PR, trigger
notifications/automation or spend money. A later live check needs an exact
destination, reviewed data and separately authorized mutation/cleanup scope.

Live GitHub behavior, draft availability, actual token permissions, REST races,
account identity and destination automation remain unverified. Existing CLI
redirect semantics and repository administrator changes cannot be described as
an atomic destination or base-commit lease. Partial immutable objects or a created
branch can remain after an error; receipts must report that state.

The full [product contract](../spec.md), live provider generation, actual Harbor
acceptance and real repository delivery remain open until independently verified.
