# Explicit local Git source snapshots

The repository adapter reads only files the user names at one explicitly
selected committed revision. It does not collect the working tree, index,
untracked files, remotes or repository configuration into the artifact. It
does not check out files, initialize submodules, install Git, fetch, execute
filters, generate model output or submit a pull request. The broader
[provider/repository delivery requirement](../spec.md) remains binding.

## Primary contract

The local source-preparation environment reported Git `2.55.0`, ARM64, with
no build commit recorded. The matching official release documentation is
pinned to [`e9019fcafe0040228b8631c30f97ae1adb61bcdc`](https://github.com/git/git/commit/e9019fcafe0040228b8631c30f97ae1adb61bcdc).
That is a documentation/source pin, not an attestation of the installed
binary. No snapshot fixtures or new checks were executed during authoring.

Every Git invocation uses a direct argv vector and the global flags
`--no-pager --no-replace-objects --no-lazy-fetch --no-optional-locks
--literal-pathspecs`. The official [global option documentation](https://github.com/git/git/blob/e9019fcafe0040228b8631c30f97ae1adb61bcdc/Documentation/git.adoc#L177)
defines these protections. Unsupported Git versions fail rather than falling
back to a command that may fetch or reinterpret paths.

The subprocess environment is newly constructed. It does not inherit `GIT_*`
repository redirection, alternate-object-directory settings, injected config,
trace destinations or pathspec settings. It sets:

```text
GIT_NO_REPLACE_OBJECTS=1
GIT_NO_LAZY_FETCH=1
GIT_OPTIONAL_LOCKS=0
GIT_LITERAL_PATHSPECS=1
GIT_TERMINAL_PROMPT=0
GIT_ALLOW_PROTOCOL=
GIT_CONFIG_NOSYSTEM=1
GIT_CONFIG_GLOBAL=/dev/null
GIT_CONFIG_SYSTEM=/dev/null
```

The empty protocol allowlist denies transport protocols. Global/system config
is skipped; repository metadata/config remains necessary for Git to interpret
its own object store. Invocation-only settings disable fsmonitor and hooks;
they do not edit any configuration file. See Git's documentation for
[configuration and prompts](https://github.com/git/git/blob/e9019fcafe0040228b8631c30f97ae1adb61bcdc/Documentation/git.adoc#L758),
[replacement objects and lazy fetch](https://github.com/git/git/blob/e9019fcafe0040228b8631c30f97ae1adb61bcdc/Documentation/git.adoc#L924),
[protocols and optional locks](https://github.com/git/git/blob/e9019fcafe0040228b8631c30f97ae1adb61bcdc/Documentation/git.adoc#L986).
Optional-lock suppression does not make arbitrary Git commands read-only;
the adapter separately restricts the commands it issues.

## Commit and blob reads

1. Query repository metadata: storage object format, bare/worktree identity and
   root prefix. The explicit path must name a repository root, including a
   linked worktree or bare repository; an ordinary nested directory is rejected.
   These are metadata queries, not working-tree file or status scans.
2. Resolve the selected revision once using
   `rev-parse --verify --quiet --output-object-format=storage --end-of-options
   <revision>^{commit}`. Keep its complete lowercase commit ID. Later reads use
   that ID, so moving a branch cannot mix revisions within one snapshot.
3. For each selected path, request
   `ls-tree --full-tree -z -l <commit> -- <path>`. Require exactly one result,
   the exact requested UTF-8 path, `blob` type, ordinary file mode `100644` or
   `100755`, a complete object ID and an acceptable declared size. Directories,
   symlinks and submodule gitlinks are rejected.
4. Read bytes using `cat-file blob <object-id>`. This uses a validated object
   ID, rather than a user-controlled `revision:path` expression. It never adds
   `--filters`, `--textconv`, `--follow-symlinks` or mailmap transformations.
   Verify byte count and the Git object digest before exporting text.

Primary references: [revision verification and option separation](https://github.com/git/git/blob/e9019fcafe0040228b8631c30f97ae1adb61bcdc/Documentation/git-rev-parse.adoc#L109),
[storage object format](https://github.com/git/git/blob/e9019fcafe0040228b8631c30f97ae1adb61bcdc/Documentation/git-rev-parse.adoc#L327),
[tree output and NUL framing](https://github.com/git/git/blob/e9019fcafe0040228b8631c30f97ae1adb61bcdc/Documentation/git-ls-tree.adoc#L52),
and [raw object contents versus filters](https://github.com/git/git/blob/e9019fcafe0040228b8631c30f97ae1adb61bcdc/Documentation/git-cat-file.adoc#L57).

Each command has a 10-second deadline, bounded stdout and 16-KiB stderr.
The POSIX runner drains both pipes, creates an owned process session and kills
and reaps that owned process group on timeout or output overflow. It never
returns raw Git stderr, filenames, command arguments or private paths in an
error. This initial subprocess adapter supports POSIX; it does not claim
Windows pipe/process-group verification.

## Portable artifact and limits

`capture_repository` returns a `personal-evals-repository` schema-1 snapshot.
It contains a user-chosen lowercase slug label, full commit and object format,
explicit data policy and its fingerprint, and the selected file records in
input order. Each file records relative path, mode, Git blob ID, content SHA-256,
UTF-8 byte count and exact decoded content. No absolute repository path, branch
selector, remote URL or Git configuration is retained.

The limits are 64 files, 240 characters per path, 128 KiB per file, 1 MiB total
content and 4 MiB canonical snapshot JSON. Paths must be unique, including after
case folding. Traversal, backslashes, colons, glob syntax and control characters
are rejected. Explicit ordinary source such as `src/auth.py`, `src/tokens.py`
and `src/auth/route.py`, and benign configuration such as `.gitignore` and
`.github/workflows/test.yml`, remain selectable. The denylist rejects `.git`
metadata, `.env*`, known credential directories (`.ssh`, `.aws`, `.azure`,
`.kube`), credential/key material suffixes and obvious credential-data filenames
with data/config extensions or no extension. It is not a content-level secret
detector and does not prove that every other selected file is credential-free. The
user must review explicitly selected source and classify its permissions.
Content must be strict UTF-8 without control characters other than newline,
carriage return and tab. BOM, ordinary Unicode and CRLF bytes are preserved.
Binary blobs are not silently decoded. Git LFS pointer blobs remain pointers;
no external LFS content is downloaded or presented as captured source.

`validate_snapshot` performs no Git or provider IO. It reconstructs detached
records and verifies content length, SHA-256, policy identity, snapshot identity
and each blob ID using the declared SHA-1/SHA-256 hash of
`b"blob " + ASCII(byte_count) + b"\0" + raw_bytes`.
This follows Git's [object-header construction](https://github.com/git/git/blob/e9019fcafe0040228b8631c30f97ae1adb61bcdc/object-file.c#L90)
and [header/content hashing](https://github.com/git/git/blob/e9019fcafe0040228b8631c30f97ae1adb61bcdc/object-file.c#L315).
The metadata/hash format does not contain a full commit/tree membership proof
or signature. The native capture establishes membership through `ls-tree`;
standalone validation establishes artifact integrity, not authenticated
provenance or provider authorization. A generation-source handoff must retain
these identities and the explicit data policy without implying any model call.
