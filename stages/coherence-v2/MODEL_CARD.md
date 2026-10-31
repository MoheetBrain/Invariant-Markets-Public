# Model card

## Intended use

S2a tests the complete synthetic research pipeline: configuration provenance,
five-band synthetic outcomes, shared macro dependence, portfolio aggregation,
principal-floor claims, risk metrics, dilution arithmetic, generic stop-loss
arithmetic and reproducible artifacts.

S2b-a tests an empirically constrained terminal investment-return marginal
model. It uses public aggregate threshold constraints, model-risk body/tail
variants, dependence stress cases, top-winner diagnostics, convergence checks
and fund-level posterior predictive validation.

S2b-a.1 audits the economic object measured by every aggregate and maps a
dependence frontier around the frozen V1 marginal. Its V2 proxy reweightings and
alternative dependence families are not fitted empirical models.

## Prohibited use

Do not use this model to offer or price a live guarantee, set regulatory capital, value PlatformCo, recommend an investment, infer a legal wrapper, claim regulatory solvency, or claim full empirical startup/fund performance.

## Model scope

Model A samples one shared `NORMAL`, `WEAK` or `CRISIS` state for each portfolio. Every startup then receives a synthetic return from one of five YAML-defined bands. Portfolios are equal weighted. The baseline runner sweeps eight portfolio sizes and five protection levels. Model B is a minimal state machine. Model C has no data implementation.

The S2b-a empirical terminal model samples equal-weighted terminal investor
MOIC from:

```text
complete-loss mass
+ partial-loss body on (0,1)
+ ordinary-success body on [1,5)
+ strong-success body on [5,10)
+ Pareto-style tail on [10,infinity)
```

It supports log-uniform and truncated-lognormal body models, capped/truncated
and no-mega-winner tail variants, and independent/Gaussian-factor/Student-t
factor dependence scenarios. These are model-risk variants, not claims that the
true distribution is known.

Founder-warrant value uses `q_T=q_0∏(1-d_r)` and remains separate from guarantee claims. Generic stop-loss uses `min(max(loss-attachment,0),limit)` and names no legal provider.

## Provenance

Every S2a startup-return probability and bound carries value, units,
`SCENARIO` status, source and notes. S2b-a observations live in
`data/calibration/empirical_constraints_v1.yaml`, source metadata lives in
`data/calibration/source_registry.yaml`, and derived parameters are reported in
run artifacts rather than written over observations. Run manifests record
code/environment identifiers, hashes, seeds and model versions.

## Known limitations

- No historical startup, fund, vintage, financing, exit, liquidity or warrant dataset.
- Uniform outcomes inside broad synthetic bands.
- Dependence is only a shared categorical state; residual company outcomes are conditionally independent.
- No timing of cash flows, follow-on amounts, sector effects, censoring or valuation uncertainty.
- Founder warrants are arithmetic terminal values, not liquid assets, option valuations or legal claims.
- VaR and Expected Shortfall summarize synthetic claims and are not regulatory capital.
- No legal, accounting, tax, insurance, counterparty, demand or PlatformCo valuation analysis.
- S2b-a uses rounded aggregate public statistics; no row-level return data are included.
- Financing-level observations may not be one terminal observation per company.
- Body distributions are model-risk choices, not fitted truths.
- Correlation scenarios are not empirically fitted.
- Fund TVPI targets are validation only and do not identify investment-level returns.
- S2b-a.1 large-N and breakpoint estimates inherit the assumed copula; no
  available dataset identifies rho or the alternative stress-family parameters.

## Validation status

S2a is complete when the acceptance suite and clean-install reproduction checks
pass. S2b-a is complete only for empirically constrained terminal marginals.
Full S2b historical calibration, independent review and every later evidence
level remain incomplete.
