# Tail convention

S2b-a uses the survival-tail convention:

\[
P(X \ge x \mid X \ge u) = (x/u)^{-\beta}, \quad x \ge u.
\]

The threshold is:

\[
u = 10x.
\]

The baseline beta is derived from rounded aggregate constraints:

\[
\beta = -\frac{\ln(P(X \ge 50)/P(X \ge 10))}{\ln(50/10)}
      = -\frac{\ln(0.004/0.04)}{\ln(5)}
      \approx 1.4306766.
\]

This is `CALIBRATED_FROM_AGGREGATE_CONSTRAINTS`, not an observed raw statistic.

The corresponding density exponent under \(f(x)\propto x^{-\alpha}\) is:

\[
\alpha = \beta + 1.
\]

The implementation deliberately names the parameter
`survival_tail_exponent_beta`; it does not use an ambiguous `alpha`.

The run compares several tail variants:

- unbounded Pareto
- Pareto capped at 500x
- Pareto capped at 1000x
- statistically truncated Pareto
- no-mega-winner stress with no return at or above 50x
