# Reproducibility

1. Inspect `PROVENANCE.json`, the two saved result directories and their manifests.
   Original result files are byte-identical to the preserved local artifacts.
   Run `python scripts/verify_release.py` to verify every published file hash.
2. Install the root in Python 3.14 with `python -m pip install -e '.[test]'` and run
   `python -m pytest`. This verifies the selection-frontier implementation with
   lightweight tests. It does not regenerate the full research experiment.
3. To test the independent completed V2 stage, change to `stages/coherence-v2`,
   create a **separate** Python 3.14 environment, install `-e '.[test]'`, and run
   `python -m pytest`. Do not mix the two editable `invariant` packages.
4. V2's original command is `python -m invariant.cli run-empirical-coherence-v2
   --config configs/research/empirical_coherence_dependence_v2.yaml` (one line,
   from the V2 directory). Its full run is optional and can be substantial.
5. The root selection command is `python -m invariant.cli run-selection-frontier
   --config configs/selection_frontier_v1.yaml` (one line). The configured core
   uses 100,000 paths and additional scenario stages. No completed output of
   this command was located or generated for publication.

The synthetic baseline's saved manifest records an initial Git commit and a dirty
worktree. Its effective config and output are preserved, but the exact historical
working-tree source is not recoverable from that manifest alone. The clean V2
manifest identifies source commit `1dff3df5be8f2588290d6da535ca69aac0f8b2ce`.

The environment pins Python 3.14 and direct dependencies in `pyproject.toml` and
`requirements.lock`. Full simulations were not rerun for publication. Public
release commits have independent identities, so rerun manifests will naturally
record new commit hashes and timestamps.
