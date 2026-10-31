# Return distribution

The first empirical terminal model is a mixture:

\[
X \sim \pi_0\delta_0 + \pi_L F_L + \pi_B F_B + \pi_S F_S + \pi_T F_T.
\]

The baseline weights are derived from aggregate constraints:

| Component | Interval | Baseline mass | Evidence class |
|---|---:|---:|---|
| Complete-loss proxy | `X = 0` | 39.0% | `PROXY` |
| Partial loss | `0 < X < 1` | 26.0% | calibrated residual split |
| Ordinary success | `1 <= X < 5` | 25.0% | `OBSERVED_AGGREGATE` constraint |
| Strong success | `5 <= X < 10` | 6.0% | `OBSERVED_AGGREGATE` constraint |
| Tail | `X >= 10` | 4.0% | `OBSERVED_AGGREGATE` constraint |

The `0 < X < 1`, `1 <= X < 5` and `5 <= X < 10` bodies have two model-risk
choices:

- `log_uniform`
- `truncated_lognormal`

Neither body model is claimed to be true. They exist because the aggregate
statistics identify threshold masses but not the continuous distribution inside
each interval.
