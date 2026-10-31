# Assumptions register

Every value driving the S2a baseline is synthetic and has `SCENARIO` provenance in `configs/base.yaml`. The values below are architecture-test inputs, not empirical estimates.

| ID | Assumption | Baseline value | Sensitivity | Validation plan |
|---|---|---:|---|---|
| A-001 | Reporting principal `K` | £1,000,000 | Absolute outputs only; per-unit metrics are scale invariant | Replace with product-specific cash-flow scale. |
| A-002 | Horizon | 10 years | High once timing enters Model B | Align to product and cohort data. |
| A-003 | Monte Carlo paths | 5,000 per portfolio size | Numerical precision | Report Monte Carlo error and convergence. |
| A-004 | Random seed | 42 | Draw-specific, not distributional | Retain seeded regression runs and multi-seed robustness checks. |
| A-005 | Portfolio sizes | 1, 10, 50, 100, 250, 500, 1,000, 2,500 | Very high | Compare with feasible portfolio construction. |
| A-006 | Protection fractions | 0%, 25%, 50%, 75%, 100% | Very high | Compare with candidate product terms. |
| A-007 | Equal initial investment weights | Yes | High | Add documented ownership and allocation rules. |
| A-008 | Shared portfolio macro state probabilities | NORMAL 70%, WEAK 25%, CRISIS 5% | Very high | Estimate vintage/macro dependence from historical cohorts. |
| A-009 | Outcome within each non-degenerate band | Uniform | High, especially tail severity | Fit candidate conditional distributions with uncertainty. |
| A-010 | NORMAL outcome probabilities | 55%, 15%, 22%, 7%, 1% | Very high | Estimate from versioned cohort data. |
| A-011 | NORMAL return ranges | 0x; 0.2–0.8x; 1.2–3.5x; 6–15x; 25–60x | Very high | Fit censored realized and unrealized outcomes. |
| A-012 | WEAK outcome probabilities | 70%, 16%, 11%, 2.5%, 0.5% | Very high | Estimate conditional on defined weak regimes. |
| A-013 | WEAK return ranges | 0x; 0.1–0.6x; 1–2.5x; 5–10x; 22–40x | Very high | Fit censored outcomes by regime. |
| A-014 | CRISIS outcome probabilities | 85%, 10%, 4.5%, 0.4%, 0.1% | Very high | Estimate conditional on defined crisis regimes. |
| A-015 | CRISIS return ranges | 0x; 0.05–0.4x; 1–1.8x; 5–8x; 21–30x | Very high | Fit censored outcomes by regime. |
| A-016 | Conditional startup draws are independent given the shared state | Yes | High | Test residual dependence and sector/vintage clustering. |
| A-017 | Initial founder warrant `q_0` | 2% | High | Obtain actual founder terms and supply evidence. |
| A-018 | Financing rounds and equal dilution | 3 rounds, 20% per round | High | Replace with event-level financing and dilution data. |
| A-019 | Terminal warrant fraction | `2% × (1−20%)³ = 1.024%` | Derived identity | Verify arithmetic; validate economics separately. |
| A-020 | Generic stop-loss attachment and limit | 5% and 35% of `K` | Very high | Obtain indicative provider terms without assuming a wrapper. |
| A-021 | Warrant value is not liquid claim support | Kept separate | Critical boundary | Add liquidity/timing only with evidence. |
| A-022 | Event-prototype follow-on/exit probabilities | NORMAL 35%/25%; WEAK 25%/15%; CRISIS 10%/8% | High for Model B only | Fit competing hazards to event histories. |
| A-023 | Largest-investment concentration conditions on positive NAV | Wipeout paths excluded; all-wipeout result is zero | Medium | Revisit alongside formal concentration reporting. |

The five outcome probabilities in each macro state are ordered as total failure, partial recovery, modest success, large success and extreme winner. Configuration validation requires each state to sum to one and enforces the declared band boundaries.

## S2b-a empirical terminal marginal assumptions

S2b-a does not overwrite the S2a assumptions above. It adds a separate empirical
terminal mixture whose observations and parameters are intentionally separated.

| ID | Assumption | Baseline value | Provenance | Validation plan |
|---|---|---:|---|---|
| E-001 | Aggregate `P(X<1x)` threshold | 65% | `OBSERVED_AGGREGATE` | Compare simulated marginal with tolerance; audit unit of observation. |
| E-002 | Aggregate `P(X>=5x)` threshold | 10% | `OBSERVED_AGGREGATE` | Compare simulated marginal with tolerance. |
| E-003 | Aggregate `P(X>=10x)` threshold | 4% | `OBSERVED_AGGREGATE` | Tail threshold and validation target. |
| E-004 | Aggregate `P(X>=50x)` threshold | 0.4% | `OBSERVED_AGGREGATE` | Derive beta and report residuals under tail variants. |
| E-005 | Complete-loss split inside `<1x` mass | 39% | `PROXY` | Report residual against older partial-loss decomposition. |
| E-006 | Tail survival exponent beta | 1.4307 | `CALIBRATED` | Test Pareto convention and sensitivity to beta 1.1, 1.3 and 1.6. |
| E-007 | Body model | log-uniform baseline | `MODEL_RISK_SCENARIO` | Compare with truncated lognormal. |
| E-008 | Tail cap | 1000x baseline | `MODEL_RISK_SCENARIO` | Compare with unbounded, 500x capped, truncated and no-mega stresses. |
| E-009 | Correlation rho | 0 baseline | `MODEL_RISK_SCENARIO` | Compare Gaussian factor rho values and Student-t stress. |
| E-010 | Carta priced-round dilution medians | Seed 20.5%, Series A 20.1% | `OBSERVED_AGGREGATE` | Use deterministic medians only; do not infer a full distribution. |

Founder proceeds, company exit-value exponents, fund TVPI and financing
transitions are not used as investor-level terminal return parameters.

## S2b-a.1 coherence and dependence assumptions

S2b-a.1 preserves every frozen V1 input above. Its additional values are
model-risk experiment coordinates, not new empirical calibrations.

| ID | Assumption | Value | Provenance | Validation plan |
|---|---|---:|---|---|
| E-011 | Principal Gaussian latent rho grid | 0.00–0.40 by 0.01 | `MODEL_RISK_SCENARIO` | Replace with company-level cohort dependence estimates. |
| E-012 | Frontier final path count | 100,000 for all N=100/rho rows | `NUMERICAL_CONTROL` | Retain MCSE and ES-tail counts; refine larger N near decisions. |
| E-013 | Larger-N screening paths | 5,000 | `NUMERICAL_CONTROL` | Treat breakpoints as screening estimates until refined. |
| E-014 | Unique-company winner-mass scale | 0.75 proxy | `MODEL_RISK_PROXY_NOT_ESTIMATED` | Estimate only from a round-to-company map. |
| E-015 | Winner-duplication stress scale | 0.50 proxy | `MODEL_RISK_PROXY_NOT_ESTIMATED` | Do not promote to a central model. |
| E-016 | Alternative below-1x masses | 62%, 65%, 68% | aggregate interpretation/model-risk proxy | Resolve with exact counts and endpoint convention. |
| E-017 | Student-t, macro-mixture and sector-factor parameters | Configured stresses | `MODEL_RISK_SCENARIO_NOT_FITTED` | Fit only with dated company-level panel data. |
| E-018 | N=2,000 as finite large-N proxy | Yes | `MODEL_RISK_ANALYSIS` | Add conditional common-factor integration for a formal limit. |

Fund TVPI, founder proceeds and company exit values remain prohibited as direct
investor-MOIC inputs without an explicit and documented mapping.
