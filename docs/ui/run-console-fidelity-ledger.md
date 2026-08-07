# Run Console Fidelity Ledger

The functional concept established information hierarchy and safety emphasis;
the implementation preserves those priorities while simplifying the first
slice to server-rendered HTML.

| Comparison point | Concept intent | Implemented result |
| --- | --- | --- |
| Plan navigation | Persistent plan rail with selected state | Scroll-bounded desktop rail and compact mobile rail over existing immutable plans |
| Immutable identity | Plan facts remain central and readable | Bound hash, scope, family/open mix, recipe, policy, duration, request count, and runtimes are shown without reinterpretation |
| Live authority | Exact-plan authorization is visually separate | Start/resume form appears only when evidence permits it and requires the full hash plus acknowledgement |
| Progress | Stage state is visible at a glance | Existing persisted steps and attempt numbers are rendered as an honest status table |
| Lifecycle | Ownership and terminal action are explicit | Recorded attached/owned/reclaimed leases and terminal actions remain visible |
| Safety notice | Reclaim behavior is adjacent to actions | The 60-second notice and manual provider-reconnect boundary are shown before live authorization |
| Responsive behavior | Dense desktop workspace remains understandable | Two-column desktop layout collapses to a scroll-bounded plan rail and single-column detail on phone widths |
| Visual treatment | Calm, restrained operational interface | Native system typography, high-contrast status color, rules, and focus states; no decorative motion or JavaScript |

Deferred visual features from the concept are search/filter controls,
derived readiness rows, icons, and a richer progress summary. They are not
required for the functional safety contract and should not be added until a
separate bounded slice defines their evidence semantics.
