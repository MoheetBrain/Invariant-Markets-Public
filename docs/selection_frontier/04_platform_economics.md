# PlatformCo scenario economics

ADR-005 remains binding. The protection model outputs claim distributions and
warrant-value scenarios. The PlatformCo module consumes them together with
separate commercial assumptions.

Per period:

```text
Origination revenue = new protected capital * origination fee
Service revenue = average outstanding protected capital * service fee
Arrangement margin = charged capital
                   * max(investor fee - external price - risk admin, 0)
Warrant revenue = realized attributable warrant value * PlatformCo share
Modeled operating profit = revenue - variable cost - fixed cost
```

The canonical architecture does not warehouse uncapped guarantee claims in
PlatformCo. Claims enter profit only when an explicit risk-bearer switch is set.
The investment vehicle, external risk provider and PlatformCo remain distinct.

Demand uplift and founder acceptance scale different objects. Demand multiplies
offered capital; founder acceptance caps the share that can be deployed. The
10-year model tracks cohort issuance, outstanding capital, delayed warrant
realization, operating costs, cumulative cash generation and discounted NPV.

External prices are `COMMERCIAL_PRICE_SCENARIO`. Enterprise-value multiples are
`ILLUSTRATIVE_VALUATION_MULTIPLE` and never a company valuation.
