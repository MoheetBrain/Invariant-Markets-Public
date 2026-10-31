# Validation plan

## Current stage: S2a

The current tests establish payoff monotonicity, zero/full-wipeout cases, generic stop-loss boundaries, multi-round warrant dilution, probability sums, same-seed identity, different-seed variation, grid completeness, serialization and a small analytical reference scenario. Integration tests verify the complete artifact set and byte-identical same-seed numerical results. They do not validate the synthetic parameters.

## Path to S2b

1. Define an immutable data dictionary and inclusion/exclusion rules for startup, fund and vintage cohorts.
2. Acquire documented historical data with licensing, provenance and point-in-time controls.
3. Resolve failures, exits, valuations, right censoring and currency/unit conventions.
4. Fit candidate survival and positive-tail distributions with uncertainty intervals.
5. Calibrate macro dependence and compare against out-of-sample cohorts.
6. Re-run Models A, B and C with common validation metrics and adversarial sensitivity tests.

## S2b-a validation

S2b-a adds:

- source registry and empirical constraints validation;
- explicit object mapping for each empirical number;
- threshold residuals for `<1x`, `>=5x`, `>=10x` and `>=50x`;
- model-risk sensitivity across body, tail and dependence assumptions;
- Monte Carlo convergence for expected claim, VaR99.5 and ES99.5;
- top-winner dependence metrics;
- fund-level TVPI comparisons used only as validation targets.

The next highest-value task is exactly one task: **build the S2b-b competing-risk transition dataset for Seed -> Series A / bridge / failure / still-seed states with censoring rules**. Do not treat the S2b-a terminal run as full S2b evidence.

## S2b-a.1 validation

The selection-frontier suite adds exact failure-boundary arithmetic, selection
normalization and monotonicity, `s=0` base recovery, factor variance and sector
sharing, invalid-rho rejection, marginal preservation, seed identity, winner
removal invariants, literal-wipeout quadrature, PlatformCo risk separation,
fee-base checks, discounting, break-even inversion, demand/founder bounds,
scenario provenance, frozen-config hashes, deterministic serialization and
frontier interpolation tests.

The canonical artifact records ES99.5 tail observations and Monte Carlo standard
error, a path-count convergence sequence, all executed experiment families and
file hashes. Core scenarios require 100,000 paths. Coarse discovery values must
not be promoted to refined estimates.

The next task recommendation for this milestone is the single empirical move in
its canonical summary: a timestamped out-of-sample underwriting backtest using
only information available at investment time.
