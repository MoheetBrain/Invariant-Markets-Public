# Generated runs

Each completed command-line run creates a unique directory here containing:

- `config.yaml` — canonical typed configuration;
- `results.json` — baseline arrays and all portfolio-size/protection-level metrics;
- `summary.md` — human-readable synthetic baseline report;
- `manifest.json` — commit, dependency, seed, config and input-data provenance;
- `figures/` — diagnostic plots only.

Generated run directories are ignored by Git by default.

Two runs with the same effective config and seed have byte-identical `results.json`; their run IDs and manifest timestamps are intentionally unique.
