# ADR-003: Exclude the legal wrapper from core mathematics

- Status: Accepted
- Date: 2026-08-13
- Scope: Economic model boundary and legal/commercial assumptions

## Context

The economic layers could eventually be implemented through many structures: an insurer, reinsurer, bank, institutional counterparty, SPV, structured note, reserve arrangement or another legally valid wrapper. Their enforceability, capital treatment, tax treatment, governance and priority of claims are not established by the economic question alone.

Hard-coding one jurisdiction or wrapper into the mathematical core would make a scenario assumption look like a theorem and would make alternative implementations unnecessarily expensive to compare.

## Decision

The mathematical core models wrapper-neutral economic primitives only:

- founder-warrant or founder-dilution support;
- liquid PlatformCo reserve or first-loss support;
- generic guarantee or excess-of-loss support.

The core must not assume Luxembourg, the UK, an SPV, insurance, reinsurance, structured notes or any specific legal priority waterfall. Legal and commercial hypotheses remain separate, provenance-labelled inputs and documentation.

## Why

This keeps the research question focused on whether the economics can work before a legal structure is selected. It allows the same terminal claim and loss distribution to be tested against multiple possible risk-transfer arrangements later, without changing the underlying financial identity.

## Consequences

- `protection/` contains economic payout arithmetic, not legal advice or contract drafting.
- `LEGAL_UNVERIFIED` is a valid provenance status and must remain visible in reports.
- A generic stop-loss payout must not be described as an available insurance or reinsurance contract.
- Legal feasibility, counterparty risk, accounting, tax and regulatory capital require separate workstreams and evidence.
- Comparison of wrappers must occur at an interface boundary above the core, with explicit term mappings and legal review.

## Revisit when

Reconsider only after a specific wrapper, jurisdiction and term set has been independently reviewed by appropriate legal, regulatory, accounting and risk-transfer specialists. Even then, the wrapper-specific implementation should remain an adapter around the economic core where possible.
