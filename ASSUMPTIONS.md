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

## S2b-a.1 selection-frontier assumptions

The canonical machine-readable register is
`configs/selection_frontier_v1.yaml::assumptions`. Every entry there contains
value, unit, meaning, provenance, reason, mathematical role, sensitivity range
and empirical evidence required to replace it. The operational config values
and the register are snapshotted into every run's `config.yaml` and
`assumptions.yaml`.

| ID | Name | Value / range | Provenance | Code / config location | Evidence required |
|---|---|---|---|---|---|
| SIM-001 | Staged Monte Carlo paths | 1,000 discovery; 10,000 sensitivity; 50,000 refinement; 100,000 core | `MODEL_RISK_SCENARIO` | `simulation` | Numerical convergence and multi-seed diagnostics. |
| SEL-001 | Selected sub-1x rate | 40%-65% | `HYPOTHETICAL_SELECTION_SKILL` | `selection.target_constraint_scenarios`; `selection/models.py` | Point-in-time selected/rejected underwriting backtest. |
| SEL-002 | Selected >=10x rate | 4%-10% | `HYPOTHETICAL_SELECTION_SKILL` | same | Out-of-sample selected/rejected investor MOIC. |
| SEL-003 | Exponential selection tilt | `s=0-0.50`, `h(x)=log(1+x)` | `HYPOTHETICAL_SELECTION_SKILL` | `selection.exponential_tilt`; `selection/models.py` | Calibrated investment-time score and outcomes. |
| DEP-001 | Macro latent dependence | 0-0.20 variance share | `MODEL_RISK_SCENARIO` | `dependence`; `portfolio/factor_model.py` | Company outcomes by vintage and macro regime. |
| DEP-002 | Sector latent dependence | 0-0.40 variance share | `MODEL_RISK_SCENARIO` | same | Unique-company return data with sector labels. |
| PORT-001 | Equal initial weights | `1/N` | `MODEL_RISK_SCENARIO` | `portfolio.equal_weighted`; `portfolio/simulation.py` | Executable allocation and follow-on policy. |
| PORT-002 | Sector allocation | five-way equal; 50% concentration stress | `MODEL_RISK_SCENARIO` | `portfolio.constructions` | Investable supply and capacity constraints. |
| TAIL-001 | Winner tail | beta 1.430676558; unbounded/capped/truncated/no-mega | calibrated aggregate base plus `MODEL_RISK_SCENARIO` variants | `tail_models` | Row-level cash-flow MOIC and censoring. |
| GUAR-001 | Principal floor | 50%, 75%, 90%, 100% | `MODEL_RISK_SCENARIO` | `portfolio.protection_fractions` | Candidate terms and legal review. |
| WAR-001 | Founder warrant economics | 2% initial; aggregate dilution medians; 0%-100% PlatformCo share | mixed aggregate/scenario | `protection_support.founder_warrant` | Executed terms, realization and acceptance. |
| STOP-001 | Generic stop-loss | 5% attachment; 35% limit | `MODEL_RISK_SCENARIO` | `protection_support.generic_stop_loss` | Indicative carrier terms and enforceability. |
| G-001 | External protection price | 2%-20% | `COMMERCIAL_PRICE_SCENARIO` | `platform_economics.external_risk_provider_prices` | Written risk-carrier quotations. |
| DEM-001 | Investor demand uplift | 1x-10x | `MODEL_RISK_SCENARIO` | `platform_economics.demand_uplifts` | Behavioral experiment or commitments. |
| SUP-001 | Founder acceptance | 25%-100% | `MODEL_RISK_SCENARIO` | `platform_economics.founder_acceptance_rates` | Founder offer experiment by requested contribution. |
| REV-001 | Platform fees | origination 0.5%-3%; service 0.25%-1%; spread 0%-2% | `MODEL_RISK_SCENARIO` | `platform_economics` | Validated product terms and willingness to pay. |
| OPEX-001 | Operating costs | variable 0.25%-2%; fixed GBP 1m-50m | `MODEL_RISK_SCENARIO` | `platform_economics` | Bottom-up operating plan and actuals. |
| BUS-001 | Business timing | 10 years; 7-year maturity/delay; 10% issuance growth | `MODEL_RISK_SCENARIO` | `platform_economics.ten_year` | Product maturity and realized cash-flow history. |
| NPV-001 | Discount rate | 12% | `MODEL_RISK_SCENARIO` | `platform_economics.ten_year.discount_rate` | Risk-adjusted cost-of-capital work. |
| VAL-001 | Valuation multiples | revenue 2x-10x; modeled profit 8x-30x | `ILLUSTRATIVE_VALUATION_MULTIPLE` | `platform_economics.valuation` | Verified relevant market comps. |
| PUB-001 | Optional public sleeve | 0%-50% allocation; 0.5x/1x/1.5x/3x returns | `MODEL_RISK_SCENARIO` | `public_innovation_sleeve` | Defined mandate and sourced return history. |
| FRONT-001 | Frontier targets and slices | E[claim] 1%-10%; P(claim) 5%-25%; canonical N=1,000/g=100% | `MODEL_RISK_SCENARIO` | `frontiers`; `portfolio` | Risk-carrier appetite and product materiality policy. |
| STR-001 | Hostile stress magnitudes | -2 sigma; beta 1.60; doubled dilution/price; U=1; acceptance 25% | `MODEL_RISK_SCENARIO` | `stress_tests`; `stress_parameters` | Crisis calibration, quotes and observed behavior. |

Selection scenarios use no future exit status, valuation, financing or revenue
as features. PlatformCo is not the canonical guarantee risk bearer. Expected
claim and ES are model outputs; external price, demand, founder supply, fees,
costs and illustrative valuation multiples remain separate assumptions.
