# ADR-002: Event-driven simulation is the primary long-run model

- Status: Accepted
- Date: 2026-08-13
- Scope: Quantitative model architecture

## Context

The terminal payoff depends on `NAV_T`, but startup portfolios generate value through time. Financing rounds, follow-on capital, dilution, competing failure and exit hazards, acquisitions, IPOs, liquidity, reserves and protection payouts are events with timing and state transitions. A terminal-only model cannot represent those mechanisms without hiding them inside opaque adjustment factors.

## Decision

The event-driven cash-flow simulator is the primary long-run quantitative architecture. The state machine must be able to represent:

```text
INITIAL → ACTIVE → FOLLOW_ON → ACTIVE → EXIT
INITIAL → ACTIVE → FAILURE
```

Model A, the terminal structural model, remains a cheap transparent benchmark. Model C, the historical bootstrap, remains an independent empirical robustness check. In Version 1, Model B is only the smallest working prototype; it does not claim to be the final actuarial simulator.

## Why

An event-driven design makes timing, cash-flow ownership, state-dependent hazards and protection-layer interactions explicit. It also creates natural seams for macro regimes and wrong-way risk. Keeping Models A and C independent prevents the primary model from becoming the only possible explanation of the data or from hiding implementation errors behind sophistication.

## Consequences

- Future features should enter through explicit events, transitions and cash flows rather than magic terminal multipliers.
- Model A must remain cheap enough to serve as a regression and analytical benchmark.
- Model C must not be implemented by reusing synthetic assumptions as if they were historical observations.
- Simulation APIs must accept explicit configurations and random generators; notebooks cannot become the source of truth.
- More realism will increase data and validation requirements, so the model must grow in small tested increments.

## Revisit when

Reconsider the primary architecture only if validated data show that event timing is immaterial to the decision being studied, or if an alternative model explains the same cash flows with demonstrably greater auditability and independent validation.
