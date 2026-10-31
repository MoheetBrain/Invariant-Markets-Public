# Data policy

Version 1 uses no empirical data. All baseline and scenario numbers are synthetic and marked `SCENARIO` in YAML. Do not place unlicensed or undocumented data in the repository.

Future datasets should flow through `raw/`, `interim/`, `processed/` and `manifests/`, with source metadata, extraction date, transformation code and SHA-256 hashes. Model C must not be implemented as a historical bootstrap until those controls exist.
