# Unit-of-observation audit

## Decision use

This audit governs S2b-a.1 / V2. It prevents an aggregate measured on one
economic object from silently becoming a parameter for another object. The
machine-readable companion is
`data/calibration/unit_of_observation_audit_v2.csv`, with one row for every
empirical observation or aggregate constraint used or discussed by the model.

The central finding is that the return-threshold source is publicly described
at financing/investment or deal level, while the target product portfolio is a
portfolio of unique companies and the validation benchmarks are fund-level
TVPI. The available public aggregates do not contain company identifiers or a
round-to-company map. They therefore cannot establish unique-company weights.

## Object taxonomy

| Object type | Meaning | Direct investor-MOIC use |
|---|---|---|
| `UNIQUE_COMPANY` | One company counted once under a stated outcome rule | Only with an investment/cash-flow bridge |
| `FINANCING_ROUND` | One financing event; a company may appear repeatedly | Round-level proxy only; never silently unique-company data |
| `INVESTOR_CHECK` | One dated investment/check and its proceeds or valuation | Yes, subject to censoring and gross/net definitions |
| `FOUNDER_PROCEEDS` | Founder-level exit proceeds | No |
| `COMPANY_EXIT_VALUE` | Enterprise/equity value at company exit | No |
| `FUND_TVPI` | Fund residual value plus distributions divided by paid-in capital | Validation only without an aggregation bridge |
| `FUND_DPI` | Fund distributions divided by paid-in capital | Validation only without an aggregation bridge |
| `UNKNOWN` | Public metadata does not identify the object | No |

The following distinctions are enforced conceptually and in tests:

- financing-round MOIC is not unique-company MOIC;
- founder proceeds are not investor MOIC;
- company exit value is not investor MOIC;
- fund TVPI is not a company-return distribution.

## Source-by-source audit

### `SRC_CORRELATION_001`

The source reports rounded thresholds—65% below 1x, 10% at or above 5x, 4% at
or above 10x, and 0.4% at or above 50x—from a public summary of a proprietary
sample of approximately 21,000 venture financing/investment observations.

- Assigned object: `FINANCING_ROUND`.
- Return definition: gross investor-return multiple, to the extent disclosed.
- Realisation/censoring: `UNKNOWN`.
- Company de-duplication: `UNKNOWN`.
- Stage/vintage coverage: insufficiently documented in the public aggregate.
- V1 use: aggregate marginal constraints.
- V2 restriction: cannot be relabelled `UNIQUE_COMPANY`; no estimate of repeated
  winner rounds is presented as fact.

Because a successful company can raise multiple rounds and generate multiple
observations, repeated rounds could overweight winners. The direction is
plausible; its magnitude is **NOT IDENTIFIABLE FROM AVAILABLE DATA**.

### `SRC_CORRELATION_002`

The realised-deal decomposition reports approximately 39% out of business, 29%
positive but below capital return, and 32% above capital return over roughly
7,976 realised deal observations.

- Assigned object: `FINANCING_ROUND`.
- Realisation: realised-deal sample.
- V1 use: 39% is a proxy split for complete-loss mass; the stronger 65% below-1x
  threshold fixes total loss mass.
- Limitation: “out of business” is not investor MOIC equal to zero, and the
  39%+29%=68% decomposition does not reconcile exactly with 65%.

V2 treats 68% as an explicit alternative interpretation, not a corrected fact.

### `SRC_ANGELLIST_001`

The approximate density exponent 2.3 concerns positive early-stage investment
returns in platform data.

- Assigned object: `INVESTOR_CHECK`.
- Conditioning: positive-return sample; it cannot identify probability below
  1x.
- Use: survival-tail beta near 1.3 is a model-risk convention after explicitly
  converting density alpha to survival beta.
- Limitation: cutoff, geography, censoring and exact fitting convention require
  source-level data.

### `SRC_MOONFIRE_001`

The candidate density exponent 2.05 and lower cutoff near 0.35 come from an
unverified public summary. Its object, unit, cutoff and exponent convention are
not adequately documented, so it remains `UNKNOWN` and is not a central input.

### `SRC_CARTA_DILUTION_001`

The 20.5% seed and 20.1% Series A medians describe `FINANCING_ROUND` dilution.
They exclude SAFE/note conversion, bridges, option-pool refreshes and other
issuance. Two medians do not identify a dilution distribution.

### `SRC_CARTA_TRANSITION_001` and `SRC_CARTA_TIMING_001`

The 17% 2022 and 25–30% 2018 Seed-to-Series-A observations are
`UNIQUE_COMPANY` cumulative incidence by 24 months, not lifetime transition
probabilities. The 766-day median is conditional on a Series A occurring and
cannot identify an unconditional event-time distribution. All remain deferred
to S2b-b.

### `SRC_BBB_001`

The 1.84x UK pooled, 1.95x US pooled and 1.48x UK median references are
`FUND_TVPI` aggregates used only for external validation.

Fund TVPI is capital-weighted; V1 is an equal-weighted terminal
investment-return average. Fees, carry, reserves, follow-ons, unrealised
valuations, vintage mix and gross/net convention are not aligned well enough
for direct calibration. The values cannot be ingested as investor-level MOIC
without a documented aggregation mapping.

### `SRC_AZEVEDO_001`

The 84–88% founder zero-proceeds range is `FOUNDER_PROCEEDS`; the candidate
exponent 1.12 is `COMPANY_EXIT_VALUE` pending exact source identification. Both
are explicitly excluded from investor-return calibration.

## Identification boundary

The audit can conclude that V1 combines financing/deal-level frequency
constraints with model-risk choices for values inside each return band, then
compares the result to a different fund-level object. It can show how declared
body, tail and proxy-reweighting scenarios change outputs.

It cannot causally allocate the 2.34x-to-fund-TVPI gap among round duplication,
censoring, vintage, stage, fees/carry, gross/net treatment or valuation policy.
Doing so would manufacture information absent from the public aggregates.

## Highest-value missing dataset

A licensed row-level panel should link a stable unique-company ID to every
financing round and investor check; dated contributions, distributions and
valuations; realised/censored status; stage, geography and vintage; ownership
and dilution; and fund-level fees/carry. That joined object would permit company
de-duplication, capital weighting, cash-flow reconstruction and a valid bridge
from investment outcomes to fund TVPI.
