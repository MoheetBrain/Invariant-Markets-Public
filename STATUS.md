# Project status

Current status: **S2b-a.1 — selection and portfolio feasibility frontier**.

This status means S2a remains reproducible and a separate S2b-a terminal
investment-return mixture now constrains marginal return thresholds using
aggregate empirical evidence. It does not mean full S2b historical calibration
has been achieved or that the model is suitable for commercial insurance
pricing, regulatory capital, legal structuring or investment decisions.

S2b-a.1 preserves that empirical base and adds hypothetical selection,
macro/sector dependence, analytical failure tolerance, portfolio-size
saturation, feasibility frontiers and separate PlatformCo scenario economics.
Selection, dependence, prices, demand, founder acceptance, fees, costs and
valuation multiples remain scenario inputs, not observed facts.

## Evidence ladder

| Level | Meaning | Status |
|---|---|---|
| S0 | Interesting hypothesis | achieved |
| S1 | Precise financial primitive defined | achieved |
| S2a | Reproducible quantitative prototype | achieved |
| S2b-a | Empirically constrained terminal marginals | achieved |
| S2b-a.1 | Hypothetical selection and portfolio feasibility frontier | achieved |
| S2b-b | Empirical survival / transition model | not achieved |
| S2b-c | Empirical dependence / macro model | not achieved |
| S2b-d | Historical bootstrap + fund validation | not achieved |
| S2b | Historically calibrated model | not achieved |
| S3 | Independent adversarial model review | not achieved |
| S4 | Indicative risk-carrier pricing | not achieved |
| S5 | Founder-supply validation | not achieved |
| S6 | Investor-demand validation | not achieved |
| S7 | Legal/regulatory architecture validated | not achieved |
| S8 | Live pilot | not achieved |
| S9 | Scale | not achieved |

## Current evidence

- Model A produces a deterministic 40-point portfolio-size/protection-level grid under a fixed configuration and seed.
- Same-seed reruns produce byte-identical numerical `results.json` output.
- The one-command baseline saves canonical config, results, summary, manifest and five labelled figures.
- Model B has a minimal state-machine prototype and deterministic event counts.
- Model C is an explicit interface and refuses to fabricate historical data.
- A clean Python 3.14 environment installs from the repository instructions with no broken requirements.
- All 93 unit, statistical, regression and integration tests pass.
- Contract invariants, probability validation, seed behaviour and serialization are covered by automated tests.
- Configuration numbers carry value, units, status, source and notes.
- S2b-a stores empirical observations separately from derived model parameters.
- Every calibration evidence item declares the object it measures and source ID.
- The empirical mixture reports body, tail, cap and dependence model-risk variants.
- Top-winner dependence, Monte Carlo convergence and fund-level validation outputs are generated.
- Exact failure-tolerance tables cover N=100/250/500/1,000/2,000, four floors,
  seven survivor MOICs and three recovery assumptions.
- Target-constrained and exponential-tilt selection models are explicit
  hypothetical sensitivities and prohibit hindsight.
- Macro and sector latent factors preserve selected marginals and separate
  AI-only concentration from frontier-sector diversification.
- Core selected-portfolio scenarios use 100,000 paths; discovery and refinement
  tiers are recorded separately.
- PlatformCo revenue, profit, demand, founder supply and illustrative valuation
  arithmetic remain separate from the claim model under ADR-005.

## What is not proven

No current result proves actual underwriting skill, a sustainable guarantee
cost, an economically sufficient founder contribution, a risk-carrier quote, a
regulatory capital requirement, a legal wrapper, investor demand, founder
willingness, or empirical tail/dependence behaviour.

Full S2b remains unachieved because empirical survival, transition timing,
follow-on policy, macro-regime dynamics, sector/vintage dependence, historical
bootstrap data and external risk-carrier economics are not calibrated.
