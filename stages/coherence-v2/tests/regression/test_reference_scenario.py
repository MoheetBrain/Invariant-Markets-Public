from invariant.core.config import config_from_dict, config_to_dict
from invariant.models.terminal.structural import TerminalStructuralModel


def test_analytical_two_x_reference_scenario(base_config):
    data = config_to_dict(base_config)
    data["number_of_simulations"] = 3
    data["random_seed"] = 7
    for regime in data["macro"]["regimes"].values():
        for name, band in regime["outcome_bands"].items():
            band["probability"]["value"] = 1.0 if name == "modest_success" else 0.0
        regime["outcome_bands"]["modest_success"]["minimum_return_multiple"]["value"] = 2.0
        regime["outcome_bands"]["modest_success"]["maximum_return_multiple"]["value"] = 2.0
    result = TerminalStructuralModel().simulate(config_from_dict(data))
    assert result.baseline_terminal_multiples == (2.0, 2.0, 2.0)
    assert result.baseline_guarantee_claims_per_unit == (0.0, 0.0, 0.0)
    assert result.baseline_metrics["expected_portfolio_multiple"] == 2.0
    assert result.baseline_metrics["mean_largest_investment_share_conditional_on_positive_nav"] == 0.01
