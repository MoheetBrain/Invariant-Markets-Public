# Start here

Invariant Markets studies whether a diversified early-stage private-company portfolio can support a principal floor at maturity at a sustainable cost.

For initial principal `K`, protection fraction `g`, maturity `T` and terminal portfolio net asset value `NAV_T`, the claim is:

\[
C_T = (gK - NAV_T)^+ = \max(gK-NAV_T,0).
\]

The economic layers are kept separate:

- **FD:** founder dilution, represented here by simple founder-warrant terminal value;
- **PP:** PlatformCo profits or liquid reserve, represented here by a first-loss reserve;
- **GS:** generic external guarantee or stop-loss, represented here by an excess-of-loss payout.

The current baseline is intentionally synthetic. One shared macro state is drawn for each portfolio. That state selects a complete distribution across total failure, partial recovery, modest success, large success and extreme winner. This creates a transparent systemic mechanism: diversification removes idiosyncratic variation but cannot remove the shared state.

The baseline runner crosses eight portfolio sizes with five protection levels. Guarantee claims and founder-warrant terminal values remain separate so their joint behaviour can be inspected without pretending warrants are liquid cash.

Run it with:

```bash
python -m invariant.cli run --config configs/base.yaml --seed 42
```

Read the generated `summary.md` for results and `manifest.json` for commit, seed, configuration and dependency provenance. Source code under `src/invariant/` is the source of truth; notebooks are reserved for exploration.
