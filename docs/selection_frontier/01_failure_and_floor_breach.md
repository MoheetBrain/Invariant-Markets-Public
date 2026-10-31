# Failure count and floor breach

For equal weights, `NAV_T/K` is the average investor-level terminal gross MOIC.
If `F` companies return `r_f` and survivors average `m`, then

```text
portfolio MOIC = (F/N) r_f + (1-F/N) m.
```

When `m>r_f`, natural coverage of floor `g` requires

```text
F/N <= (m-g)/(m-r_f).
```

For zero recovery this reduces to `F/N <= 1-g/m`. Integer maximum counts are
floored and tested against direct portfolio arithmetic. If `m<g`, a portfolio
with zero failures already misses the floor; the output is explicitly
infeasible rather than a misleading maximum of zero.

Three events remain distinct:

- Literal wipeout: every company returns exactly zero.
- Floor breach: portfolio average MOIC is below `g`.
- Liquidity shortfall: liquid assets cannot settle the protection obligation.

S2b-a.1 primarily estimates floor breach. It reports literal wipeout by
simulation and, for AI-only one-factor cases, by Gaussian quadrature of
`E[P(X=0|Z)^N]`. Liquidity remains uncalibrated.
