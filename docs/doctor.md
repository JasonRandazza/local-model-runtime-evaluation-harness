# Offline Doctor

`lmre doctor` reports whether this machine's static local state is prepared
for a later live evaluation. It reads; it never writes, repairs, adopts,
downloads, executes, or contacts anything.

## Usage

```bash
./bin/lmre doctor
./bin/lmre doctor --format text
```

The default output is the managed CLI's JSON convention
(`{"ok": true, "diagnostic": ...}`); `--format text` prints a concise
checklist projection of the same structured result. `ok` means the
diagnostic completed — readiness lives in the separate
`overall_readiness` field. The command exits `0` whenever a complete
diagnostic is emitted, including one full of action items; a nonzero exit
means the invocation was malformed or the diagnostic itself failed.

## Vocabulary

| Status | Meaning |
| --- | --- |
| `OFFLINE_READY` | Every prerequisite this offline command may check passed. |
| `ACTION_REQUIRED` | A required local prerequisite is missing or invalid. |
| `WARNING` | A non-blocking condition deserves attention. Reserved: no current check emits it. |
| `NOT_CHECKED_LIVE` | The fact requires runtime, provider, credential, listener, process, memory, or inference contact and was deliberately not checked. |

`OFFLINE_READY` never means the machine is ready to run a live evaluation.
Endpoint reachability, provider inventory, process identity, credentials,
memory headroom, and actual model behavior are always `NOT_CHECKED_LIVE`
until a separately authorized live workflow observes them.

## What It Checks

1. **Harness** — supported Python version, the expected `bin/` command
   wrappers, and core operator documentation.
2. **Commands** — whether `osaurus`, `omlx`, and `optiq` are discoverable on
   `PATH`. They are never executed; versions and behavior stay unchecked.
3. **Machine profile** — the fixed `.lmre/machine-profile.json` through the
   same strict loader the managed path uses. A missing or invalid profile is
   reported with the copy-example remediation; the doctor never repairs it.
4. **Configuration** — active families, cells, campaigns, managed recipes,
   suites, preference/RAG mappings, RAG corpus, and overhead pairs through
   the existing parsers, including the native-triple cross-file agreement
   rule. One broken family fails closed without hiding the others.
5. **Artifacts** — the exact model artifact paths resolved from committed
   `{LMRE_ROOT:...}` templates and the validated profile: present, missing,
   broken symlink, or unreadable. No cache scanning, no sizes, no mutation.
6. **Policy** — the adopted standing policy record, its hash, and its
   expiry through the existing policy APIs. An absent or invalid record is a
   manual action; the example policy is a source for review, never
   auto-adopted.
7. **Family readiness** — one offline verdict per active family and managed
   recipe, with explicit reasons and the live qualifications above.
8. **Actions** — a deterministic, deduplicated list of manual next steps,
   each pointing at current documentation. Suggested commands are existing
   safe LMRE commands; the doctor never runs them.

## What It Deliberately Cannot Know

Whether runtimes are running or reachable, what providers expose, whether
credentials exist or work, current memory headroom, and whether any model
actually loads or answers. Those facts require live observation under
[managed-runs.md](managed-runs.md) and are always labeled
`NOT_CHECKED_LIVE`.

## Boundaries

No network or loopback contact, no subprocess execution, no port binding,
no process inspection, no Keychain access, no policy adoption or repair, no
plan or evidence creation, no model download or storage changes, and no
persisted snapshot — rerun the command for a fresh view.
