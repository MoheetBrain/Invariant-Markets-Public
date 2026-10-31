# Validation

S2b-a validation has four layers:

1. **Marginal return constraints**: compare simulated investment-level returns
   with `<1x`, `>=5x`, `>=10x` and `>=50x` aggregate constraints.
2. **Fund-level posterior predictive targets**: compare gross equal-weighted
   simulated portfolio MOIC with external fund-level TVPI targets, without
   tuning to match them.
3. **Monte Carlo convergence**: compare expected claim, VaR99.5 and ES99.5
   across increasing path counts.
4. **Power-law dependence diagnostics**: report largest/top-3/top-5 NAV shares,
   HHI and expected claims after removing top winners.

Fund-level TVPI is validation only. It is not used as investment-level return
data because fees, carry, reserves, unrealized valuation marks, vintage maturity
and fund construction differ from the terminal equal-weighted simulator.
