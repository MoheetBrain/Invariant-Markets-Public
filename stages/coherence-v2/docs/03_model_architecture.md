# Model architecture

```text
YAML scenario
    ↓
typed config + provenance → shared macro state
    ↓
five-band startup outcomes → portfolio multiple/NAV
    ↓
principal-floor claim → 8×5 Monte Carlo grid → risk metrics
    ↓
results.json + summary.md + manifest.json + five figures
```

S2b-a adds a parallel empirical terminal path:

```text
source registry + empirical constraints
    ↓
derived mixture weights + tail beta + model-risk specifications
    ↓
terminal investor-level MOIC samples
    ↓
equal-weighted portfolio NAV → principal-floor claim
    ↓
validation residuals + sensitivity table + convergence + top-winner diagnostics
    ↓
S2b-a run artifacts
```

## Separation of concerns

- `core/` contains domain types, parameter provenance and pure mathematical identities.
- `macro/` owns systemic state sampling; it is shared rather than hidden inside a startup loop.
- `models/terminal/` contains the cheap synthetic reference model.
- `models/terminal/empirical_mixture.py` contains the S2b-a terminal marginal model.
- `calibration/` loads evidence, derives parameters, tracks uncertainty and writes S2b-a artifacts.
- `models/event_driven/` contains the minimal state machine and future cash-flow boundary.
- `models/historical_bootstrap/` refuses to run until documented empirical data exist.
- `protection/` keeps generic stop-loss arithmetic separate from founder-warrant value and names no legal wrapper.
- `risk/` calculates named portfolio and claim metrics.
- `reporting/` writes auditable run artifacts.

The five long-run concepts are `G` guarantee cost per £1 protected, `U` investor-capital uplift, `Q` founder equity/warrant requirement, `K` risk capital per £1 protected and `R` PlatformCo revenue per £1 protected. Version 1 estimates only terminal claim and prototype quantities supported by its assumptions; `U`, `K` and `R` are explicitly marked unsupported.

The rationale for these boundaries is recorded in the [architecture decision records](decisions/README.md), especially ADR-001 through ADR-005. Future architectural changes should add or amend an ADR rather than relying on undocumented intent.

ADR-006 records the S2b-a rule that empirical observations remain separate from
model parameters.
