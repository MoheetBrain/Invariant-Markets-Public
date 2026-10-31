# Experiment staging and validation

The planner avoids a uniform high-path Cartesian explosion:

- Core: at least 100,000 paths for the three primary portfolios across all N
  and floors, with matched nested portfolio sizes.
- Sensitivity: 10,000 paths for selection/dependence surfaces and tail models.
- Discovery: 1,000 paths across every required N, floor, selection, portfolio,
  tail and declared dependence-path combination.
- Refinement: 50,000 paths at canonical interpolated 2.5% expected-claim
  boundaries.
- Stress: 10,000 paths for hostile risk cases.

Frontiers apply cumulative monotone denoising before linear interpolation.
Every row says whether it is coarse discovery, interpolation or high-path check.
No missing crossing is silently extrapolated.

Validation includes frozen historical config hashes, exact unselected recovery,
selection monotonicity, analytical failure arithmetic, core path counts,
provenance checks, deterministic seeds, convergence, ES tail counts and Monte
Carlo standard errors. Artifact manifests hash configuration, assumptions,
sources, dependencies, experiment definitions and every generated file.

S2b-a.1 ES integrates exactly the worst `(1-confidence)` empirical probability
mass. This avoids the inherited threshold convention that can include every
zero-loss path when VaR is zero. Frozen S2a and S2b-a outputs remain unchanged.
