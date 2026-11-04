# Offline delivery-plan checks — passed

4 November 2026. **20/20 passed**, with no failures, errors or skips, from one invocation of the existing Python runtime. The [JSON receipt](delivery-plan-checks.json) retains all 20 actual test IDs/statuses, complete bounded stdout/stderr, their byte hashes and all 43 source fingerprints.

- Checked source: `d031a159d0baead0a5bac7f38e777f4e1bd03e5f`; working tree clean before and after the test.
- Command: `PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest -v tests.unit.test_delivery`.
- Actual runtime: CPython **3.14.7**, macOS (`darwin`); executable display uses the portable basename `python3`.
- Unittest reported **1.046 seconds**; supervised child duration **1.476 seconds**, exit **0**. This is a functional fixture run, not a performance benchmark.
- [Historical seal](../10-28/delivery-source.json): **43 inputs / 378,591 bytes**; SHA-256 `2952c26017548c2bb9d921fb4ac1dd963606e6ad7369baaf36bbf794659035c4`. All sealed bytes and captured executable modes matched before and after; the historical seal was unchanged.

The selected [proposal subset](../../../proposals/github-publisher.md) checks binary-safe offline bundle plans, exact identities and consent, malformed/altered content, path and inventory collisions, detached validation, private exclusive output, source-change fencing and bounded failure cleanup. Its authored fixtures exercise actual local planner/validator source; no task code is executed.

The child had a **120-second cap**, 128 KiB per-stream caps, bytecode disabled and a fresh owned private temporary root. It received only the six documented Python/temp/time environment variables. No timeout, interruption, forced kill or truncation occurred. The child was reaped, its process group was gone, all fixture directories had already been cleaned, and the identity-checked parent root was removed. Stdout was empty; stderr was 3,847 bytes, SHA-256 `9e3d4c46ed0cd468611d54e5a85640b3a541dec59496114c5f5afd8a9c080ed6`.

The authenticated publisher and its 24 proposed cases remain inactive; the CLI activation patch was not applied. The earlier 76 and 52 scopes remain separate. No installation, CI, server/browser/database, Harbor/container, model/provider, real account lookup or remote delivery was involved. These fixtures do not establish live GitHub/PR acceptance, authentic model output or full product completion.

Only these two result files were written. No source repair, commit or publication was performed; the historical seal and source files remain intact.
