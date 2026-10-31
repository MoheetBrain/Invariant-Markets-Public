# Data dictionary

No empirical data are included in Version 1. The future historical bootstrap should at minimum document:

| Field | Meaning | Unit / convention | Required provenance |
|---|---|---|---|
| `company_id` | Stable pseudonymous company identifier | String | Source and de-identification method |
| `vintage_date` | Cohort entry date | ISO date | Original dataset and timezone |
| `entry_value` | Invested or marked entry value | Currency | Valuation method and currency |
| `follow_on_cash_flow` | Subsequent capital invested | Currency, signed | Transaction source |
| `exit_date` | Realization date if observed | ISO date or missing | Exit source and censoring flag |
| `exit_value` | Realized value if observed | Currency | Exit source and proceeds definition |
| `status` | Failure, active, acquired, IPO or other state | Controlled vocabulary | Coding rules |
| `macro_state` | State used for dependence analysis | Versioned categorical mapping | Mapping methodology |
| `right_censored` | Whether outcome is not yet observed | Boolean | Observation cut-off date |

Raw, interim, processed and manifest folders are kept separate. No row should enter the model without a source, extraction date, transformation log and hash.
