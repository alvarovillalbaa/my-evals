# Local artifact contract v1

These are Personal Evals artifacts around Harbor, not new Harbor schemas.
The [owning brief](../spec.md) and [pinned framework contract](harbor.md) preserve
the product and runtime boundaries. Hashes identify exact local evidence, not
the honesty of its author or a provider attestation.

Repository snapshots and generation request/review artifacts have separate
contracts in the [Git reference](git.md) and [generation workflow](generation.md).
They feed explicitly reviewed task source into the bundle format below; they do
not change the meaning of an accepted evaluation manifest or activate a task.
Repository delivery plans have their own [delivery contract](delivery.md): they
embed the exact accepted bundle, destination/account/base metadata and sharing
consent. They do not include source snapshots or generation/review artifacts,
and preparing them performs no account lookup or remote publication.

## Explicit suite input

The suite is strict JSON: duplicate keys, non-finite numbers, surrogate Unicode,
unknown fields and numeric booleans are rejected. No output artifact contains
the original absolute source directory.

```text
{schemaVersion:1,id,version,split,
 decision:{question,minimumPairedTasks,minimumImprovement,maxCriticalRegressions},
 dataPolicy:{classification,permission,containsPersonalData},
 tasks:[{id,path,files,critical,rewardKey,successThreshold}]}
```

IDs/reward keys are bounded lowercase ASCII slugs. Versions and the question
are bounded nonempty text. `split` is validation, holdout or blind_holdout;
optimization/training is not implemented. Classification is authored/private,
permission is owned/authorized and personal-data presence is an explicit boolean.
This declaration is recorded, not independently established by the tool.

Tasks are ordered, uniquely identified selections. Their paths and selected
file paths are relative; links, traversal, nonregular inputs and secret filenames
are rejected. File contents can still contain sensitive information: the user
must select and review authorized content before exporting it.

The initial profile requires `task.toml`, `instruction.md`,
`environment/Dockerfile` and `tests/test.sh`; optional selected files can include
`README.md` and descendants of environment/tests/solution. It does not collect
ignored files, repository history, local settings or raw model trajectories.
Tasks must explicitly declare the pinned schema, `[task].name` and version.
At most 100 tasks, 100 files per task, 1 MiB per file and 32 MiB total are accepted.
These are deliberate product bounds, not Harbor-wide limits.

The decision specifies the minimum paired task count, practical mean reward
improvement and allowed critical regressions. Each task declares one numeric
reward in [0,1] and a success threshold. Harbor itself has no universal passing
threshold; these semantics belong to the sealed personal suite.

## Portable bundle and download

The output directory contains `bundle.json` and selected files under
`tasks/{id}/`. Its manifest contains:

```text
{schemaVersion:1,kind:'personal-evals-bundle',suite:{id,version},split,
 decision,dataPolicy,dataPolicyFingerprint,harbor,
 tasks:[{id,name,version,critical,rewardKey,successThreshold,harborDigest,
         files:[{path,sha256,bytes}]}],sampleManifestId,bundleId}
```

`dataPolicyFingerprint` hashes canonical policy JSON; `sampleManifestId` hashes
the exact ordered task records, including file/grader identities. `bundleId`
hashes the complete manifest except itself. Verification requires their exact
recomputation, exact file inventory and byte/hash/TOML correspondence. A changed
policy, grader, split, task order or decision cannot reuse the same bundle ID.

`harborDigest` is separately computed using the pinned framework's packager
algorithm over the exact emitted task files. It is not the suite hash or legacy
`task_checksum`. The downloadable ZIP preserves canonical manifest/files, stable
archive order/timestamps and private regular-file modes. Archive generation
rechecks bytes and refuses existing output. No archive extraction command is
implemented. Repository delivery is offline planning only; its authenticated
publisher remains an inactive proposal.

File reads/writes operate in explicitly selected trusted local directories.
They reject links and nonregular inputs at the checked boundaries, but do not
claim a sandbox against a hostile process concurrently replacing parent
directories. Source snapshots are per-file observations, not an atomic snapshot
of a changing repository. Freeze your selected inputs before sealing.

## Plans, imports and comparisons

Plans contain bundle/sample/policy IDs, an explicit requested model, agent/version,
attempt count and pinned Harbor source. The protocol identity covers all those
settings except the model being compared; the plan identity also covers the model.
Plans contain no credentials or local paths. Rendering a command requires
explicit runtime bundle/jobs paths and a job name and executes no process.

Imports project actual per-trial evidence with source result/lock hashes, stable
IDs, rewards, error types, reported model/provider and nullable observed usage/
duration. They exclude raw environment/configuration, private local paths,
exception messages, tracebacks and model reasoning. The importer requires the
admitted framework profile, task digest/version, job and model/agent bindings;
missing or unsupported provenance is rejected or excluded from comparison.

The normalized import has its own `runId`. Comparison validates those identities,
requires the same bundle and protocol, and joins task records by ID. Exactly the
planned number of valid attempts is needed for each paired task. Task means are
equally weighted; attempts are not incorrectly counted as independent tasks.
The report retains missing/excluded/error/extra/duplicate evidence and never
silently fills it with zeros.

Paired task deltas produce a mean effect and deterministic paired bootstrap 95%
percentile interval using 2,000 resamples, seeded from the evidence identities.
This describes uncertainty within the selected personal task sample; it is not
a guarantee for unseen populations or an unbiased post-selection experiment.
A supported-candidate decision requires complete clean coverage, sufficient
paired tasks, practical improvement, an interval above zero and the critical
regression limit. Otherwise the report is inconclusive or records a supported
regression; it never automatically promotes a model.
