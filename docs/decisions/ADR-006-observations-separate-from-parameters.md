# ADR-006: Separate empirical observations from model parameters

- Status: Accepted
- Date: 2026-08-14
- Scope: S2b empirical calibration evidence and terminal model inputs

## Context

S2b-a introduces public aggregate venture-return evidence. Those statistics are
rounded, often proprietary at the row level, and sometimes measure different
objects: investment MOIC, financing-level returns, fund TVPI, founder proceeds,
company exit values or financing transitions.

If the repository writes an observed aggregate directly into a model parameter,
the audit trail loses the distinction between data, proxy, calibration and model
risk.

## Decision

Empirical observations are stored in `data/calibration/empirical_constraints_v1.yaml`.
Source metadata is stored in `data/calibration/source_registry.yaml`. Model
parameters are derived in code and reported with residuals, provenance and
sensitivity analysis.

Every evidence item must declare:

- `object_measured`
- `provenance`
- `source_id`

Rounded public statistics must not be converted into exact counts or precise
posteriors unless raw data become available.

## Consequences

- The YAML layer is more verbose, but an external quant can trace every number.
- Founder/company/fund statistics cannot silently become investor-return data.
- Model-risk scenarios remain explicit rather than hidden as fitted facts.
- Calibration residuals are first-class outputs, not inconvenient byproducts.

## Revisit when

Revisit when row-level licensed data are available with documented inclusion
rules, de-duplication, censoring, cash-flow definitions and hashes. Even then,
raw observations and fitted parameters should remain separate artifacts.
