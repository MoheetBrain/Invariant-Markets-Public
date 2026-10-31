"""Named metrics for one portfolio-size/protection-level scenario."""

import numpy as np

from invariant.core.metrics import empirical_expected_shortfall, empirical_var


def build_scenario_metrics(
    terminal_multiples: np.ndarray,
    guarantee_claims_per_unit: np.ndarray,
    stop_loss_payouts_per_unit: np.ndarray,
    founder_warrant_values_per_unit: np.ndarray,
    extreme_winner_counts: np.ndarray,
    largest_investment_shares: np.ndarray,
    protection_fraction: float,
) -> dict[str, float]:
    """Calculate all required S2a outputs for one grid point.

    VaR and Expected Shortfall use an upper-tail, positive-loss convention on
    ``guarantee_claim / initial_principal``: larger positive values are worse.
    """

    positive_nav_shares = largest_investment_shares[largest_investment_shares > 0]
    mean_concentration = (
        float(np.mean(positive_nav_shares)) if positive_nav_shares.size else 0.0
    )
    metrics: dict[str, float] = {
        "expected_portfolio_multiple": float(np.mean(terminal_multiples)),
        "median_portfolio_multiple": float(np.median(terminal_multiples)),
        "probability_nav_below_protected_principal": float(
            np.mean(terminal_multiples < protection_fraction)
        ),
        "expected_guarantee_claim_per_unit": float(
            np.mean(guarantee_claims_per_unit)
        ),
        "median_guarantee_claim_per_unit": float(
            np.median(guarantee_claims_per_unit)
        ),
        "probability_at_least_one_extreme_winner": float(
            np.mean(extreme_winner_counts > 0)
        ),
        "mean_number_of_extreme_winners": float(np.mean(extreme_winner_counts)),
        "mean_largest_investment_share_conditional_on_positive_nav": mean_concentration,
        "expected_founder_warrant_value_per_unit": float(
            np.mean(founder_warrant_values_per_unit)
        ),
        "median_founder_warrant_value_per_unit": float(
            np.median(founder_warrant_values_per_unit)
        ),
        "expected_stop_loss_payout_per_unit": float(
            np.mean(stop_loss_payouts_per_unit)
        ),
        "probability_stop_loss_payout_positive": float(
            np.mean(stop_loss_payouts_per_unit > 0)
        ),
    }
    for confidence in (0.95, 0.99, 0.995):
        suffix = f"{confidence * 100:g}"
        metrics[f"guarantee_claim_var_{suffix}_per_unit"] = empirical_var(
            guarantee_claims_per_unit, confidence
        )
        metrics[
            f"guarantee_claim_expected_shortfall_{suffix}_per_unit"
        ] = empirical_expected_shortfall(guarantee_claims_per_unit, confidence)
    return metrics
