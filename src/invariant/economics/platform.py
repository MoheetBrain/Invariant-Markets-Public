"""PlatformCo scenario economics separated from the protection-risk model.

The risk model supplies claim statistics and warrant-value scenarios. This
module supplies commercial prices, fees, demand, founder acceptance, and costs.
No guarantee claim reaches PlatformCo profit unless ``platform_is_risk_bearer``
is explicitly true.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite


COMMERCIAL_PRICE_PROVENANCE = "COMMERCIAL_PRICE_SCENARIO"
BUSINESS_ASSUMPTION_PROVENANCE = "MODEL_RISK_SCENARIO"
VALUATION_PROVENANCE = "ILLUSTRATIVE_VALUATION_MULTIPLE"


@dataclass(frozen=True)
class PlatformEconomicsInputs:
    """One-period commercial assumptions with unambiguous revenue bases."""

    new_protected_capital: float
    average_outstanding_protected_capital: float
    protected_capital_charged: float
    origination_fee_rate: float
    annual_service_fee_rate: float
    investor_protection_fee_rate: float
    external_risk_provider_price_rate: float
    variable_risk_admin_cost_rate: float
    founder_warrant_value_per_new_capital: float
    platform_warrant_share: float
    variable_operating_cost_rate: float
    fixed_operating_cost: float
    performance_revenue: float = 0.0
    allow_negative_guarantee_margin: bool = False
    platform_is_risk_bearer: bool = False
    expected_claim_per_unit: float = 0.0

    def validate(self) -> None:
        amount_fields = (
            self.new_protected_capital,
            self.average_outstanding_protected_capital,
            self.protected_capital_charged,
            self.fixed_operating_cost,
            self.performance_revenue,
        )
        if any(value < 0 or not isfinite(value) for value in amount_fields):
            raise ValueError("capital, cost, and revenue amounts must be finite and non-negative")
        rates = (
            self.origination_fee_rate,
            self.annual_service_fee_rate,
            self.investor_protection_fee_rate,
            self.external_risk_provider_price_rate,
            self.variable_risk_admin_cost_rate,
            self.founder_warrant_value_per_new_capital,
            self.platform_warrant_share,
            self.variable_operating_cost_rate,
            self.expected_claim_per_unit,
        )
        if any(value < 0 or not isfinite(value) for value in rates):
            raise ValueError("economic rates must be finite and non-negative")
        if self.platform_warrant_share > 1:
            raise ValueError("platform_warrant_share cannot exceed 100%")


@dataclass(frozen=True)
class PlatformEconomicsResult:
    """Transparent one-period revenue and modeled-profit decomposition."""

    origination_revenue: float
    service_revenue: float
    guarantee_arrangement_margin: float
    warrant_revenue: float
    performance_revenue: float
    total_revenue: float
    variable_operating_cost: float
    fixed_operating_cost: float
    platform_borne_claim_cost: float
    modeled_operating_profit: float

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


def model_platform_economics(inputs: PlatformEconomicsInputs) -> PlatformEconomicsResult:
    """Calculate one period without double counting any configured cash flow."""

    inputs.validate()
    origination_revenue = inputs.new_protected_capital * inputs.origination_fee_rate
    service_revenue = (
        inputs.average_outstanding_protected_capital * inputs.annual_service_fee_rate
    )
    raw_guarantee_spread = (
        inputs.investor_protection_fee_rate
        - inputs.external_risk_provider_price_rate
        - inputs.variable_risk_admin_cost_rate
    )
    applied_spread = (
        raw_guarantee_spread
        if inputs.allow_negative_guarantee_margin
        else max(raw_guarantee_spread, 0.0)
    )
    guarantee_margin = inputs.protected_capital_charged * applied_spread
    warrant_revenue = (
        inputs.new_protected_capital
        * inputs.founder_warrant_value_per_new_capital
        * inputs.platform_warrant_share
    )
    total_revenue = (
        origination_revenue
        + service_revenue
        + guarantee_margin
        + warrant_revenue
        + inputs.performance_revenue
    )
    variable_operating_cost = (
        inputs.new_protected_capital * inputs.variable_operating_cost_rate
    )
    platform_borne_claim_cost = (
        inputs.protected_capital_charged * inputs.expected_claim_per_unit
        if inputs.platform_is_risk_bearer
        else 0.0
    )
    profit = (
        total_revenue
        - variable_operating_cost
        - inputs.fixed_operating_cost
        - platform_borne_claim_cost
    )
    return PlatformEconomicsResult(
        origination_revenue=origination_revenue,
        service_revenue=service_revenue,
        guarantee_arrangement_margin=guarantee_margin,
        warrant_revenue=warrant_revenue,
        performance_revenue=inputs.performance_revenue,
        total_revenue=total_revenue,
        variable_operating_cost=variable_operating_cost,
        fixed_operating_cost=inputs.fixed_operating_cost,
        platform_borne_claim_cost=platform_borne_claim_cost,
        modeled_operating_profit=profit,
    )


@dataclass(frozen=True)
class TenYearBusinessInputs:
    """Configurable cohort model for issuance, outstanding capital, and NPV."""

    years: int
    base_annual_unprotected_demand: float
    annual_issuance_growth_rate: float
    maturity_years: int
    demand_uplift: float
    founder_acceptance_rate: float
    origination_fee_rate: float
    annual_service_fee_rate: float
    investor_protection_fee_rate: float
    external_risk_provider_price_rate: float
    variable_risk_admin_cost_rate: float
    founder_warrant_value_per_new_capital: float
    platform_warrant_share: float
    warrant_realization_delay_years: int
    variable_operating_cost_rate: float
    initial_fixed_operating_cost: float
    operating_cost_growth_rate: float
    discount_rate: float
    platform_is_risk_bearer: bool = False
    expected_claim_per_unit: float = 0.0

    def validate(self) -> None:
        if self.years <= 0 or self.maturity_years <= 0:
            raise ValueError("years and maturity_years must be positive")
        if self.warrant_realization_delay_years < 0:
            raise ValueError("warrant realization delay cannot be negative")
        if self.base_annual_unprotected_demand < 0:
            raise ValueError("base demand cannot be negative")
        if self.demand_uplift < 0:
            raise ValueError("demand uplift cannot be negative")
        if not 0 <= self.founder_acceptance_rate <= 1:
            raise ValueError("founder acceptance must be in [0, 1]")
        if self.annual_issuance_growth_rate <= -1 or self.operating_cost_growth_rate <= -1:
            raise ValueError("growth rates must exceed -100%")
        if self.discount_rate <= -1:
            raise ValueError("discount_rate must exceed -100%")
        PlatformEconomicsInputs(
            new_protected_capital=0.0,
            average_outstanding_protected_capital=0.0,
            protected_capital_charged=0.0,
            origination_fee_rate=self.origination_fee_rate,
            annual_service_fee_rate=self.annual_service_fee_rate,
            investor_protection_fee_rate=self.investor_protection_fee_rate,
            external_risk_provider_price_rate=self.external_risk_provider_price_rate,
            variable_risk_admin_cost_rate=self.variable_risk_admin_cost_rate,
            founder_warrant_value_per_new_capital=self.founder_warrant_value_per_new_capital,
            platform_warrant_share=self.platform_warrant_share,
            variable_operating_cost_rate=self.variable_operating_cost_rate,
            fixed_operating_cost=0.0,
            platform_is_risk_bearer=self.platform_is_risk_bearer,
            expected_claim_per_unit=self.expected_claim_per_unit,
        ).validate()


def model_ten_year_business(inputs: TenYearBusinessInputs) -> list[dict[str, float | int]]:
    """Return annual cohort cash flows and discounted cumulative generation."""

    inputs.validate()
    issuance: list[float] = []
    rows: list[dict[str, float | int]] = []
    opening_outstanding = 0.0
    cumulative_cash = 0.0
    cumulative_npv = 0.0
    for year_index in range(inputs.years):
        year = year_index + 1
        offered = (
            inputs.base_annual_unprotected_demand
            * inputs.demand_uplift
            * (1.0 + inputs.annual_issuance_growth_rate) ** year_index
        )
        deployed = offered * inputs.founder_acceptance_rate
        issuance.append(deployed)
        first_active = max(0, len(issuance) - inputs.maturity_years)
        closing_outstanding = sum(issuance[first_active:])
        average_outstanding = (opening_outstanding + closing_outstanding) / 2.0
        realized_index = year_index - inputs.warrant_realization_delay_years
        realized_warrant_base = issuance[realized_index] if realized_index >= 0 else 0.0
        fixed_cost = inputs.initial_fixed_operating_cost * (
            1.0 + inputs.operating_cost_growth_rate
        ) ** year_index
        period = model_platform_economics(
            PlatformEconomicsInputs(
                new_protected_capital=deployed,
                average_outstanding_protected_capital=average_outstanding,
                protected_capital_charged=deployed,
                origination_fee_rate=inputs.origination_fee_rate,
                annual_service_fee_rate=inputs.annual_service_fee_rate,
                investor_protection_fee_rate=inputs.investor_protection_fee_rate,
                external_risk_provider_price_rate=inputs.external_risk_provider_price_rate,
                variable_risk_admin_cost_rate=inputs.variable_risk_admin_cost_rate,
                founder_warrant_value_per_new_capital=0.0,
                platform_warrant_share=inputs.platform_warrant_share,
                variable_operating_cost_rate=inputs.variable_operating_cost_rate,
                fixed_operating_cost=fixed_cost,
                platform_is_risk_bearer=inputs.platform_is_risk_bearer,
                expected_claim_per_unit=inputs.expected_claim_per_unit,
            )
        )
        warrant_revenue = (
            realized_warrant_base
            * inputs.founder_warrant_value_per_new_capital
            * inputs.platform_warrant_share
        )
        total_revenue = period.total_revenue + warrant_revenue
        profit = period.modeled_operating_profit + warrant_revenue
        cumulative_cash += profit
        discounted_profit = profit / (1.0 + inputs.discount_rate) ** year
        cumulative_npv += discounted_profit
        rows.append(
            {
                "year": year,
                "offered_protected_capital": offered,
                "annual_protected_issuance": deployed,
                "closing_protected_capital_outstanding": closing_outstanding,
                "average_protected_capital_outstanding": average_outstanding,
                "origination_revenue": period.origination_revenue,
                "service_revenue": period.service_revenue,
                "guarantee_arrangement_margin": period.guarantee_arrangement_margin,
                "warrant_revenue": warrant_revenue,
                "total_revenue": total_revenue,
                "variable_operating_cost": period.variable_operating_cost,
                "fixed_operating_cost": fixed_cost,
                "platform_borne_claim_cost": period.platform_borne_claim_cost,
                "modeled_operating_profit": profit,
                "cumulative_cash_generation": cumulative_cash,
                "discounted_modeled_operating_profit": discounted_profit,
                "cumulative_npv": cumulative_npv,
            }
        )
        opening_outstanding = closing_outstanding
    return rows


def steady_state_contribution_rate(
    origination_fee_rate: float,
    annual_service_fee_rate: float,
    outstanding_years_per_annual_issuance: float,
    investor_protection_fee_rate: float,
    external_risk_provider_price_rate: float,
    variable_risk_admin_cost_rate: float,
    founder_warrant_value_per_new_capital: float,
    platform_warrant_share: float,
    variable_operating_cost_rate: float,
) -> float:
    """Return modeled annual contribution per £1 of steady-state issuance."""

    guarantee_margin = max(
        investor_protection_fee_rate
        - external_risk_provider_price_rate
        - variable_risk_admin_cost_rate,
        0.0,
    )
    return (
        origination_fee_rate
        + annual_service_fee_rate * outstanding_years_per_annual_issuance
        + guarantee_margin
        + founder_warrant_value_per_new_capital * platform_warrant_share
        - variable_operating_cost_rate
    )


def break_even_issuance(fixed_operating_cost: float, contribution_rate: float) -> float | None:
    """Solve annual issuance required for zero modeled operating profit."""

    if fixed_operating_cost < 0:
        raise ValueError("fixed_operating_cost cannot be negative")
    if contribution_rate <= 0:
        return None
    return fixed_operating_cost / contribution_rate


def minimum_demand_uplift(
    base_unprotected_demand: float,
    founder_acceptance_rate: float,
    fixed_operating_cost: float,
    contribution_rate: float,
    target_profit: float = 0.0,
) -> float | None:
    """Invert deployable issuance to the investor-demand uplift requirement."""

    if base_unprotected_demand < 0 or fixed_operating_cost < 0:
        raise ValueError("demand and fixed cost cannot be negative")
    if not 0 <= founder_acceptance_rate <= 1:
        raise ValueError("founder_acceptance_rate must be in [0, 1]")
    denominator = base_unprotected_demand * founder_acceptance_rate * contribution_rate
    if denominator <= 0:
        return None
    return (fixed_operating_cost + target_profit) / denominator


def maximum_external_protection_price(
    annual_issuance: float,
    target_profit: float,
    profit_before_guarantee_margin: float,
    investor_protection_fee_rate: float,
    variable_risk_admin_cost_rate: float,
) -> float | None:
    """Solve the highest external price while a positive margin is required.

    ``None`` means either the target is unreachable even at zero external price,
    or non-guarantee economics already meet the target and no finite price
    boundary is identified by this arrangement-margin equation.
    """

    if annual_issuance <= 0:
        raise ValueError("annual_issuance must be positive")
    available_margin_at_zero_price = max(
        investor_protection_fee_rate - variable_risk_admin_cost_rate,
        0.0,
    )
    required_margin = (target_profit - profit_before_guarantee_margin) / annual_issuance
    if required_margin <= 0 or required_margin > available_margin_at_zero_price:
        return None
    return investor_protection_fee_rate - variable_risk_admin_cost_rate - required_margin


def illustrative_enterprise_values(
    revenue: float,
    modeled_operating_profit: float,
    revenue_multiples: tuple[float, ...],
    operating_profit_multiples: tuple[float, ...],
) -> list[dict[str, float | str]]:
    """Return valuation arithmetic explicitly labelled as illustrative."""

    if revenue < 0:
        raise ValueError("revenue cannot be negative")
    rows: list[dict[str, float | str]] = []
    for multiple in revenue_multiples:
        if multiple < 0:
            raise ValueError("valuation multiples cannot be negative")
        rows.append(
            {
                "method": "revenue_multiple",
                "metric": revenue,
                "multiple": multiple,
                "illustrative_enterprise_value": revenue * multiple,
                "provenance": VALUATION_PROVENANCE,
            }
        )
    for multiple in operating_profit_multiples:
        if multiple < 0:
            raise ValueError("valuation multiples cannot be negative")
        rows.append(
            {
                "method": "modeled_operating_profit_multiple",
                "metric": modeled_operating_profit,
                "multiple": multiple,
                "illustrative_enterprise_value": modeled_operating_profit * multiple,
                "provenance": VALUATION_PROVENANCE,
            }
        )
    return rows
