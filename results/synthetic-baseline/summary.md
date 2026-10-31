# Reproducible run: `baseline`

> All startup-return inputs are synthetic `SCENARIO` assumptions. These outputs are architecture tests, not empirical estimates, guarantee prices or capital requirements.

## Run identity

- Model version: `0.2.0-synthetic`
- Random seed: `42`
- Monte Carlo paths per grid point: `5,000`
- Baseline portfolio size: `100` startups
- Baseline protection fraction: `75%`
- Scenario: Five-band synthetic startup outcomes with one shared macro state per portfolio; architecture testing only.

## Baseline numerical outputs

| Quantity | Synthetic result |
|---|---:|
| Expected portfolio multiple | 1.3769x |
| Median portfolio multiple | 1.4233x |
| Probability NAV below protected principal | 24.2200% |
| Expected guarantee claim per £1 initial principal | £0.0836 |
| Median guarantee claim per £1 initial principal | £0.0000 |
| Claim VaR 95% per £1 | £0.5357 |
| Claim VaR 99% per £1 | £0.6781 |
| Claim VaR 99.5% per £1 | £0.6934 |
| Claim Expected Shortfall 95% per £1 | £0.6391 |
| Claim Expected Shortfall 99% per £1 | £0.6946 |
| Claim Expected Shortfall 99.5% per £1 | £0.7037 |
| Probability of at least one extreme winner | 54.4600% |
| Mean number of extreme winners | 0.8264 |
| Mean largest-investment share, conditional on positive NAV | 21.5005% |
| Expected founder-warrant value per £1 initial principal | £0.0141 |
| Expected generic stop-loss payout per £1 initial principal | £0.0578 |

## Diversification sweep at the baseline protection level

| Startups | Expected multiple | Claim probability | Expected claim/£1 | ES 99.5%/£1 | Largest share if NAV>0 |
|---:|---:|---:|---:|---:|---:|
| 1 | 1.4862x | 73.1600% | £0.4883 | £0.7500 | 100.0000% |
| 10 | 1.4005x | 44.1600% | £0.1807 | £0.7500 | 60.5035% |
| 50 | 1.4147x | 24.8200% | £0.0912 | £0.7233 | 29.8175% |
| 100 | 1.3769x | 24.2200% | £0.0836 | £0.7037 | 21.5005% |
| 250 | 1.3860x | 25.3200% | £0.0731 | £0.6808 | 12.8949% |
| 500 | 1.3779x | 28.3800% | £0.0729 | £0.6673 | 8.0443% |
| 1,000 | 1.3936x | 28.0800% | £0.0672 | £0.6554 | 4.4533% |
| 2,500 | 1.3875x | 29.4400% | £0.0682 | £0.6409 | 1.9512% |

## Risk-measure convention

Guarantee claims are non-negative losses expressed per £1 of initial principal: `claim/K = max(g - NAV_T/K, 0)`. Larger positive values are worse. VaR is the empirical upper-tail claim quantile. Expected Shortfall is the mean of simulated claims greater than or equal to that VaR threshold.

Founder-warrant value is reported separately and is not deducted from the guarantee claim or treated as liquid cash. The generic stop-loss output applies `min(max(loss-attachment,0),limit)` to the gross claim and does not imply insurance, reinsurance or any legal provider.

## Baseline macro-state counts

- `normal`: `3,504`
- `weak`: `1,229`
- `crisis`: `267`

## Unsupported outputs

- U: investor-capital uplift caused by protection
- K: risk capital required per £1 protected
- R: PlatformCo revenue per £1 protected

See `config.yaml` for every synthetic probability, return range, protection level and warrant assumption with units, status, source and notes.
