import numpy as np
import pytest

from invariant.core.contracts import (
    diluted_warrant_fraction,
    excess_of_loss_payout,
    founder_warrant_terminal_value,
    principal_floor_claim,
)


def test_zero_protection_always_produces_zero_claim():
    navs = np.array([0.0, 0.5, 10.0])
    np.testing.assert_array_equal(principal_floor_claim(navs, 0.0), 0.0)


def test_nav_at_or_above_protected_principal_produces_zero_claim():
    np.testing.assert_array_equal(
        principal_floor_claim(np.array([75.0, 80.0, 100.0]), 75.0),
        np.array([0.0, 0.0, 0.0]),
    )


def test_total_wipeout_produces_exactly_protected_principal():
    assert principal_floor_claim(0.0, 75.0) == 75.0


def test_claim_is_non_negative_and_cannot_increase_with_nav():
    navs = np.linspace(0.0, 120.0, 241)
    claims = principal_floor_claim(navs, 75.0)
    assert np.all(claims >= 0)
    assert np.all(np.diff(claims) <= 0)


def test_increasing_protection_cannot_decrease_claim():
    claims = [principal_floor_claim(40.0, protected) for protected in (0.0, 25.0, 50.0, 75.0, 100.0)]
    assert np.all(np.diff(claims) >= 0)


def test_stop_loss_below_at_between_and_above_attachment_and_limit():
    losses = np.array([0.0, 4.0, 5.0, 20.0, 35.0, 36.0, 100.0])
    payouts = excess_of_loss_payout(losses, attachment=5.0, limit=30.0)
    np.testing.assert_allclose(payouts, [0.0, 0.0, 0.0, 15.0, 30.0, 30.0, 30.0])


def test_founder_warrant_round_dilution_arithmetic():
    terminal_fraction = diluted_warrant_fraction(0.02, [0.20, 0.20, 0.20])
    assert terminal_fraction == pytest.approx(0.02 * 0.8**3)
    value = founder_warrant_terminal_value(100.0, 0.02, [0.20, 0.20, 0.20])
    assert value == pytest.approx(100.0 * 0.02 * 0.8**3)
