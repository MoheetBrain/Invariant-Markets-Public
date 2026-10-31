import numpy as np

from invariant.core.metrics import empirical_expected_shortfall, empirical_var, largest_investment_share


def test_upper_tail_loss_metrics_are_ordered():
    losses = np.arange(100, dtype=float)
    assert empirical_var(losses, 0.99) >= empirical_var(losses, 0.95)
    assert empirical_expected_shortfall(losses, 0.99) >= empirical_var(losses, 0.99)


def test_largest_investment_share_uses_terminal_value_and_handles_wipeout():
    returns = np.array([[1.0, 1.0, 2.0], [0.0, 0.0, 0.0]])
    np.testing.assert_allclose(largest_investment_share(returns), [0.5, 0.0])
