# Authored live GitHub delivery and message repair

The real publisher created [draft PR #1](https://github.com/alvarovillalbaa/my-evals/pull/1)
for one explicitly authored format-demo bundle. All seven delivered files were
downloaded anonymously and matched the sealed bytes, including a binary fixture.
All 71 base files retained their exact Git objects, modes and sizes. The PR was
closed without merging; its SHA-checked fixture branch was deleted. Open and
closed/deleted-branch resume returned the same PR through GET requests only.

This accepts the **supervised approved-gh-tool transport profile**. The default
native `GhApi` child could not connect during read-only preflight and stays
unaccepted. The execution-context difference is unproven; no credentials,
account, permission, dependency, CI or network policy was changed to fix it.
The unmodified publisher used its existing `api` seam with an owned IPC adapter;
the approved CLI tool performed each actual request with its stored login.
Actual status/JSON, never fake responses, drove the publisher. The adapter had
no networking or credentials. Account/repository replies were projected to
the required fields; opaque HTTP error bodies supplied no success data.

## Real defect and exact repair

The original `f971eefa` runtime created the expected immutable tree/commit, then
returned `github_object_mismatch` before any branch or PR. GitHub's actual
commit response omitted the outgoing message's terminal newline. Author,
committer, timestamp, parent and tree matched. The observed original commit is
`a31ee951c6523610d17324deb2b6d95ec594634c` and remains unreferenced.

Only `_commit_payload` changed: send the same fixed message without its terminal
newline. `_verify_commit` remains literal; no trimming or relaxed identity
comparison was added. The repaired publisher SHA-256 is
`121445c2b29350cae4e4491e225fb551bfaa90b8fc1df0bba7899997d2e69130`.
The same plan and private journal resumed, skipped the seven verified blobs,
verified commit `2a1635d386f4cac82213d9967f30c060357fcea8`, then created exactly
one branch and one draft PR. Both immutable commits are retained, not claimed
deleted. This observation is a current GitHub profile, not a universal promise
about undocumented message normalization.

Three new authored T2 cases passed on existing CPython 3.14.7: the outgoing
contract, rejection of changed message content, and preservation of strict
tree/parent/authorship checks. Their direct tool observation is retained; raw
stdout/stderr were not separately captured. No old 128/20/51 suite was replayed.

## Delivery identity and retained outcomes

| Item | Exact identity |
| --- | --- |
| Repository / actor | `alvarovillalbaa/my-evals` ID 1437479976 / `alvarovillalbaa` ID 87529457 |
| Pinned base | `f971eefacccc0ad2da69a08c5eaaadbfdfb1fa6f` |
| Plan | `0156385d69c94c0374a27d54740e8d5d6401d806309ae552f8fe57a57b34281d` |
| Bundle | `eb993e5043e89cc62aeb51ad63ae1d2dd47957c4bb44be8e0bb129a5f59d0a77` |
| Delivery | seven files / 2,469 bytes under `evals/qualification-20261113-1` |
| Archive | 3,423 bytes; SHA-256 `dd20e7bbfebf8e2a2d18be45e51b3a93c88e3f95c9d04315f31ce71c950f45f2` |
| Actual delivery tree | `9195e94a98d84afc9f098e42d63c2ad8f15eefa1` (78 files, including the 71 unchanged base files) |
| Retired fixture branch | `qa/personal-evals-delivery-20261113-1`, last SHA `2a1635d3`, now absent |

Original failures remain: the binary was initially outside admitted task roots
and was moved unchanged to `environment/data.bin`; native preflight failed;
the original message readback failed; the first open resume received HTTP 503
on its first GET. A subsequent explicit resume of the same plan/journal passed.
The 503 was a read failure, with no uncertain write or new operation.

The 29 private journal events were validated locally, including their hash
chain and exactly one `branch_pending` and one `pr_pending`. Public evidence
contains event seals, not the raw private plan/journal. The 66 returned
supervised request observations are not a complete network-activity attestation:
earlier operator framing/connection attempts and unsuccessful generic connector
blob reads were not fully retained. Independent byte acceptance uses the seven
successful anonymous raw downloads and the separate GitHub tree/PR readbacks.

[Evidence and data-only verifier](github-delivery/) retain the authored archive,
safe reviewed-plan projection, source fingerprints, finite outcomes, request
observations, event seals and independent verification. The raw private plan,
journal and transient account/repository responses stay out of public source.
Five owned IPC directories (147 files / 130,862 bytes) were removed after their
fingerprints were sealed, all known publisher workers ended and a scoped lsof
read found no openers. The private plan and 29-event journal remain preserved.
This is scoped cleanup evidence, not every-process or host-wide attestation.

No Harbor/task/grader, provider/model, real personal evaluation, paid service,
browser, database or CI execution occurred. This does not prove native `GhApi`
connectivity, live task generation, semantic grader quality, Harbor performance,
every permission/race configuration, notification rollback or full-product
acceptance. It establishes this authored portable-bundle PR delivery profile.
