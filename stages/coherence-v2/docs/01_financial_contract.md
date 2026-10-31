# Financial contract

## Variables

| Symbol | Meaning | Units |
|---|---|---|
| `K` | Initial investor principal | Currency |
| `g` | Protected principal fraction | Fraction in `[0,1]` |
| `T` | Maturity | Years |
| `N` | Number of startups | Count |
| `NAV_T` | Portfolio net asset value at maturity | Currency |
| `C_T` | Principal-floor claim | Currency |
| `FD` | Founder dilution / founder-warrant support | Currency or equity claim, depending on contract |
| `PP` | Platform profits or reserve first-loss support | Currency |
| `GS` | External guarantee or stop-loss support | Currency |

The terminal claim is `C_T = max(gK - NAV_T, 0)`. It is never negative and, for non-negative NAV, cannot exceed `gK`.

The layers in this repository are an economic decomposition, not a legal priority waterfall. In S2a the gross guarantee claim, founder-warrant value and generic stop-loss payout are reported separately. Founder warrants are not assumed liquid and are not deducted from the claim. The actual enforceability, priority, liquidity and counterparty obligations remain unverified.

For initial warrant percentage `q_0` and financing-round dilution percentages `d_r`, the simple terminal warrant fraction is:

\[
q_T=q_0\prod_r(1-d_r).
\]
