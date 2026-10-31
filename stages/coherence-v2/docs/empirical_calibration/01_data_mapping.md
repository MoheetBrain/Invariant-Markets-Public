# Data mapping

S2b-a treats these stochastic objects as distinct:

| Object | May be used for terminal investor MOIC? | Notes |
|---|---:|---|
| Investor-level gross return multiple | Yes, if unit is documented | Preferred target for terminal model. |
| Financing-level investment return | Proxy | May include multiple rounds in one company. |
| Company enterprise exit value | No direct substitution | Needs ownership, liquidation preference and dilution mapping. |
| Founder exit proceeds | No | Founder zero proceeds is not investor 0x. |
| Fund TVPI / DPI | Validation only | Fund-level, affected by fees, reserves and valuations. |
| Financing transition | Deferred | S2b-b survival/event input, not terminal MOIC. |
| Legal survival / dissolution | Deferred | Not equal to investor capital recovery. |

Every empirical item in `data/calibration/empirical_constraints_v1.yaml` declares
`object_measured`, `provenance` and `source_id`. This prevents a founder,
company, financing, investment and fund statistic from silently becoming the
same random variable.
