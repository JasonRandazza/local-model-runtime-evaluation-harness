# A rubric gates on constraints, then orders on one metric

A rubric names the quality floors a cell must clear — RAG fact hits, preference
losses — and then the single metric that orders whatever clears them, normally
p50 total latency. It does not normalize the collected metrics into a weighted
score.

## Considered Options

- **Weighted scalar score.** Rejected: combining seconds, judged pairwise wins,
  and fact-hit fractions requires a normalization step that is itself an
  arbitrary judgment, and it is invisible in the result. The output is a number
  with decimal places that looks measured and is not — the same dishonesty this
  project refuses in `N/A`, `INCOMPARABLE`, and the browser's refusal to derive
  scores.
- **Pareto frontier.** Rejected: it is the most honest of the three and decides
  nothing, which leaves the judgment where it already is — in the operator's
  head.
- **Constraint then order (chosen).** Reads as a sentence, survives being
  disagreed with, and fails honestly.

## Consequences

When no cell clears the floors, the ruling reports that none qualify. It does
not fall back to the least-bad candidate; a rubric that cannot be satisfied is
information, not an error.
