---
status: accepted
---

# MXFP quantization is retired

Operator decision, 2026-08-07: MXFP is no longer selectable in any active
family, cell, campaign, suite map, open mix, or comparison class. It ran far
longer than the Gemma and Ornith lanes and did not produce correct comparable
results, so its cells cost disproportionate wall-clock while yielding evidence
that could not be set beside the others. For the `qwen36-35b-a3b` family the
Osaurus-native cell is `qwen_jangtq4__osaurus`; there is no MXFP replacement to
propose.

## Consequences

Retirement means "not selectable for future runs", never "erase the record".
The sealed MXFP failure evidence stays preserved and must not be deleted,
retroactively sealed, or reinterpreted — it is the justification for this
decision and the answer to anyone who proposes retrying MXFP.

Removing MXFP model weights from disk and removing an MXFP entry from an
Osaurus provider are operator actions outside agent authority: report them,
never perform them.
