# ADR-007: Treat selection skill as a hypothetical sensitivity

- Status: Accepted
- Date: 2026-08-14
- Scope: S2b-a.1 underwriting-selection experiments

## Context

Invariant Markets proposes to select companies rather than sample randomly from
the venture universe. The repository has aggregate terminal-return constraints,
but no timestamped selected/rejected underwriting dataset. A better simulated
selected marginal can therefore identify required skill, but cannot demonstrate
that the skill exists.

## Decision

Selection is implemented only through two explicit sensitivity instruments:
target-constrained probability reallocation and a monotone exponential tilt.
Both are labelled `HYPOTHETICAL_SELECTION_SKILL` or
`MODEL_RISK_SCENARIO`. Neither may be labelled fitted or calibrated.

Any future empirical underwriting model must estimate outcomes conditional only
on information available at the investment decision date. Future funding,
eventual revenue, exit status and exit valuation are prohibited as selection
features unless they were genuinely known at that date.

## Consequences

- The model may invert guarantee targets to required selection quality.
- It may not claim that Invariant can achieve that quality.
- Selected and rejected opportunities must both be retained for backtesting.
- Selection benefit and sector-concentration cost must be reported separately.
- A favourable selected scenario is not evidence of founder supply, investor
  demand, a risk-carrier price or PlatformCo value.

## Revisit when

Revisit after a versioned, out-of-sample underwriting backtest links timestamped
investment-time information and decisions to investor-level terminal or
censored MOIC with documented inclusion and censoring rules.
