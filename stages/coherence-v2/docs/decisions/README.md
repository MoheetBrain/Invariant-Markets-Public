# Architecture decision records

These records capture decisions that shape the research system, the reasoning behind them, and the conditions under which they should be revisited. They are deliberately short enough to read during onboarding and specific enough to constrain future implementation.

| Record | Decision | Status |
|---|---|---|
| [ADR-001](ADR-001-python-is-primary.md) | Python is the primary implementation language for Version 1. | Accepted |
| [ADR-002](ADR-002-event-driven-simulation-is-primary.md) | Event-driven simulation is the long-run primary quantitative architecture. | Accepted |
| [ADR-003](ADR-003-legal-wrapper-excluded-from-core-mathematics.md) | Legal wrappers are excluded from core mathematics. | Accepted |
| [ADR-004](ADR-004-assumptions-require-provenance.md) | Important assumptions require explicit provenance. | Accepted |
| [ADR-005](ADR-005-separate-model-outputs-from-platformco-valuation.md) | Model outputs are separated from PlatformCo valuation. | Accepted |
| [ADR-006](ADR-006-observations-separate-from-parameters.md) | Empirical observations stay separate from model parameters. | Accepted |

The earlier `0001-economic-core-separate-from-legal-wrapper.md` is retained as the original short decision note; ADR-003 is the canonical expanded record.
