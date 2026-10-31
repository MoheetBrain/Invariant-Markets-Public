"""Economic calculations kept separate from legal wrappers and portfolio risk."""

from invariant.economics.platform import (
    PlatformEconomicsInputs,
    PlatformEconomicsResult,
    TenYearBusinessInputs,
    break_even_issuance,
    maximum_external_protection_price,
    minimum_demand_uplift,
    model_platform_economics,
    model_ten_year_business,
)

__all__ = [
    "PlatformEconomicsInputs",
    "PlatformEconomicsResult",
    "TenYearBusinessInputs",
    "break_even_issuance",
    "maximum_external_protection_price",
    "minimum_demand_uplift",
    "model_platform_economics",
    "model_ten_year_business",
]
