# Reviewed bundle delivery

Last updated: 2026-10-28

Delivery starts from an accepted [portable bundle](formats.md), not a generation
request or repository snapshot. The active commands create and verify a private,
self-contained GitHub delivery plan. They do not contact GitHub or read account
credentials. The authenticated publisher remains an
[inactive proposal](../proposals/github-publisher.md) under the supplied §14 gate.

## Prepare the exact destination

Write a delivery intent containing:

- The repository name and immutable numeric ID, expected visibility, base branch
  and full base commit, a new branch name and an absent destination prefix.
- The expected operator's GitHub login/ID and a fixed UTC creation timestamp.
- The PR title/body, explicit draft/ready mode and sharing purpose.

[examples/delivery-intent.json](../../examples/delivery-intent.json) contains
placeholders, not a selected live destination or account. Replace them before
preparing a real plan. The fixed timestamp belongs to the saved intent; do not
regenerate a plan to recover an uncertain remote operation.

```sh
python3 -m personal_evals delivery-plan artifacts/accepted \
  --intent path/to/delivery-intent.json --confirm-sharing \
  --out artifacts/delivery.json
python3 -m personal_evals delivery-verify artifacts/delivery.json
```

`--confirm-sharing` records the owner's permission to share this exact bundle
with that destination. It does not execute a remote action or prove ownership,
license suitability or the repository's current settings. Actual account,
permission, visibility, base and namespace checks belong to the proposed
publisher before any remote write.

The output embeds canonical `bundle.json` and every task file under the chosen
prefix. All content uses canonical base64, preserving binary bytes; base64 is
not encryption. The plan excludes generation requests, source snapshots, review
records, private checkout paths and Git configuration. A manifest may itself
contain private task questions/content: inspect the accepted bundle before
confirming sharing.

Public destinations reject bundles declared private or containing personal data.
The planner does not silently reclassify a bundle. Local validation requires the
exact manifest/file inventory, lengths, SHA256 and Git blob identities, TOML task
identity and the owner-bound data/decision policy. An edited payload, destination,
actor, PR text or consent changes the plan ID.

## Local plan contract

```text
{schemaVersion:1,kind:'personal-evals-delivery-plan',bundleId,
 target:{repository,repositoryId,visibility,baseBranch,baseCommit,newBranch,pathPrefix},
 actor:{login,id},createdAt,pullRequest:{title,body,draft},
 publication:{operatorConfirmed:true,bundleId,targetFingerprint,purpose},
 preconditions:{baseUnchanged:true,visibilityMatches:true,newBranchAbsent:true,pathPrefixAbsent:true},
 files:[{path,mode:'100644',encoding:'base64',content,bytes,sha256,gitBlob}],planId}
```

The initial destination profile is GitHub.com with SHA1 Git object IDs; its
publisher must confirm the destination's algorithm. Plans admit at most the
existing 10,001-file bundle inventory and 64 MiB encoded JSON. Core task limits
remain unchanged. Paths must be a nonempty, safe relative namespace, without
duplicate, Unicode-normalized/casefold or file/directory-prefix collisions.
Base and new branches must differ and pass the conservative ref-name contract.
Local outputs remain private and refuse overwrite; writing inside the source
bundle is rejected.

## Proposed remote publication

The separate [GitHub contract](github.md) records the actual API and existing
GitHub CLI behavior. The proposed publisher reuses that CLI's active login,
checks the expected actor/repository/visibility/permissions, uploads immutable
objects and creates only the selected new ref and PR. It does not force-push,
replace an existing branch, merge, delete remote resources, grant a role, change
repository settings or enable a paid plan.

A private append-only receipt records mutation intent before calls and verified
identities afterward. Uncertain PR creation is reconciled by a positive exact
readback; absence from a query is not proof that an earlier request cannot still
arrive. The publisher must never blindly submit that PR again. Partial remote
objects/branches are retained and reported, not silently removed.

These are proposed execution semantics, not live acceptance evidence. REST
prechecks cannot atomically freeze administrator-controlled repository settings
or the base branch. The existing GitHub CLI's documented redirects still apply.
Publishing may trigger destination notifications and existing automation; no
actual publication is authorized by preparing this plan.
