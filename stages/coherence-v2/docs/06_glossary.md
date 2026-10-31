# Glossary

**Principal floor** — the minimum targeted fraction `gK` of initial principal at maturity before considering how support is funded.

**NAV** — net asset value; here `NAV_T` is the terminal portfolio value used by the payoff.

**Founder warrant** — a contractual right or equity interest whose economic value may support the protection system; the prototype uses simple arithmetic only.

**First-loss reserve** — liquid capital that absorbs losses before a later support layer.

**Stop-loss / excess-of-loss** — a contract that pays losses above an attachment up to a limit.

**Reinsurance** — risk transfer from one risk carrier to another. It is a possible commercial concept, not assumed by the mathematical core.

**VaR** — a quantile of a loss or claim distribution at a selected confidence level.

**Expected Shortfall** — the average loss in the tail beyond a selected VaR threshold.

**Ruin probability** — probability that a defined reserve or capital balance is exhausted. Version 1 does not claim a full regulatory ruin framework.

**Right censoring** — an outcome is still active or unobserved at the data cut-off, so its final value is unknown.

**Copula** — a method for modelling dependence separately from marginal distributions; no copula is fitted here.

**Power-law tail** — a heavy-tailed positive outcome distribution; the current model uses a single explicit extreme-winner point instead.

**Wrong-way risk** — support needs rise in states where the assets or founder warrants intended to support them lose value.
