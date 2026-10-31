# Macro, sector and effective diversification

Company `i` in sector `j` receives latent score

```text
Z_i = sqrt(rho_macro) M
    + sqrt(rho_sector) S_j
    + sqrt(1-rho_macro-rho_sector) epsilon_i.
```

The score becomes `U_i=Phi(Z_i)` and return `X_i=F_s^-1(U_i)`. This preserves
the selected marginal while introducing explicit macro and same-sector
dependence. AI-only portfolios share one sector factor. Frontier portfolios use
five independent sector factors conditional on macro.

For large `N`, idiosyncratic averages stabilize conditional on common factors.
More companies therefore cannot diversify away a bad macro state or a shared AI
state. The report solves maximum tolerable dependence rather than selecting one
preferred rho.

The effective-N table uses only

```text
N_effective = 1 / [rho + (1-rho)/N].
```

It is linear equal-correlation intuition, not a substitute for heavy-tail
simulation.
