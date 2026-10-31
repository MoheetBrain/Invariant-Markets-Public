# ADR-001: Python is primary

- Status: Accepted
- Date: 2026-08-13
- Scope: Version 1 implementation language and scientific runtime

## Context

The project needs a reproducible laboratory for terminal models, event-driven cash flows, calibration, risk metrics, reporting and tests. Several languages could express the mathematics, but a multi-language stack would make the first version harder to install, audit and reproduce. The repository is a research system, not a production latency-sensitive trading engine.

## Decision

Python is the sole implementation language for Version 1. The package lives under `src/invariant/` and uses a normal `pyproject.toml` project with a pinned Python version and committed dependency lockfile. The initial scientific stack is intentionally limited to NumPy, SciPy, pandas, Matplotlib, PyYAML and pytest; additional dependencies need a concrete research justification.

## Why

Python provides a single readable language across numerical calculation, data preparation, testing, configuration and reporting. Its scientific ecosystem is sufficient for the current problem, while type hints, pure functions and ordinary package layout support review by an outside quant who does not need a second runtime.

## Consequences

- Contributors should not introduce MATLAB, Julia, C++, TensorFlow, PyTorch, databases or web frameworks into Version 1.
- Performance is secondary to correctness and auditability; optimize only after profiling identifies a bottleneck.
- The lockfile, Python version and run manifest become part of reproducibility evidence.
- A later production system may use another language, but it must preserve the tested mathematical contracts and cross-checks.

## Revisit when

Reconsider this decision only when profiling or deployment requirements demonstrate a material limitation that cannot be addressed within Python, and only with a cross-language numerical comparison plan.
