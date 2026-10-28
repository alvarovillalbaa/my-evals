# Personal Evals: owning brief and delivery contract

The [Notion child brief](https://app.notion.com/p/3a5a1ee8bd0680bfb9a0fe37dfa1790a)
was fetched in full on 28 October 2026. The connector returned an unverified
19 October snapshot, without omitted blocks. It directly asks for portable,
personal evals to compare changing models/providers, use of Harbor, and a
provider/repository connection to evaluation generation and download/PR delivery.
The coding-harness wording is a question, not a settled product requirement.

The existing personal OpenEvals product is not substituted for this brief.
Bounded connected-account searches and direct candidate repository checks found
no dedicated My Evals owner; this repository begins that separate source.

## Required outcome

| Requirement | Evidence required for completion |
| --- | --- |
| Portable personal evals | An immutable, exportable suite preserving task/grader/file versions, data policy, split and task IDs; accepted import after transfer |
| Compare switching model/provider | Matched complete actual results on the same sealed suite and run protocol; paired effects, uncertainty, critical regressions and explicit inconclusive decisions |
| Use Harbor | Real pinned Harbor task format and actual run-result contracts; successful approved framework execution, not a replacement harness |
| Provider/repository connection and generation | Explicit source selection and provider authorization, grounded generated tasks reviewed before activation, reproducible repository revision and no secret leakage |
| Download/PR delivery | A verifiable portable download plus authorized delivery to the selected repository; no automatic publication of private tasks |
| Coding-harness use | Owner decision remains open; do not impose a coding-only product identity |

The initial implementation covers local suite sealing, framework run planning
and evidence comparison/import. Its subsequent repository handoff captures
committed selected source, freezes a generation request, validates supplied task
files and requires owner review before sealing. This is not completion of the
live provider/repository generation or PR flow. No model result is fabricated
and no live account, container, framework execution or deployment is implied by
source publication.

## Evaluation decision

The user must choose a representative task population and state the model-switch
question before collecting results. They set the practical improvement, minimum
paired-task count, critical tasks and required success thresholds in the sealed
suite. Training/validation/holdout roles are explicit. A small authored example
is a format demonstration, not a personal benchmark or evidence for a model.

Comparison must preserve missing coverage, errors, task versions and run settings.
Do not average incompatible workloads, replace missing/error rewards with zero,
select a winner from unpaired samples or infer a population-wide improvement
from a narrow personal sample. This product does not automatically promote a
model or rewrite graders/thresholds after results are known.

## Operational limits

Only explicit bounded local files and committed selected Git blobs are read.
No repository scan, remote fetch, provider call, hidden model reasoning, account
connection or credential discovery is implicit. No paid service or provider run
is authorized by this source work.
Harbor/container installation and execution require their own reviewed scope.
There is no web service, database or shared Auth need for the initial local CLI;
Vercel/Supabase provisioning would add no runtime capability to this slice.
