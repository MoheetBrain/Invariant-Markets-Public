# ADR-005: Separate model outputs from PlatformCo valuation

- Status: Accepted
- Date: 2026-08-13
- Scope: Economic outputs, business valuation and product claims

## Context

The portfolio model can estimate quantities about terminal NAV, claims, reserve usage, warrant value and stop-loss payouts. PlatformCo valuation would additionally require fees, expenses, revenue persistence, investor demand, founder supply, risk-carrier pricing, capital requirements, operating costs and a valuation method. Those are not implied by a simulated claim distribution.

The long-run project reserves five concepts:

\[
G=\text{guarantee cost per £1 protected},\quad
U=\text{investor-capital uplift},\quad
Q=\text{founder equity/warrant requirement},
\]

\[
K=\text{risk capital per £1 protected},\quad
R=\text{PlatformCo revenue per £1 protected}.
\]

## Decision

Portfolio and protection-model outputs remain separate from PlatformCo valuation. The model may expose a supported economic quantity or a clearly labelled proxy, but it must not infer `U`, `K` or `R` from terminal portfolio results alone. Revenue, investor behaviour, founder behaviour, operating economics and valuation belong in separate modules and evidence plans.

## Why

Separating the layers prevents circular reasoning: a favourable simulated outcome cannot manufacture demand, revenue or enterprise value. It also allows an outside quant to validate the risk model independently of a commercial narrative.

## Consequences

- Current reports explicitly mark unsupported quantities rather than filling them with invented numbers.
- Expected claim or external payout is not automatically a guarantee price.
- PlatformCo valuation must use its own documented assumptions, cash-flow model and validation status.
- Interfaces can later connect the models, but the connection must be explicit and one-directional where possible.
- Commercial success is not evidence that the underlying risk model is calibrated, and model calibration is not evidence of commercial viability.

## Revisit when

Add a formal valuation layer only after validated fee schedules, expenses, demand/supply evidence, indicative risk-carrier terms and capital treatment are available. The separation should remain even then; integration is not a reason to collapse the boundaries.
