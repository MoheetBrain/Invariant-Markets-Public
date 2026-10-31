# Calibration data policy

This directory contains source metadata and aggregate empirical constraints used
by S2b-a. It does not contain row-level historical data.

The files here are evidence inputs, not fitted model parameters:

- `source_registry.yaml` records what each external source appears to measure.
- `empirical_constraints_v1.yaml` records candidate aggregate observations,
  tolerances, provenance classes and object mapping.

Rounded public statistics are treated as aggregate constraints or proxies. They
must not be converted into exact counts or precise posteriors unless raw data
become available.
