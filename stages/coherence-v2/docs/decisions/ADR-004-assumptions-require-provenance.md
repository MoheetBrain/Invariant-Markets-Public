# ADR-004: All important assumptions require provenance

- Status: Accepted
- Date: 2026-08-13
- Scope: Parameters, configuration, reporting and validation

## Context

Quantitative research often fails audit when a number from a report, expert opinion or illustrative example silently becomes a model fact. This project must distinguish mathematical identities, observed data, fitted parameters, calibrated parameters, scenario assumptions, expert assumptions and unverified legal/commercial hypotheses.

## Decision

Every important numeric or categorical parameter must carry:

- value;
- units;
- provenance status;
- source;
- notes.

The allowed status vocabulary is `OBSERVED`, `FITTED`, `CALIBRATED`, `SCENARIO`, `EXPERT` and `LEGAL_UNVERIFIED`. Baseline numbers are explicitly synthetic/scenario values unless repository evidence establishes otherwise. Magic numbers must not be scattered through model code.

## Why

Provenance makes it possible to answer “where did this number come from?” without reverse-engineering code. It also prevents a polished simulation from creating false confidence merely because its inputs look precise.

## Consequences

- YAML is more verbose, but configuration becomes inspectable and diffable.
- Run artifacts record the canonical configuration hash, seed, dependency lock hash, Git commit and input-data hashes.
- A new calibration cannot silently overwrite a scenario; its status and source must change explicitly.
- Tests should validate configuration shape and provenance fields as well as arithmetic.
- Reports must label synthetic outputs and state which ultimate quantities remain unsupported.

## Revisit when

The vocabulary may be extended when a new evidence class is needed, but no status may weaken the distinction between identity and assumption. Any extension should update the model card, configuration validator and reporting contract together.
