# Volatile upstream runtime defaults are pinned to fixed values

Three upstream defaults shipped by OptiQ and oMLX now silently change what this
harness measures. The harness exists to produce comparable numbers across
runtimes; a default that varies by machine or by disk warmth destroys that.
Each is pinned to a fixed value that is independent of the host.

OptiQ's `--max-context` defaults to `auto`, which engages a memory-safe KV cap
only when the model's full native context would not fit in RAM. That makes the
KV budget machine-dependent: the same cell yields different results on a 64GB
versus a 32GB Mac with nothing in the artifact explaining why. It is pinned to
`8192`, comfortably above the largest suite prompt and every workload's
`max_tokens` cap, while remaining a fixed, reproducible budget.

oMLX's `--max-concurrent-requests` defaults to 8, `--memory-guard` is a tiered
RAM-dependent setting (`off|safe|balanced|aggressive`), and a paged SSD cache is
on by default. All three move TTFT and throughput. They are pinned to
`--max-concurrent-requests 1` (the suites are sequential), `--memory-guard off`
(the tiered guard is the same class of RAM-dependent bug as `--max-context
auto`), and `--no-cache` (the paged cache makes TTFT depend on disk warmth across
runs, corrupting the metric the harness exists to measure).

## Consequences

Pinning these defaults changes the cell configs. Runs planned before this
change read `INCOMPARABLE` against runs planned after -- that is correct and
intended, because the measurement genuinely changed. The sealed evidence is
preserved; only the meaning of future plans is altered.

The optiq adapter's `validate_start_command` expected tuple and the three optiq
cell configs must stay in exact sync, as must the oMLX checks and its three cell
configs. Osaurus has no comparable knob and is left untouched.
