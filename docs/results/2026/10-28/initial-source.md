# Personal Evals initial source

Date: 2026-10-28. Status: authored local CLI source; focused runtime checks
pending separate approval. This is progress toward the full product, not its
completion.

## Ownership and source work

The [owning Notion brief](https://app.notion.com/p/3a5a1ee8bd0680bfb9a0fe37dfa1790a)
was fetched in full; the returned 19 October snapshot is unverified and has no
omitted blocks. Direct requirements are portable personal evals for model/provider
switching, Harbor and provider/repo generation with download/PR delivery. The
coding-harness wording remains a question. Bounded personal repository searches,
direct candidate checks and immediate local directory inventory found no
dedicated owner; OpenEvals was preserved as a separate product.

Implemented source:

- Explicit selected-file suite preparation, stable ordered task/file/grader
  identities, policy/decision fingerprints, actual-byte portable bundles and
  strict verification. No implicit repository/private-directory scan.
- Deterministic downloadable ZIP output and private exclusive local JSON
  publication. Existing outputs are preserved; cleanup removes owned files.
- Real Harbor run-plan/argv preparation without process execution. The source
  admits provider-neutral Terminus2 and explicitly versioned Codex adapters.
- Pinned per-trial result/lock import with durable task digest/version, run/job,
  agent/model and workload-profile checks. Raw configs, local paths, credentials,
  exception messages, traces and hidden model reasoning are not projected.
- Task-ID-paired comparison, complete-attempt and provenance gates, missing/error
  coverage, nullable observed metrics, paired bootstrap uncertainty and explicit
  inconclusive outcomes. It does not synthesize results or promote a model.

The [artifact contract](../../../references/formats.md) records schema and
scientific/operational limits. The [framework reference](../../../references/harbor.md)
pins authoritative Harbor source at
`3095f96e5cc813783dc50c9c7970bc225fb7627b`. Runtime code, rather than lagging
prose, defines the admitted task schema and import profile.

Source review corrected concrete contract risks before publication: Harbor job
aggregates omit trials; task_checksum differs from durable package digest; default
ignored files must not enter the advertised digest; legacy schema aliases can
override the explicit version; nullable reported provider identity is distinct
from a guessed provider; partial step usage is not a complete cost; and agent
versions require adapter-specific handling. No installed framework was invoked
to obtain this source evidence.

## Verification boundary

The source-only check parses Python AST, checks relative imports/local Markdown
links and reads the example JSON/TOML as data. It does not import product modules,
run the task grader, create a container or execute a test. Final static counts
were 18 Python modules and 19 local Markdown links, with no unresolved references.
The existing Python `3.14.7` executable and version were captured in the same
repository process; machine-local paths are excluded from committed evidence.
Whitespace checks covered all new files. The [source manifest](source-manifest.json)
records the exact source/test/example hashes for the proposed run. Publication
is verified separately after committing the frozen source.

The [focused proposal](../../../proposals/local-checks.md) scopes **76 authored
unexecuted cases** (20 suite, 20 importer, 20 comparison, 16 local/CLI). Runtime
execution needs separate approval under the supplied verification rules.

## Remaining delivery requirements

Real Harbor installation/execution and a framework/task/container round trip are
unverified. No provider, agent credential, model call, benchmark outcome, measured
cost or actual model-switch recommendation is claimed. Provider/repository-driven
generation, review/activation of generated evals, repository revision connection
and authorized PR delivery remain unimplemented. An authored example is a format
demonstration, not a representative personal benchmark.

This local CLI slice has no web server, shared database or Auth service, so
Vercel/Supabase provisioning is not necessary for its runtime. No dependency,
provider/CI/production configuration, migration, plan change or paid enrollment
was made. The complete portfolio goal and the [full product contract](../../../spec.md)
remain active.
