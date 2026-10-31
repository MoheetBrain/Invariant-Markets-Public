# S2b-a.1 empirical coherence and dependence frontier

## Scope

This milestone investigates cross-object empirical coherence and shared
dependence around the frozen S2b-a terminal marginal. It does not model
selection skill, survival transitions, legal structure, risk-carrier pricing,
founder-warrant reliability or PlatformCo value.

No central `empirical_terminal_v2` is introduced. Available aggregates do not
identify company de-duplication, capital weighting, censoring, cash-flow timing,
fees/carry or valuation policy. The V2 label denotes an analysis version around
V1, with proxy adjustments kept as named model-risk scenarios.

## Reproduction

```bash
python -m invariant.cli run-empirical-coherence-dependence \
  --config configs/research/empirical_coherence_dependence_v2.yaml
```

The command writes the config, assumptions, observation audit, coherence grid,
dependence frontier, breakpoints, saturation analysis, correlated deletion
tests, dependence-family comparison, validation diagnostics, summary and ten
figures into one ignored canonical run directory.

## Coherence experiment

The experiment crosses two declared body families, four survival-tail
exponents, five tail caps, three observation-weight interpretations and three
interpretations of the rounded 65% below-1x statistic. It never searches for a
parameter merely because it matches fund TVPI.

Each row reports threshold probabilities, implied equal-weighted pooled mean,
simulated N=100 median proxy, numerical error and one of:

- `compatible`: threshold residuals and both fund benchmark gaps satisfy the
  tight declared tolerances;
- `weakly_compatible`: threshold residuals and both gaps satisfy wider declared
  tolerances;
- `incompatible`: otherwise.

The round/company reweighting factors are stress magnitudes, not estimates.

## Dependence experiment

The principal model is a Gaussian latent one-factor copula over the frozen V1
marginal. Rho runs from 0.00 through 0.40 exactly in steps of 0.01. The grid
covers N = 50, 100, 250, 500, 1,000 and 2,000 and floors of 50%, 75%, 80%, 90%
and 100%.

N=100 receives 100,000 paths at every rho. Larger-N rows use a 5,000-path
screening stage and are labelled as such; their breakpoints are screening
estimates, not false precision. Every row includes claim-mean and probability
MCSEs plus ES tail counts and ES MCSEs.

Breakpoint interpolation uses the first crossing of a monotone envelope over
the simulated grid. The raw frontier remains unaltered, so Monte Carlo noise is
visible. Thresholds outside rho 0.00–0.40 are reported explicitly.

## Large-N interpretation

Under independence, idiosyncratic outcomes diversify rapidly. Under a common
factor, conditional portfolio returns converge toward a function of that
factor. More companies reduce conditional sampling noise but do not remove the
shared state. The saturation output quantifies each adjacent N increment and
distance to N=2,000 as a finite large-N proxy.

## Stress models

Gaussian one-factor, Student-t common-scale, a two-state macro mixture and a
ten-sector toy factor model are compared at the same declared rho parameter.
Only the Gaussian and sector latent-normal constructions preserve normal
one-dimensional latent margins by construction. None of the families or rho
values is empirically fitted; comparisons are model-risk stresses.

## Falsification standard

The thesis fails if economically relevant floors are cheap only under near-zero
dependence, continued capture of rare power-law winners and optimistic gross
return assumptions. The analysis must state that result directly and cannot
convert a model-risk stress into evidence of product viability.
