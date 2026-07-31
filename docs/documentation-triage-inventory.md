# Documentation Cleanup Record

## Vault Reconciliation

A vault-wide read-only scan covered filenames and standard-note bodies across
`00 System`, `01 Inbox`, `10 Wiki`, `20 Records`, `30 Sources`, and
`90 Archive`, plus Cursor attribution, recent vault Git history, governed
metadata, and UID duplication.

Sensitive note bodies, credentials, and generated/configuration directories
were excluded.

Result:

- no LMRE documentation was misplaced in the vault root, Inbox, Sources,
  unrelated projects, or Archive;
- Cursor-attributed LMRE writes are accounted for in the project Wiki, Tier 5
  records, Benchmark Coordinator templates, and dated activity notes;
- the July 24 North Star and Multi-Family Reopen records are correctly located;
- no duplicate LMRE UIDs were found;
- the full vault validator passed.

The problem was current-state drift and excess historical material, not missing
or floating documents.

## Repository Cleanup

The initial cleanup reduced the active repository around Discovery, Approach 3,
native matrix, preference, RAG, and overhead. A subsequent reconciliation made
the managed-run layer the normal live workflow and scoped those collector
documents to low-level or diagnostic use. The complete committed pre-cleanup
state was copied to the checksummed sibling archive before removal.

Current instruction precedence:

1. `AGENTS.md` defines repository safety and authority.
2. `docs/managed-runs.md` defines the normal live operator workflow.
3. `README.md`, `docs/status.md`, and `docs/architecture.md` describe the
   current product.
4. Collector guides describe their direct low-level CLIs.
5. Dated specs and evidence preserve context and results but grant no current
   authority.

Retained current documentation:

- `README.md`
- `AGENTS.md`
- `docs/status.md`
- `docs/architecture.md`
- `docs/managed-runs.md`
- `docs/history.md`
- `docs/discovery.md`
- `docs/matrix.md`
- `docs/preference.md`
- `docs/rag.md`
- `docs/overhead.md`
- current managed-run design and selected dated historical specs/evidence

Where retained historical wording differs from current instructions, the
precedence above controls.

Retired documentation, code, configuration, tests, manifests, and plugin source
remain recoverable from the sibling archive and Git history.
