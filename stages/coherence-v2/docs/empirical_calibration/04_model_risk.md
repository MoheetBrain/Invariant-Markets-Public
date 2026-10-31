# Model risk

S2b-a does not choose a single correct terminal model. It reports a model-risk
table over:

- body distribution family
- survival-tail exponent beta
- tail cap/truncation/no-mega stress
- correlation model and rho
- portfolio size
- protection fraction

Correlation is not treated as fitted. The supported dependence family is:

```text
independent
gaussian latent factor with rho_macro in {0, .05, .10, .15, .20, .30}
student-t latent factor stress
```

For the Gaussian factor:

\[
Z_i = \sqrt{\rho}M + \sqrt{1-\rho}\epsilon_i,
\qquad U_i=\Phi(Z_i),
\qquad X_i=F^{-1}(U_i).
\]

The Student-t stress uses a common scale shock to create heavier joint tail
dependence. It is a stress case, not an empirical claim.
