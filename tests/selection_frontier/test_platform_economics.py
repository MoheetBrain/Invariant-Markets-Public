import pytest

from invariant.economics.platform import (
    COMMERCIAL_PRICE_PROVENANCE,
    VALUATION_PROVENANCE,
    PlatformEconomicsInputs,
    TenYearBusinessInputs,
    break_even_issuance,
    illustrative_enterprise_values,
    maximum_external_protection_price,
    minimum_demand_uplift,
    model_platform_economics,
    model_ten_year_business,
)


def test_platform_does_not_bear_claims_by_default():
    result = model_platform_economics(_period_inputs(expected_claim_per_unit=0.25))
    assert result.platform_borne_claim_cost == 0


def test_claims_enter_profit_only_when_platform_is_risk_bearer():
    result = model_platform_economics(
        _period_inputs(platform_is_risk_bearer=True, expected_claim_per_unit=0.25)
    )
    assert result.platform_borne_claim_cost == pytest.approx(25.0)


def test_revenue_streams_sum_once():
    result = model_platform_economics(_period_inputs())
    assert result.total_revenue == pytest.approx(
        result.origination_revenue
        + result.service_revenue
        + result.guarantee_arrangement_margin
        + result.warrant_revenue
        + result.performance_revenue
    )


def test_fee_percentages_use_the_correct_bases():
    result = model_platform_economics(_period_inputs())
    assert result.origination_revenue == pytest.approx(2.0)
    assert result.service_revenue == pytest.approx(2.0)
    assert result.guarantee_arrangement_margin == pytest.approx(4.0)


def test_negative_guarantee_margin_is_floored_by_default():
    inputs = _period_inputs(
        investor_protection_fee_rate=0.05,
        external_risk_provider_price_rate=0.10,
    )
    assert model_platform_economics(inputs).guarantee_arrangement_margin == 0


def test_ten_year_discounting_is_mathematically_correct():
    rows = model_ten_year_business(_business_inputs())
    first = rows[0]
    assert first["discounted_modeled_operating_profit"] == pytest.approx(
        first["modeled_operating_profit"] / 1.10
    )
    assert rows[1]["cumulative_npv"] == pytest.approx(
        rows[0]["discounted_modeled_operating_profit"]
        + rows[1]["discounted_modeled_operating_profit"]
    )


def test_break_even_solver_reproduces_toy_case():
    assert break_even_issuance(10.0, 0.10) == pytest.approx(100.0)
    assert break_even_issuance(10.0, 0.0) is None


def test_demand_uplift_solver_reproduces_toy_case():
    assert minimum_demand_uplift(100.0, 0.5, 10.0, 0.10) == pytest.approx(2.0)


def test_u_equal_one_does_not_magically_increase_offered_capital():
    rows = model_ten_year_business(_business_inputs(demand_uplift=1.0))
    assert rows[0]["offered_protected_capital"] == pytest.approx(100.0)


def test_founder_acceptance_cannot_exceed_one():
    with pytest.raises(ValueError, match="founder acceptance"):
        model_ten_year_business(_business_inputs(founder_acceptance_rate=1.01))


def test_maximum_external_price_solver_reproduces_toy_case():
    assert maximum_external_protection_price(100.0, 10.0, 5.0, 0.20, 0.05) == pytest.approx(
        0.10
    )


def test_external_price_label_remains_scenario():
    assert COMMERCIAL_PRICE_PROVENANCE == "COMMERCIAL_PRICE_SCENARIO"


def test_enterprise_value_multiples_remain_illustrative():
    rows = illustrative_enterprise_values(100.0, 20.0, (2.0,), (8.0,))
    assert {row["provenance"] for row in rows} == {VALUATION_PROVENANCE}
    assert rows[0]["illustrative_enterprise_value"] == 200.0


def _period_inputs(**overrides):
    values = {
        "new_protected_capital": 100.0,
        "average_outstanding_protected_capital": 200.0,
        "protected_capital_charged": 100.0,
        "origination_fee_rate": 0.02,
        "annual_service_fee_rate": 0.01,
        "investor_protection_fee_rate": 0.15,
        "external_risk_provider_price_rate": 0.10,
        "variable_risk_admin_cost_rate": 0.01,
        "founder_warrant_value_per_new_capital": 0.04,
        "platform_warrant_share": 0.25,
        "variable_operating_cost_rate": 0.01,
        "fixed_operating_cost": 1.0,
    }
    values.update(overrides)
    return PlatformEconomicsInputs(**values)


def _business_inputs(**overrides):
    values = {
        "years": 2,
        "base_annual_unprotected_demand": 100.0,
        "annual_issuance_growth_rate": 0.0,
        "maturity_years": 2,
        "demand_uplift": 1.0,
        "founder_acceptance_rate": 1.0,
        "origination_fee_rate": 0.02,
        "annual_service_fee_rate": 0.01,
        "investor_protection_fee_rate": 0.15,
        "external_risk_provider_price_rate": 0.10,
        "variable_risk_admin_cost_rate": 0.01,
        "founder_warrant_value_per_new_capital": 0.04,
        "platform_warrant_share": 0.25,
        "warrant_realization_delay_years": 1,
        "variable_operating_cost_rate": 0.01,
        "initial_fixed_operating_cost": 1.0,
        "operating_cost_growth_rate": 0.0,
        "discount_rate": 0.10,
    }
    values.update(overrides)
    return TenYearBusinessInputs(**values)
