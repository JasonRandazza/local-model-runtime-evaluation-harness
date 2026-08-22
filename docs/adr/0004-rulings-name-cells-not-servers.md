# A ruling names a cell, never a server

A family's native diagonal runs a different quant on each server — Gemma 4 12B
is `jang_4m` on Osaurus, `oq4_fp16` on oMLX, and `optiq_4bit` on OptiQ, from
three different publishers. Stack and quant therefore vary together, so a
latency or quality gap between those cells cannot be attributed to the serving
runtime alone. A ruling says "serve `jang_4m` on Osaurus for this family"; it
must never say "Osaurus is faster than oMLX."

## Considered Options

- **Isolate the server effect.** Rejected: it needs the full cross-product that
  [ADR-0001](0001-native-diagonal.md) rules out, and a quant run on a server it
  was not built for measures the mismatch instead of the runtime.
- **Name a cell (chosen).** The cell is already the smallest thing that can be
  executed and measured, and it is what an operator actually serves. Nobody
  serves "oMLX"; they serve a specific quant on it.

## Consequences

The confound is invisible in the evidence: a reader who sees three latency
numbers will reach for "this runtime is faster" and be wrong. Any presentation
of a ruling therefore has to carry the cell identity, not just the server name.

The same claim shape holds for open mixes, where the candidates come from
different families — "of these, serve this cell" is true either way. Rulings
consume a comparison group and do not care whether that group is one family's
diagonal or a heterogeneous mix.
