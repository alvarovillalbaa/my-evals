# Pinned Harbor integration

Personal Evals uses the real [Harbor framework](https://github.com/harbor-framework/harbor),
with this source contract pinned to commit
[`3095f96e5cc813783dc50c9c7970bc225fb7627b`](https://github.com/harbor-framework/harbor/commit/3095f96e5cc813783dc50c9c7970bc225fb7627b),
observed on 28 October 2026. No Harbor installation, container start, agent
installation or model/provider request is part of preparing a suite, rendering
a plan, or importing existing explicit files. Successful real framework
execution and provider/repository generation remain delivery work under the
[owning specification](../spec.md).

## Task format and content identity

The runtime's `TaskConfig.schema_version` defaults to `"1.4"`. It still accepts
the deprecated root `version` alias. The repository's task-configuration prose
currently says `"1.3"`; older standalone documentation may show `version="1.0"`.
The importer/exporter contract follows the pinned runtime, rather than treating
those examples as interchangeable. See
[TaskConfig](https://github.com/harbor-framework/harbor/blob/3095f96e5cc813783dc50c9c7970bc225fb7627b/src/harbor/models/task/config.py#L853)
and the [repository documentation](https://github.com/harbor-framework/harbor/blob/3095f96e5cc813783dc50c9c7970bc225fb7627b/docs-mintlify/tasks/configuration.mdx#L9).

The restricted `single-step-docker-v1` bundle contains `bundle.json` and
`tasks/<task-id>/` directories. Each selected task has:

```text
instruction.md
task.toml
environment/Dockerfile
tests/test.sh
solution/solve.sh          optional
README.md                 optional
```

Other explicitly selected files under `environment/`, `tests/` and `solution/`
are permitted by the suite reader. It excludes unlisted files, ignore files,
links and multi-step definitions. `task.toml` has explicit top-level
`schema_version="1.4"`, `[task].name` in `org/name` format and an explicit
nonempty `[task].version`. These are distinct schema and task versions. Task
resources and instructions are sealed content, not an implicit new resource
policy. See Harbor's [task layout and loader](https://github.com/harbor-framework/harbor/blob/3095f96e5cc813783dc50c9c7970bc225fb7627b/src/harbor/models/task/task.py#L34)
and [package metadata](https://github.com/harbor-framework/harbor/blob/3095f96e5cc813783dc50c9c7970bc225fb7627b/src/harbor/models/task/config.py#L289).

For this explicit selected-file profile, Harbor's content digest can be
reproduced with the Python standard library: sort task-relative POSIX paths;
for each file compute its SHA-256; then SHA-256 the concatenated UTF-8 records
`path + NUL + lowercase-file-hash + newline`. Store the result as
`sha256:<64 lowercase hex>`. The selected file set and bytes are already sealed
by `bundle.json`. This implements the pinned
[Packager selection and hashing](https://github.com/harbor-framework/harbor/blob/3095f96e5cc813783dc50c9c7970bc225fb7627b/src/harbor/publisher/packager.py#L29),
without attempting general gitignore or package-registry compatibility.

Do not compare that digest with `TrialResult.task_checksum`: the latter uses
the older directory-hash implementation and is deprecated. The durable
digest and declared task version are in the trial's `lock.json`, built using
`Packager` for local tasks. See the [checksum warning](https://github.com/harbor-framework/harbor/blob/3095f96e5cc813783dc50c9c7970bc225fb7627b/src/harbor/models/task/task.py#L245)
and [lock construction](https://github.com/harbor-framework/harbor/blob/3095f96e5cc813783dc50c9c7970bc225fb7627b/src/harbor/models/job/lock.py#L597).

## Restricted run protocol

A plan records the sealed suite/data/decision identities, requested literal
`provider/model`, attempt count, agent name/version and Harbor source commit.
It never starts a subprocess. The separately rendered argv targets real
`harbor run --path <bundle>/tasks`, Docker, concurrency one, the explicit
attempt count, zero retries and explicit output directory/job name.
The `run` command is an [alias for job start](https://github.com/harbor-framework/harbor/blob/3095f96e5cc813783dc50c9c7970bc225fb7627b/src/harbor/cli/main.py#L171).
Relevant flags are in [CLI job configuration](https://github.com/harbor-framework/harbor/blob/3095f96e5cc813783dc50c9c7970bc225fb7627b/src/harbor/cli/jobs.py#L428).

The two source-verified adapters are:

- `codex`: the rendered command adds `--agent-kwarg version=<declared-version>`.
  The value is JSON-quoted so Harbor's kwargs parser preserves a string. Only
  explicit numeric release versions (optionally prefixed `v` or suffixed with
  a prerelease) are admitted; mutable tags such as `latest` cannot freeze an
  installed agent, because Harbor reports the requested version string.
  Both trial config and lock must record exactly that kwargs map; the reported
  agent version must match. The installed base accepts and reports the version,
  and Codex uses it in its installation package spec. See the
  [base constructor](https://github.com/harbor-framework/harbor/blob/3095f96e5cc813783dc50c9c7970bc225fb7627b/src/harbor/agents/installed/base.py#L643)
  and [Codex setup](https://github.com/harbor-framework/harbor/blob/3095f96e5cc813783dc50c9c7970bc225fb7627b/src/harbor/agents/installed/codex.py#L633).
- `terminus-2`: the provider-neutral built-in adapter reports version `2.0.0`
  at this source pin. Its command has no invented version kwarg and both config
  and lock require empty kwargs. See the [provider connection specification](https://github.com/harbor-framework/harbor/blob/3095f96e5cc813783dc50c9c7970bc225fb7627b/src/harbor/agents/terminus_2/terminus_2.py#L194)
  and [version method](https://github.com/harbor-framework/harbor/blob/3095f96e5cc813783dc50c9c7970bc225fb7627b/src/harbor/agents/terminus_2/terminus_2.py#L574).

Recorded model identity must either equal the requested literal with an unknown
provider, or match its exact provider/name pair. A bare model name with an
unknown provider does not establish a qualified request. The original-literal
fallback is the actual [Harbor parser behavior](https://github.com/harbor-framework/harbor/blob/3095f96e5cc813783dc50c9c7970bc225fb7627b/src/harbor/agents/agent_auth_resolution.py#L320);
provider aliases are not silently treated as equivalent.

The importer admits only the pinned defaults for trial-level runtime options:
timeout multiplier one; no timeout/resource overrides, extra instructions,
skills, MCP servers, custom kwargs, extra environment values, mounts, compose
overlays, simulated user, loaded trajectories, install-only or regrade.
Docker lifecycle defaults are `force_build=false`, `delete=true`, `stream=false`
and CPU/memory enforcement `auto`. Verification must be enabled and shared;
unknown or changed runtime fields exclude the trial. These restrictions concern
run overrides: the task's own selected settings remain covered by its digest.
The field/default owner is [TrialConfig and its nested records](https://github.com/harbor-framework/harbor/blob/3095f96e5cc813783dc50c9c7970bc225fb7627b/src/harbor/models/trial/config.py#L65).

## Import evidence and limits

Import an explicit local job directory with root `result.json`, root
`lock.json`, and immediate child trial directories containing their own
`result.json` and `lock.json`. The final root result normally **omits**
`trial_results`; its aggregate statistics do not replace trial evidence.
See the [final writer](https://github.com/harbor-framework/harbor/blob/3095f96e5cc813783dc50c9c7970bc225fb7627b/src/harbor/job.py#L1206)
and [individual trial writer](https://github.com/harbor-framework/harbor/blob/3095f96e5cc813783dc50c9c7970bc225fb7627b/src/harbor/trial/trial.py#L666).

The importer bounds raw JSON files to 2 MiB and trial directories to 2,000.
It opens directory/file descriptors without following links. Root provenance
requires job-lock schema 3, the pinned Harbor commit and a recorded framework
version, concurrency one and zero retries. Each trial requires schema-2 lock
membership in that root lock, the sealed task digest/version/local directory
name, matching declared package task name, matching job ID, requested model
literal and reported agent/version. Local dataset source is `tasks`, as emitted
from the rendered bundle path. UUIDs must be unique across all trials.
Missing or mismatched trial provenance remains excluded; it cannot become a
valid score through matching names alone. See [lock records](https://github.com/harbor-framework/harbor/blob/3095f96e5cc813783dc50c9c7970bc225fb7627b/src/harbor/models/job/lock.py#L60)
and [local dataset task source](https://github.com/harbor-framework/harbor/blob/3095f96e5cc813783dc50c9c7970bc225fb7627b/src/harbor/models/job/config.py#L187).

Only the suite's selected reward key is projected, as a finite value in `[0,1]`.
Harbor itself supports arbitrary numeric labeled metrics: `reward.txt` becomes
the `reward` key, while `reward.json` supplies a map. A selected suite threshold
defines success; the importer invents no universal pass threshold. Missing or
invalid rewards are null. Trial and step error types are retained with their
stage, while messages and tracebacks are discarded. All errored trials are
excluded from this restricted comparison, even if a numeric reward exists;
this is a conservative Personal Evals rule, not a claim to reproduce every
Harbor failure/aggregation policy. See the [reward parser](https://github.com/harbor-framework/harbor/blob/3095f96e5cc813783dc50c9c7970bc225fb7627b/src/harbor/verifier/verifier.py#L69)
and [trial error/reward semantics](https://github.com/harbor-framework/harbor/blob/3095f96e5cc813783dc50c9c7970bc225fb7627b/src/harbor/models/trial/result.py#L104).

Usage comes from `agent_result`, or step contexts when the former is absent,
never both. Input tokens already include cached tokens. Missing measurements
stay null; partial contributing usage is not presented as a complete total.
Cost is reported agent cost, without price lookup or invoice reconciliation.
Duration uses timezone-aware trial start/finish values and excludes invalid,
reversed or incomplete times; naive job timestamps are not silently made UTC.
See [usage fields](https://github.com/harbor-framework/harbor/blob/3095f96e5cc813783dc50c9c7970bc225fb7627b/src/harbor/models/agent/context.py#L21)
and [context selection](https://github.com/harbor-framework/harbor/blob/3095f96e5cc813783dc50c9c7970bc225fb7627b/src/harbor/models/trial/result.py#L130).

The normalized report keeps plan/suite IDs, safe model/agent metadata, rewards,
exclusion codes, error types, measurements and input-file SHA-256 hashes. It
does not retain absolute paths, URIs, environment values, arbitrary agent
metadata, raw trajectories or exception text. Imported files and recorded
metadata are not signed execution attestations: these checks establish the
restricted file/protocol correspondence, not that Harbor actually ran, that a
provider honored a model name, or that an authored fixture measures a model.
