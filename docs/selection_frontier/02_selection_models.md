# Hypothetical selection models

## Target constraints

The target model specifies scenario values for `P(X<1)` and `P(X>=10)`.
Within the loss region it preserves the frozen base complete-loss/partial-loss
split. Within `[1,10)` it preserves the base 1-5x/5-10x split. It also preserves
the base conditional `P(X>=50|X>=10)`. Every probability change is therefore
renormalized and has an explicit destination.

## Exponential tilt

The smooth model uses

```text
p_s(x) proportional to p_0(x) exp(s log(1+x)), s>=0.
```

Log weights are centered before exponentiation. At `s=0`, the code calls the
frozen empirical inverse CDF exactly. Positive `s` stochastically favours larger
returns in this numerical sensitivity instrument.

Neither model predicts company quality. An empirical underwriter requires
timestamped investment-time information, selected and rejected companies,
investor-level MOIC, and censoring rules. Hindsight variables are prohibited.
