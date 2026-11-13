# GitHub delivery contract and activation boundary

Current live evidence: [13 November authored delivery](../results/2026/11-13/live-github-delivery.md).
GitHub returned the first outgoing commit message without its final newline.
The publisher now omits that newline when constructing the request and still
compares the response literally. Authorship/tree/parent checks are unchanged.
Only the supervised approved-tool profile passed; the default native child's
connection failure remains unaccepted. The exact fixture PR is closed and its
branch retired; the historical source/check authorization below is not the
separate live authorization.

Last updated: 2026-11-04

This reference prepares the PR-delivery requirement in the
[owning specification](../spec.md). Offline delivery planning does not access an
account or publish a branch/PR. The owner authorized the operator-invoked
[publisher source and focused checks](../proposals/github-publisher.md); the
repaired capability has [51 focused local checks passed](../results/2026/11-04/publisher-activation-checks.md).
Publication of this product's
source does not authorize uploading a private evaluation bundle elsewhere.

## Primary sources and versions

Research on 28 October 2026 used the official REST documentation with explicit
API version `2026-03-10`, and the installed `gh 2.100.0`. The matching CLI source
is pinned to [`45437bc7eeeb3359bbfddd1742f79de7652fd3e2`](https://github.com/cli/cli/commit/45437bc7eeeb3359bbfddd1742f79de7652fd3e2).
Official documentation repository HEAD was
[`57f571f065a75c31071127b8027a44b064181add`](https://github.com/github/docs/commit/57f571f065a75c31071127b8027a44b064181add).
The API-description repository HEAD was
[`c66e298030d4070b70a569dcd4268b3a041b5380`](https://github.com/github/rest-api-description/commit/c66e298030d4070b70a569dcd4268b3a041b5380);
the versioned OpenAPI file was located by metadata, rather than downloading its
13.8-MB compiled JSON. Endpoint contracts below were read from their official
REST pages. No destination/account endpoint, login, token command, PR or write
request was executed for this research.

| Endpoint family | Contract used |
| --- | --- |
| [Repository metadata](https://docs.github.com/en/rest/repos/repos?apiVersion=2026-03-10#get-a-repository) | Check the explicit destination's identity, visibility and reported permissions before writes |
| [Blobs](https://docs.github.com/en/rest/git/blobs?apiVersion=2026-03-10#create-a-blob) | Create binary-safe Git blobs using `encoding:"base64"`; the restricted publisher admits SHA-1 destinations |
| [Trees](https://docs.github.com/en/rest/git/trees?apiVersion=2026-03-10#create-a-tree) | Explicit paths, modes and blob SHAs; retain `base_tree` to preserve unrelated files |
| [Commits](https://docs.github.com/en/rest/git/commits?apiVersion=2026-03-10#create-a-commit) | Explicit tree, parent, message, author and committer metadata |
| [References](https://docs.github.com/en/rest/git/refs?apiVersion=2026-03-10#create-a-reference) | Create a new branch; an existing branch is a reconciliation/conflict case |
| [Pull requests](https://docs.github.com/en/rest/pulls/pulls?apiVersion=2026-03-10) | Create the reviewed PR and reconcile by exact head/base identity across all states |

## Existing authentication, without credential extraction

The publisher may invoke the existing CLI login through `gh api` only after
literal execution approval and POSIX locking support. Offline CLI commands do
not import the publisher. In `publish_delivery`, unsupported platforms receive
a finite `github_platform_unavailable` before its internal plan validation,
journal or client creation. The CLI may first read/verify the explicit local
artifact.
It must not invoke `gh auth token`, expose token values, create an account,
request additional scopes, change the active account, run a browser login, or
silently repair authorization failures. A reviewed actor ID/login must match
the authenticated actor observed during execution; declared commit authorship
alone is not evidence of the authenticated sender. The CLI can select an
environment-supplied token ahead of stored credentials, so the proposal must
state whether such existing overrides are admitted. It cannot claim to freeze
an account while another process changes the shared CLI login.

The pinned CLI [adds active credentials inside its HTTP transport](https://github.com/cli/cli/blob/45437bc7eeeb3359bbfddd1742f79de7652fd3e2/api/http_client.go#L153).
The caller does not need to retrieve a credential. It should send complete
JSON via stdin using `--input -`, an explicit method and the fixed JSON media
type/API-version headers. Do not use `-F` coercion, repository placeholders,
verbose/debug request logging, a pager, an unbounded pagination loop, or raw
HTTP/error output as a public receipt. Capture bounded subprocess output with
a deadline and project only approved fields/status codes.

`--hostname github.com` is insufficient to pin the request destination: the
pinned CLI applies a configured experimental `api_host` to relative endpoints.
Construct only absolute `https://api.github.com/` URLs with validated/encoded
endpoint segments; do not accept arbitrary supplied URLs. Absolute endpoints
[bypass that host substitution](https://github.com/cli/cli/blob/45437bc7eeeb3359bbfddd1742f79de7652fd3e2/pkg/cmd/api/http.go#L16).
The CLI has no documented `gh api` flag that refuses every HTTP redirect. Its
credential transport avoids adding a token after a hostname-changing redirect,
but that does not establish that redirected request content could never leave
the original origin. The adapter must describe existing CLI transport/config
trust honestly, rather than advertise `redirect:error` semantics.

## Reviewed destination and immutable content

The execution proposal must bind the accepted bundle and delivery-plan hashes,
repository numeric ID and full name, expected visibility, base branch and
expected base commit, destination prefix, actor, timestamp and exact PR text.
Private/local plans and payloads are not automatically committed to this public
source repository. Data policy must permit this particular destination;
`containsPersonalData` or a local generation handoff is not publication approval.

After activation, preflight must reject identity/visibility drift, archived or
disabled destinations, absent base refs and inadequate reported write access.
It must also check the documented [repository hash-algorithm endpoint](https://docs.github.com/en/rest/repos/repos?apiVersion=2026-03-10#get-the-hash-algorithm-for-a-repository)
and admit only `hash_algorithm:"sha1"` for this initial Git-data profile.
Repository metadata can contain a sensitive `temp_clone_token`; never retain
or log the raw metadata response.
Reported repository permissions do not prove that a particular token has every
required scope: Git-object writes require Contents write; PR creation requires
Pull requests write, and the server remains authoritative. Unsupported access
fails without refreshing scopes or escalating a plan.

The offline planner captures and rechecks the accepted, verified bundle. The
publisher validates the sealed, self-contained plan bytes; it does not infer
or re-read a bundle path. The reviewed manifest binds every relative
destination path, mode, byte count and SHA-256. Binary
content is base64, never replacement-decoded text. Verify returned Git blob
IDs against local raw-byte Git hashes. Use only ordinary blob files beneath
the selected artifact prefix, with no workflow, symlink, gitlink or deletion
entries. Before writing, prove the new prefix is absent in the pinned base.
Tree creation must retain the base tree: omitting it can turn all unrelated
base files into apparent deletions; supplying an existing path can overwrite
that path. Reject truncated tree evidence and read only bounded needed trees.

## Commit, branch and PR sequence

1. Prepare a private, append-only local journal and exclusive local operation
   ownership before the first external write. Bind it to the reviewed plan.
2. Create/verify immutable blob and tree objects. Create a commit with exactly
   one parent, the approved base commit, the reviewed tree and ASCII message.
   Supply both author and committer name/email/date; otherwise the API can use
   current identity/time defaults. A proposed noreply identity must be derived
   from the reviewed actor, not a newly collected private email address.
3. Read back and verify the returned commit's tree, parent, message and full
   metadata; durably record its SHA before any branch request. REST documents
   these metadata fields but does not guarantee a particular raw commit-byte
   serialization or trailing-message-newline normalization. A locally predicted
   SHA is not a documented guarantee. Do not fabricate that guarantee to make
   lost-response recovery appear complete.
4. Recheck the destination and base. Create the deterministic new branch
   directly at the verified commit. Never update, force, delete or repoint an
   existing ref. An existing matching ref may be reconciled only against the
   intended commit SHA already durably recorded in this plan's journal, after
   checking its exact tree/parent/message/identity metadata. A missing commit
   receipt or different head is a conflict. Matching remote content alone is
   not ownership; losing the local journal requires manual review.
5. Recheck the base before creating the reviewed PR. The PR's head/base repo
   identities, branch names, head commit, marker, title and body must match.
   Draft availability depends on destination capabilities: failure must not
   silently create a ready PR or change the account's plan. PR creation can
   notify people; that effect belongs in the separate execution approval.
   Creation/readback must honor the owner's actual draft boolean. An existing
   open PR with changed mode is a conflict. Closed/merged recovery may report
   its current mode after an owner's conversion, without changing or reopening
   the PR; the authenticated creator must still match the reviewed actor.

The REST ref-update endpoint's `force:false` is a fast-forward rule, not an
expected-old-SHA compare-and-swap. This design avoids ref updates entirely.
Base-ref and visibility checks are also not transactional with subsequent
writes. The base can move between checks; retain the planned commit parent,
report observed drift, and never silently rebase, merge or change the plan.
The current `base.sha` on a PR is mutable and is not its retry identity.

## Ambiguous outcomes and recovery

Append an intent event before each visible branch/PR write, followed by a
verified result event. Events contain operation/plan IDs, hashes, remote object
IDs and safe phase/status metadata, never credentials, raw request/response
bodies, absolute paths, source bytes or exception messages. Existing events
must not be overwritten. If local durable recording fails, stop before the
next remote write. Retain partial remote objects/branches; no automatic cleanup
or deletion is authorized.

A lost immutable-object response is distinct from a lost PR response. Before
branch creation, a repeated fixed object intent cannot overwrite an existing
branch, but might leave an unreferenced object; do not claim those requests
have a general documented idempotency key. Branch reconciliation reads its
exact deterministic ref and requires the durably recorded desired commit.
An absent ref with `branch_pending` cannot distinguish a failed create from an
owner deletion after a lost acknowledgement. Preserve uncertainty unless a
positive exact PR is recovered; never blindly create that branch again.

For an uncertain PR request, query bounded all-state results for the exact
head/base and verify the complete delivery identity. A unique matching PR can
be recovered, including a subsequently closed or merged one. Never reopen,
merge, overwrite edited text, or create a replacement automatically. Multiple
or mismatched candidates are conflicts. An absent read does not prove a timed-
out request will never arrive; retain `pr_create_pending` and require explicit
resolution instead of blindly retrying POST. The REST PR endpoint documents
no client idempotency key or atomic check-and-create transaction.

## Source activation and live-use boundary

The [current packet](../proposals/github-publisher.md) records the owner's source/check
authorization, repaired active publisher/CLI, preserved 24 case bodies, seven
new regression/owned-transport cases and a complete frozen 51-case scope. The
original `.proposed` module/tests and activation patch remain historical inputs;
they must not overwrite the repaired active implementation.

The [canonical result](../results/2026/11-04/publisher-activation-checks.md) records
one exact-source invocation with all 51 case IDs `ok`, unchanged source guards
and owned cleanup. The 24 original case bodies/helpers remain unchanged copies.
Fake-gh subprocesses exercised local framing/deadline/cleanup only, without
real `gh`, authentication, GitHub, provider, Harbor or full-product acceptance.
Source activation and
fixture approval do not authorize a live account lookup, private bundle upload,
branch/PR, notifications, automation or spend. Those actions need the exact
reviewed destination/data/live-effect scope; no such action occurred here.
