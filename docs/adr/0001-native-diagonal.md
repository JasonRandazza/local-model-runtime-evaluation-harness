# Each quant runs only on its native server

A benchmarking harness invites the full cross-product: every quant on every
runtime. We deliberately run the diagonal instead — each family exposes exactly
one cell per capable native server (Osaurus-native quant on Osaurus, oQ on
oMLX, OptiQ on OptiQ) — because a quant executed on a runtime it was not built
for measures the mismatch, not the runtime. Cross-server cells existed earlier
and are archived, not deleted.

## Considered Options

- **Full cross-product matrix.** Rejected: most cells measure conversion or
  compatibility overhead rather than the runtime under test, and the resulting
  numbers invite comparisons that aren't honest.
- **Native diagonal (chosen).** Fewer cells, every one of them comparable.

## Consequences

Cell identity is shared across discovery, matrix, preference, and RAG, so an
incompatible mix fails closed rather than producing plausible numbers. A
comparison class may append reviewed same-family native cells to a baseline,
but may never replace or reorder baseline cells, select cross-family cells, or
relax native-server validation.
