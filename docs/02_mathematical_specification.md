# Mathematical specification

## Synthetic startup outcomes

For each portfolio path, a shared macro state `S∈{NORMAL, WEAK, CRISIS}` is sampled. Conditional on `S`, each startup is assigned to exactly one YAML-defined band:

\[
X_i\in\{\text{failure},\text{partial},\text{modest},\text{large},\text{extreme}\}.
\]

Failure is exactly `0x`. Conditional on a non-degenerate band, the S2a return multiple is uniform between that band's configured minimum and maximum. This uniform choice is synthetic and exists only to test the architecture.

For equal initial weights and `N` startups:

\[
M_T=\frac{1}{N}\sum_{i=1}^{N}X_i,
\qquad
NAV_T=K M_T.
\]

## Principal-floor claim

\[
gK=\text{protected principal},
\qquad
C_T=\max(gK-NAV_T,0).
\]

Per £1 initial principal:

\[
\frac{C_T}{K}=\max(g-M_T,0).
\]

The latter is what the grid risk metrics report.

## Founder warrant

\[
q_T=q_0\prod_{r=1}^{R}(1-d_r),
\qquad
W_T=q_TV_T.
\]

S2a uses the same configured dilution percentage in each round. Warrant value is not netted against the guarantee claim.

## Generic stop-loss

\[
P=\min(\max(L-A,0),U),
\]

where `L` is gross guarantee loss, `A` attachment and `U` maximum payout. This is wrapper-neutral arithmetic.

## VaR and Expected Shortfall convention

Claims are non-negative losses per £1 initial principal; larger positive values are worse. VaR at confidence `α` is the empirical upper-tail claim quantile. Expected Shortfall is the mean of simulated claims greater than or equal to that VaR threshold. These are synthetic sample summaries, not calibrated capital requirements.

## Concentration

For each non-wipeout path, concentration is the largest startup terminal value divided by portfolio terminal NAV. The reported metric is its Monte Carlo mean conditional on positive terminal NAV. If every path is a total wipeout, the reported concentration is zero because no terminal value remains to allocate.
