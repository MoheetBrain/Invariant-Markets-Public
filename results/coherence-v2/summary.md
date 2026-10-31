# S2b-a.1 / V2 empirical coherence + dependence frontier

> V2 is an analysis layer around the frozen V1 marginal. It is not a refitted unique-company return model, guarantee quote, capital model, or product-viability assessment.

## Bottom line

The frozen V1 run produces `2.3396x` because the four rounded financing/deal-level thresholds leave the within-band body and extreme-tail severity underidentified. The selected log-uniform body and capped Pareto tail convert those frequency constraints into a high gross equal-weighted mean. That object is not comparable one-for-one with capital-weighted fund TVPI.

Across `360` pre-declared interpretations, `0` are classified compatible and `0` weakly compatible under the stated joint threshold/TVPI tolerances. No proxy adjustment is promoted to a central V2 model because company de-duplication and cash-flow definitions are unavailable.

The Correlation-style source is not proven to be a unique-company dataset. The public description is financing/investment-level and may repeat successful companies across rounds. The amount of duplication is **NOT IDENTIFIABLE FROM AVAILABLE DATA**.

## Required reduction from V1 proxy

| Comparison | Absolute | Percentage of V1 proxy |
|---|---:|---:|
| us_pooled | 0.3896x | 16.65% |
| uk_pooled | 0.4996x | 21.35% |
| uk_median | 0.5349x | 26.55% |

These are required total reductions, not causal allocations. Body/tail variants show model sensitivity; weighting, duplication, censoring, vintage, fees/carry, gross/net and stage contributions cannot be uniquely decomposed from public aggregates.

## N=1,000 Gaussian frontier (screening estimates)

| rho | floor | E[claim]/K | P(claim) | ES99.5 |
|---:|---:|---:|---:|---:|
| 0.00 | 50% | 0.00% | 0.00% | 0.00% |
| 0.10 | 50% | 0.16% | 1.62% | 19.93% |
| 0.20 | 50% | 1.50% | 9.06% | 40.90% |
| 0.30 | 50% | 3.99% | 18.74% | 46.48% |
| 0.40 | 50% | 6.44% | 25.32% | 49.24% |
| 0.00 | 75% | 0.00% | 0.00% | 0.00% |
| 0.10 | 75% | 1.07% | 6.14% | 44.93% |
| 0.20 | 75% | 4.99% | 18.76% | 65.90% |
| 0.30 | 75% | 9.96% | 28.78% | 71.48% |
| 0.40 | 75% | 14.05% | 35.26% | 74.24% |
| 0.00 | 80% | 0.00% | 0.00% | 0.00% |
| 0.10 | 80% | 1.40% | 7.32% | 49.93% |
| 0.20 | 80% | 5.99% | 20.96% | 70.90% |
| 0.30 | 80% | 11.46% | 31.02% | 76.48% |
| 0.40 | 80% | 15.86% | 37.30% | 79.24% |
| 0.00 | 90% | 0.00% | 0.00% | 0.00% |
| 0.10 | 90% | 2.30% | 10.74% | 59.93% |
| 0.20 | 90% | 8.29% | 25.18% | 80.90% |
| 0.30 | 90% | 14.73% | 34.48% | 86.48% |
| 0.40 | 90% | 19.78% | 40.72% | 89.24% |
| 0.00 | 100% | 0.00% | 0.00% | 0.00% |
| 0.10 | 100% | 3.55% | 14.30% | 69.93% |
| 0.20 | 100% | 11.00% | 28.88% | 90.90% |
| 0.30 | 100% | 18.35% | 37.96% | 96.48% |
| 0.40 | 100% | 24.00% | 43.64% | 99.24% |

## N=2,000 incremental safety

| rho | floor | N=1,000 E[claim] | N=2,000 E[claim] | reduction |
|---:|---:|---:|---:|---:|
| 0.10 | 80% | 1.40% | 1.32% | 0.08% |
| 0.10 | 100% | 3.55% | 3.35% | 0.20% |
| 0.20 | 80% | 5.99% | 5.91% | 0.07% |
| 0.20 | 100% | 11.00% | 10.87% | 0.12% |
| 0.30 | 80% | 11.46% | 11.35% | 0.11% |
| 0.30 | 100% | 18.35% | 18.21% | 0.13% |
| 0.40 | 80% | 15.86% | 15.83% | 0.03% |
| 0.40 | 100% | 24.00% | 23.96% | 0.04% |

These are 5,000-path screening comparisons. Under positive shared dependence, idiosyncratic risk diversifies but common-factor state risk remains; the 1,000→2,000 gain is only a few tenths of a percentage point in the displayed cases.

## N=1,000 breakpoints requested for 80% and 100% floors

| Floor | E[claim] threshold | rho breakpoint | Status |
|---:|---:|---:|---|
| 80% | 2.5% | 0.1253 | INTERPOLATED |
| 80% | 5.0% | 0.1827 | INTERPOLATED |
| 80% | 10.0% | 0.2832 | INTERPOLATED |
| 100% | 2.5% | 0.0818 | INTERPOLATED |
| 100% | 5.0% | 0.1156 | INTERPOLATED |
| 100% | 10.0% | 0.1896 | INTERPOLATED |

## Correlation versus missing winners

At rho=0.20, N=1,000 and a 90% floor, the correlated normal portfolio has E[claim]/K `8.23%`. Removing every >=10x winner raises it by `3.93%` to `12.16%`. The shared-dependence effect is already structural before deletion; missing winners is a material additional stress, not a substitute explanation.

## Dominant model uncertainty

Among the `30` variants that still meet the rounded threshold tolerances, implied pooled means span `2.0084x` to `2.7363x`, showing that tail severity/cap and body shape remain material even before dependence. At rho=0.20, N=1,000 and g=90%, the four unfitted dependence families span E[claim]/K `8.39%` to `12.69%`. Dependence family/strength, extreme-tail severity and the unobserved round-to-company weighting dominate current model uncertainty.

## Falsification and decision relevance

- Protection that looks nearly free under independence is not robust to moderate shared dependence. Large N cannot diversify a common latent state.
- Winner-deletion stresses show an additional reliance on retaining rare outcomes, but correlated shifts move the whole portfolio and are the more structural obstacle at large N.
- Gaussian, Student-t, macro-mixture and sector-factor results are model-risk stresses, not fitted dependence estimates.
- No current evidence justifies calling 80%–100% protection cheap under realistic dependence. Any such claim would require unusually low dependence, reliable capture of extreme winners, and a better unique-company return dataset.
- The most valuable missing dataset is a licensed row-level panel linking unique company IDs to every financing/check, dated cash flows and valuations, realised/censored status, stage/vintage/geography, and fund fee/carry treatment.

## Robust conclusions versus model artefacts

Robust: the source objects are mismatched; the V1 body/tail are underidentified; shared dependence survives diversification; exact mismatch attribution is unavailable. Model artefacts: the precise rho breakpoint, tail-cap sensitivity, macro-state severity, sector allocation and all proxy de-duplication factors.

See the CSV files and `validation.json` for path counts, Monte Carlo errors, tail observations, interpolation status and audit controls.
