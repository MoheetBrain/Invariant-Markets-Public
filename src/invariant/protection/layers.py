"""Wrapper-neutral protection calculations kept separate from asset value."""

from dataclasses import dataclass

import numpy as np

from invariant.core.contracts import excess_of_loss_payout


@dataclass(frozen=True)
class ProtectionLayerPayouts:
    """Gross claim and generic excess-of-loss payout for one batch."""

    gross_guarantee_claim: np.ndarray
    generic_stop_loss_payout: np.ndarray


def calculate_protection_layers(
    gross_claims: np.ndarray,
    stop_loss_attachment: float,
    stop_loss_limit: float,
) -> ProtectionLayerPayouts:
    """Evaluate generic stop-loss without treating illiquid warrants as cash."""

    claims = np.asarray(gross_claims, dtype=float)
    return ProtectionLayerPayouts(
        gross_guarantee_claim=claims,
        generic_stop_loss_payout=np.asarray(
            excess_of_loss_payout(claims, stop_loss_attachment, stop_loss_limit),
            dtype=float,
        ),
    )
