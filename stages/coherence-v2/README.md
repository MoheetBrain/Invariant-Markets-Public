# Invariant Markets

An auditable Python laboratory for one question:

> Can a highly diversified portfolio of early-stage private-company investments support a credible principal floor at maturity at an economically sustainable cost?

The repository now preserves **S2a: Reproducible Quantitative Prototype** and
adds **S2b-a: Empirically Constrained Terminal Return Model**. S2b-a constrains
terminal investment-return marginals using audited aggregate evidence, but it is
not full historical calibration, a guarantee quote, legal structure, insurance
premium or capital calculation.

## What the S2a runner does

```text
YAML configuration
→ synthetic startup outcomes
→ equal-weighted portfolio NAV
→ principal-floor claim
→ Monte Carlo distribution
→ risk metrics
→ reproducible run artifacts
```

For initial principal `K`, protection fraction `g` and terminal NAV `NAV_T`:

\[
\text{protected principal}=gK,
\qquad
C_T=\max(gK-NAV_T,0).
\]

One `NORMAL`, `WEAK` or `CRISIS` state is shared by every startup in each simulated portfolio. State-specific YAML probabilities select one of five synthetic outcome bands: total failure, partial recovery, modest success, large success or extreme winner. All probabilities and return ranges are visibly marked `SCENARIO`.

The baseline command evaluates 40 grid points: portfolio sizes `1, 10, 50, 100, 250, 500, 1,000, 2,500` crossed with protection fractions `0%, 25%, 50%, 75%, 100%`. The configured baseline point is `N=100`, `g=75%`.

## Clean installation and baseline run

Python 3.14 is pinned in `pyproject.toml`.

```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[test]'
python -m pytest
python -m invariant.cli run --config configs/base.yaml --seed 42
```

Running the final command twice with seed 42 creates two unique run directories but byte-identical `results.json` files. The effective seed override is saved in each run's canonical `config.yaml`.

## Empirically constrained terminal run

S2b-a stores aggregate observations separately from model parameters:

```bash
python -m invariant.cli run-empirical-terminal --config configs/calibrated_terminal_v1.yaml
```

The run writes `empirical_constraints.yaml`, `source_snapshot.yaml`,
`validation.json`, `sensitivity.csv`, `parameter_draw_summary.json`,
`results.json`, `summary.md`, `manifest.json` and diagnostic figures. The output
is a model-risk table for the principal-floor claim distribution, not a single
commercial insurance price.

## Empirical coherence and dependence frontier

S2b-a.1 audits the unit of observation, tests declared marginal-model variants
without force-fitting fund TVPI, and runs the Gaussian rho frontier plus
alternative dependence and winner-deletion stresses:

```bash
python -m invariant.cli run-empirical-coherence-dependence \
  --config configs/research/empirical_coherence_dependence_v2.yaml
```

The frozen V1 marginal remains unchanged. The V2 designation refers to the
analysis layer; public aggregates are insufficient to justify a new central
unique-company marginal model.

## Outputs

Every `runs/<run-id>/` contains:

- `config.yaml` — complete effective configuration with parameter provenance;
- `results.json` — baseline Monte Carlo arrays and all 40 aggregate grid results;
- `summary.md` — baseline metrics, diversification table and conventions;
- `manifest.json` — seed, Git commit, dirty-worktree flag, Python/model versions and config/lock hashes;
- `figures/` — expected claim, claim probability and 99.5% Expected Shortfall versus portfolio size, plus baseline return and claim distributions.

Guarantee loss metrics use a positive upper-tail convention and are expressed per £1 initial principal. Founder-warrant value is reported separately; it is not treated as liquid cash or deducted from claims. The generic stop-loss calculation does not imply insurance, reinsurance or a specific legal provider.

## Three model architectures

- **Model A — terminal structural:** the current five-band synthetic reference model and diversification grid.
- **Model B — event-driven:** a minimal state-machine prototype; the intended long-run primary model.
- **Model C — historical bootstrap:** interface only; no historical data are fabricated.

Start with [the conceptual guide](docs/00_start_here.md), [model card](MODEL_CARD.md), [assumptions register](ASSUMPTIONS.md), [status](STATUS.md), [empirical calibration docs](docs/empirical_calibration/00_overview.md), [unit-of-observation audit](docs/empirical_calibration/unit_of_observation_audit.md) and [architecture decisions](docs/decisions/README.md). Data policy and future fields are in [data/README.md](data/README.md), [the data dictionary](docs/05_data_dictionary.md) and [calibration metadata](data/calibration/README.md).
