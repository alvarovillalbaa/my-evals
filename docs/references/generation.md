# Repository-connected generation handoff

Last updated: 2026-10-28

This implements the local repository/request/draft portion of the
[Personal Evals brief](../spec.md). It does not connect a provider account, send
source to a model, authenticate a response or create a pull request. Those are
still required integration work; a local handoff is not called live generation.
The [Git reference](git.md) owns committed-file capture. The existing
[bundle contract](formats.md) and [Harbor profile](harbor.md) own accepted tasks.

## Select committed source

Specify a local repository, revision, label, data-policy file and every selected
file. The revision is resolved once; bytes come from that immutable commit,
including when working-tree files have different unsaved edits. There is no
checkout, reset, stash, fetch or implicit directory scan. Missing local objects
fail rather than fetching from a promisor remote. No origin URL or checkout
location is copied into the artifact.

```sh
python3 -m personal_evals snapshot --repo . --revision HEAD --label format-demo \
  --file examples/demo-text/instruction.md --policy examples/source-policy.json \
  --out artifacts/source.json
```

The example is explicitly authored demonstration content. Replace the selection
and policy with files you are authorized to use. File-name fences do not prove
that source text contains no sensitive data; inspect selected content before any
external handoff. The snapshot is private local JSON containing exactly the
selected source text, commit/blob identities, content hashes and the declared
data policy. It is not a source-repository access grant or an execution attestation.

## Freeze the generation request

```sh
python3 -m personal_evals generation-request artifacts/source.json \
  --intent examples/generation-intent.json --out artifacts/request.json
```

The intent names the requested provider/model, suite decision and split, and
each task's ID, Harbor name/version, selected source paths, goal, grader
requirements, criticality, reward key and success threshold. The provider/model
in the example is a placeholder. No model is selected or called by this command.

Every selected source file must be requested by at least one task, and each task
must refer only to selected files. The request embeds the validated snapshot and
is self-contained. Its data policy is copied from the snapshot and cannot be
weakened. Its identity covers source bytes, metadata, goals and grading contract.
Treat source contents as untrusted data when using a model; this artifact format
does not make prompt injection impossible or establish semantic grounding.

The source snapshot/request/import path is versioned separately from existing
evaluation manifests. Preparing a request does not add a task to an active suite,
change a comparison threshold or claim a calibrated grader.

## Import a supplied response for review

A separately obtained response must use this exact local interchange shape:

```text
{schemaVersion:1,kind:'personal-evals-generated-tasks',requestId,snapshotId,model,
 tasks:[{id,sourcePaths,files:[{path,content}]}]}
```

Task IDs and source references must match the request. Task-array position is
not identity. Every instruction, TOML configuration, Dockerfile and verifier
must actually be supplied; the importer fabricates none of them. The response
cannot change owner-selected policies, thresholds, task names or versions.
Unknown fields, missing files, invalid paths, links, oversized content or a
different request/snapshot/model binding fail validation. This checks the
declared model string, not the identity of an external provider.

```sh
python3 -m personal_evals generation-import artifacts/request.json \
  --response path/to/response.json --out artifacts/draft
```

The new private draft contains ordinary task sources, owner-bound `suite.json`,
the request and `review.json` with status `review_required`. The existing suite
validator checks the actual emitted bytes and computes their proposed bundle
identity. No Harbor task, container, verifier or model is executed and no accepted
bundle is written by import.

Review the instructions, selected sources, hidden expected data, Dockerfile,
dependencies, verifier semantics and license/privacy suitability. File-format
validity does not prove a useful task, correct grader, authentic provider output
or permission to execute arbitrary task code.

## Accept explicitly after review

```sh
python3 -m personal_evals generation-accept artifacts/draft --reviewed \
  --out artifacts/accepted
python3 -m personal_evals verify artifacts/accepted
python3 -m personal_evals archive artifacts/accepted --out artifacts/accepted.zip
```

Acceptance requires the explicit owner review flag and rechecks request/review
identities and current draft bytes against the reviewed proposed bundle ID.
Tampering cannot reuse the original review receipt. Acceptance seals task source;
it does not execute it or certify its meaning. The local request/review records
retain repository provenance; the accepted task bundle excludes the repository
snapshot unless that material is explicitly included in its selected task files.
No private source is automatically published to GitHub.

All writes refuse existing outputs. These artifacts operate in trusted local
directories and do not claim protection against a hostile local process replacing
parent directories concurrently. The complete provider/repository-to-PR flow,
live framework acceptance and representative model-switch evidence remain open.
