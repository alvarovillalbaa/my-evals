# Repository-connected generation handoff source

Date: 2026-10-28. Status: published source and static checks only; no runtime
test, provider call or generated-task execution is claimed.

## Product requirement advanced

The [owning brief](../../../spec.md) requires provider/repository-connected
generation and download/PR delivery beyond the initial portable comparison CLI.
This increment implements the local repository/request/draft/review path. It
does not substitute the handoff for the remaining live provider or PR integration.
The [initial source receipt](initial-source.md) and its 76-case proposal remain
a separate historical source/approval boundary.

## Source behavior

- Explicit repository/revision/file selection captures committed Git blobs,
  preserving selected order, bytes, modes, full commit/OIDs and policy/content
  identities. It reads no source from dirty/untracked working-tree files and
  performs no checkout, index mutation, fetch, replacement-object lookup or
  filter transformation. Git stdout/stderr, per-call time and owned processes
  are bounded. Installed Git 2.55.0 was observed; its official source contract is
  pinned in the [Git reference](../../../references/git.md).
- Selection permits ordinary source and benign configuration such as `auth.py`
  and `.github` workflows, while rejecting known credential material, Git metadata,
  traversal, links/gitlinks and unsupported/oversized inputs. This is not content
  secret detection or a repository-wide privacy claim.
- The self-contained generation request seals the selected snapshot and owner
  task goals, source references, grading requirements, decision, policy, split
  and requested model. Every selected source is used; no extra source is added
  implicitly. Preparing a request transmits nothing.
- Supplied responses must match request/snapshot/model and task IDs/source
  references. Every task file is supplied, and owner-defined task/TOML/policy/
  threshold metadata cannot be changed by the response. The existing suite
  validator checks the emitted files; import creates a private review-required
  draft rather than an accepted bundle.
- Explicit owner acceptance validates review/request/current draft identities,
  checks owner metadata before reading redirected task paths, captures reviewed
  bytes privately and invokes the existing bundle writer on those captured
  bytes. No generated instruction, grader, container or model executes.

The four CLI commands are `snapshot`, `generation-request`, `generation-import`
and `generation-accept`. The [generation contract](../../../references/generation.md)
owns their workflow and data meanings. Local hashes establish supplied artifact
integrity; they do not authenticate a provider, prove semantic grounding or
independently attest commit membership after transfer.

## Verification and retained boundaries

Source-only checks passed after source freeze: 23 Python modules parsed, relative
imports and example JSON/TOML resolved, all 40 local Markdown links resolved, and
all 45 tracked/new files passed whitespace checks. The existing Python `3.14.7`
version and executable attribution were captured in the same repository process;
machine-local paths are not committed. No product/test module was imported by
those tools. Source and fixtures are recorded in the separate
[increment fingerprint manifest](repository-generation-source.json).

The [new check proposal](../../../proposals/repository-generation-checks.md)
scopes 52 authored, unexecuted cases: 20 repository, 20 generation and 12 CLI.
The original 76 tests and initial 23-file fingerprint manifest remain unchanged.
Their exact source at `1081ca8c3aca64ea02e0818b8e27fbd855bb7e2c` is preserved;
later CLI changes are not silently substituted into that pending approval.

Independent source review refined overbroad credential-name rejection, preserved
multiline owner instructions, checked process ownership/lazy-fetch suppression,
and moved owner/path validation before draft file reads. This is source evidence,
not successful native Git/app/runtime acceptance.

## Publication

The source, examples, three test files and separate check proposal were published
in [`424c81fd033b8c1211e6f81044888dcd00297aaf`](https://github.com/alvarovillalbaa/my-evals/commit/424c81fd033b8c1211e6f81044888dcd00297aaf).
The connected GitHub branch readback matched that commit, and all 45 remote
file entries matched the local committed path, mode and blob SHA. The other
26 existing blobs were preserved. The working tree was clean after publication.
This publication follow-up changes documentation only; all functional checks
remain unexecuted under their separate pending scopes.

## Remaining outcome

No provider endpoint or credential connection, model call, PR creation, cloud
database, Auth/CI/production configuration, dependency installation or paid plan
was introduced. Live generation, generated task quality/calibration, authentic
provider provenance, real Harbor/agent/container acceptance and authorized
repository delivery remain unfinished. All 128 authored cases across the two
scopes are unexecuted at this checkpoint; source publication is not proof that
the full product or portfolio is complete.
