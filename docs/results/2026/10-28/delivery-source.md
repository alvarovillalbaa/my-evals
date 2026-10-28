# Offline delivery plans and inactive publisher source

Date: 2026-10-28. Status: source/static verification only. No runtime test,
account lookup, provider call or remote delivery is claimed.

## Product requirement advanced

The [owning brief](../../../spec.md) requires download/PR delivery after personal
evaluation generation. The active local CLI now seals an accepted portable
bundle into a self-contained binary-safe repository delivery plan. The
[workflow](../../../references/delivery.md) records its strict destination,
account, immutable base, new branch/path prefix, PR text and sharing consent.
Preparing or verifying that artifact sends nothing and reads no credentials.

The authenticated publisher is a deliberately inactive
[source candidate](../../../proposals/github_delivery.py.proposed), accompanied
by an unapplied [CLI patch](../../../proposals/github-delivery-activation.patch)
and 24 inactive fixture cases. Its existing-GitHub-CLI/API contract and limits
are recorded in the [primary-source reference](../../../references/github.md).
The separate [activation/check proposal](../../../proposals/github-publisher.md)
is the reviewable §14/§7 approval surface; it does not request a real account
lookup or GitHub mutation.

## Source behavior and review

- Offline planning embeds exactly the verified bundle manifest and selected task
  files, preserves binary bytes, rechecks hashes/inventory/TOML, rejects path
  collisions, and creates private exclusive outputs. Private or personal-data
  declarations cannot be silently exported to a public destination.
- The inactive publisher checks the selected actor/repository/visibility/push
  permission/SHA1 profile, preserves the base tree, verifies immutable objects,
  and journals a verified commit durably before creating a new ref. It has no
  force/update/merge/delete or scope-escalation path.
- Source review fixed a recovery ownership gap: a matching remote branch cannot
  be adopted without this journal's durable verified-commit receipt. It also
  tightened malformed stopped-event and PR merged-state validation. Exact
  positive PR recovery checks author/text/head/base/mode; an uncertain PR POST
  cannot be followed by a blind repeat. These are inspected semantics, not
  observed GitHub runtime guarantees.
- Independent source/fixture/activation reviews found no further concrete
  mismatch. The real subprocess adapter and live CLI/API behavior remain
  unexecuted. Existing CLI redirect semantics and REST races are explicit limits.

## Verification boundary

The [fingerprint manifest](delivery-source.json) records the exact source,
activation patch, examples, contracts and fixture hashes. Static verification
parses Python and inactive `.py.proposed` source as AST, checks local relative
imports/document links/example formats, counts authored cases, and checks
whitespace and activation-patch applicability. It never imports product modules
or runs a fixture, task, subprocess adapter, Harbor, container or provider.

There are **44 new authored cases: 20 offline-plan and 24 inactive publisher**.
All remain unexecuted and separately gated. Across this source tree there are
172 authored cases including the unchanged 128 earlier cases. The initial
76-case scope remains pinned at `1081ca8c3aca64ea02e0818b8e27fbd855bb7e2c`;
the 52 repository/generation cases remain pinned at
`424c81fd033b8c1211e6f81044888dcd00297aaf`. Their historical manifests are
preserved, rather than presented as approval for successor sources.

Static verification used the existing Python 3.14.7 executable: 25 active Python
files and two inactive proposals parsed, 67 local Markdown links resolved, and
172 authored cases were counted without importing them. The proposed activated
CLI was reconstructed and parsed in memory only; its expected SHA256 is
`b74b3396481cf8df8c250d5b016294f9e5c435c4bc550038308f3f8464bff2a4`.
`git apply --check` passed without applying the activation patch.
`git diff --check` and separate checks of all 11 new files passed. All 23
initial and 30 repository/generation historical fingerprint entries matched
their respective immutable commits. The new manifest freezes 43 files.

No installation, build, server, browser, database,
CI, model call, real account lookup or product GitHub write occurred. Publishing
this application's source is separate from publishing an evaluation bundle.

## Source publication

Published source commit
[`c7197bc69665e334c0d6b18b32e4e54f5693358f`](https://github.com/alvarovillalbaa/my-evals/commit/c7197bc69665e334c0d6b18b32e4e54f5693358f)
was pushed to the personal repository's `main`. Connected GitHub readback
confirmed that branch identity and all 56 file paths, modes, object types and
blob SHAs against the local recursive Git tree; the response was not truncated.
That proves this source publication, including the inactive review package.
It does not execute the product's GitHub integration or publish any task bundle.

A separate approval request links the immutable proposal at that commit and
offers either exact activation plus 44 fixtures, just the 20 offline fixtures,
or leaving both pending. No approval has been inferred from the active portfolio
goal or La Porra's separate 38-case approval. This receipt-only follow-up keeps
the frozen source and candidate hashes unchanged.

## Remaining work

Explicitly approved source activation/fixture checks, destination-specific live
delivery acceptance, real provider generation and approved Harbor execution
remain open. Source publication does not complete the all-project goal. This
local CLI needs no Vercel or Supabase service for the delivered capability.
