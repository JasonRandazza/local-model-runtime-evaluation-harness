# Workspace root falls back to two levels above the package

Workspace-root resolution tries `LMRE_WORKSPACE`, then the nearest ancestor
holding a `.lmre-workspace` marker or a `config/managed-runs/` tree, then the
directory two levels above the package. That third rule looks like a
convenience default and is not: it is what makes a source checkout resolve
exactly as it did before workspaces existed.

## Consequences

Plan hashes and recorded `input_hashes` keys stay byte-identical across that
change, which is the only reason existing sealed runs remain comparable with
future ones. Anything that alters where a plan input resolves therefore breaks
comparability of already-sealed evidence — silently, since the runs still
execute fine. Consult the plan-hash gate in `docs/release-checklist.md` before
touching resolution order, marker discovery, or path constants derived from the
root.

`LMRE_WORKSPACE` set to a non-directory is a hard error rather than a fallback:
silently substituting another root would let a run record evidence against
configuration the operator never chose.
