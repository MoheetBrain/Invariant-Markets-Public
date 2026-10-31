"""Staged experiment planner for core, sensitivity, frontier, and stress runs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ExperimentDefinition:
    """One simulation family with explicit numerical purpose and path budget."""

    experiment_id: str
    tier: str
    purpose: str
    portfolio_construction: str
    selection_levels: tuple[str, ...]
    tail_models: tuple[str, ...]
    dependence_cases: tuple[str, ...]
    portfolio_sizes: tuple[int, ...]
    protection_fractions: tuple[float, ...]
    number_of_paths: int

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        for field in (
            "selection_levels",
            "tail_models",
            "dependence_cases",
            "portfolio_sizes",
            "protection_fractions",
        ):
            value[field] = list(value[field])
        return value


def plan_experiments(config: dict[str, Any]) -> tuple[ExperimentDefinition, ...]:
    """Return the exact staged plan without creating a blind Cartesian grid."""

    simulation = config["simulation"]
    sizes = tuple(int(value) for value in config["portfolio"]["sizes"])
    floors = tuple(float(value) for value in config["portfolio"]["protection_fractions"])
    reporting_size = int(config["portfolio"]["canonical_reporting_size"])
    surface_floors = tuple(
        float(value) for value in config["portfolio"]["surface_protection_fractions"]
    )
    refinement_sizes = tuple(
        int(value) for value in config["frontiers"]["refinement_portfolio_sizes"]
    )
    refinement_floors = tuple(
        float(value)
        for value in config["frontiers"]["refinement_protection_fractions"]
    )
    selection_levels = tuple(
        item["name"] for item in config["selection"]["target_constraint_scenarios"]
    )
    tails = tuple(item["name"] for item in config["tail_models"])
    baseline_tail = str(config["baseline_tail_model"])
    central = ("broad_venture", "hyper_selected_ai", "hyper_selected_frontier")
    definitions: list[ExperimentDefinition] = []
    for construction in central:
        selection = str(
            config["portfolio"]["constructions"][construction]["selection_level"]
        )
        definitions.append(
            ExperimentDefinition(
                experiment_id=f"core_{construction}",
                tier="core",
                purpose="Primary N and floor comparison with >=100,000 paths.",
                portfolio_construction=construction,
                selection_levels=(selection,),
                tail_models=(baseline_tail,),
                dependence_cases=("central",),
                portfolio_sizes=sizes,
                protection_fractions=floors,
                number_of_paths=int(simulation["core_paths"]),
            )
        )
    for construction in ("hyper_selected_ai", "hyper_selected_frontier"):
        definitions.append(
            ExperimentDefinition(
                experiment_id=f"surface_{construction}",
                tier="sensitivity",
                purpose="Selection by named dependence level at N=1,000.",
                portfolio_construction=construction,
                selection_levels=selection_levels,
                tail_models=(baseline_tail,),
                dependence_cases=tuple(config["dependence"]["levels"]),
                portfolio_sizes=(reporting_size,),
                protection_fractions=surface_floors,
                number_of_paths=int(simulation["surface_paths"]),
            )
        )
    for construction in central:
        definitions.append(
            ExperimentDefinition(
                experiment_id=f"tail_{construction}",
                tier="sensitivity",
                purpose="Tail-model dependence at the central N=1,000 case.",
                portfolio_construction=construction,
                selection_levels=(
                    str(config["portfolio"]["constructions"][construction]["selection_level"]),
                ),
                tail_models=tails,
                dependence_cases=("central",),
                portfolio_sizes=(reporting_size,),
                protection_fractions=surface_floors,
                number_of_paths=int(simulation["tail_sensitivity_paths"]),
            )
        )
    definitions.append(
        ExperimentDefinition(
            experiment_id="feasibility_frontier_discovery",
            tier="discovery",
            purpose="Coarse common-random-number search across N, floor, selection, type, and tail.",
            portfolio_construction="all",
            selection_levels=selection_levels,
            tail_models=tails,
            dependence_cases=tuple(
                f"d={float(item['dependence_index']):.2f}"
                for item in config["dependence"]["feasibility_path"]
            ),
            portfolio_sizes=sizes,
            protection_fractions=floors,
            number_of_paths=int(simulation["frontier_discovery_paths"]),
        )
    )
    definitions.append(
        ExperimentDefinition(
            experiment_id="frontier_refinement",
            tier="refinement",
            purpose="High-path checks around canonical interpolated feasibility boundaries.",
            portfolio_construction="three_primary_portfolios",
            selection_levels=("unselected", "hyper"),
            tail_models=(baseline_tail,),
            dependence_cases=("interpolated_boundary_neighbours",),
            portfolio_sizes=refinement_sizes,
            protection_fractions=refinement_floors,
            number_of_paths=int(simulation["frontier_refinement_paths"]),
        )
    )
    definitions.append(
        ExperimentDefinition(
            experiment_id="hostile_stress_suite",
            tier="stress",
            purpose="Risk, liquidity, demand, founder, dilution, and price falsification cases.",
            portfolio_construction="scenario_specific",
            selection_levels=("unselected", "hyper"),
            tail_models=(baseline_tail, "no_mega_winner"),
            dependence_cases=("scenario_specific",),
            portfolio_sizes=(reporting_size,),
            protection_fractions=surface_floors,
            number_of_paths=int(simulation["stress_paths"]),
        )
    )
    return tuple(definitions)
