"""Command-line entry point for reproducible research runs."""

import argparse
from dataclasses import replace
from pathlib import Path

from invariant.calibration.coherence_dependence import run_empirical_coherence_dependence
from invariant.calibration.terminal_fit import run_empirically_constrained_terminal
from invariant.core.config import load_config
from invariant.models.event_driven.prototype import simulate_event_driven_prototype
from invariant.models.terminal.structural import TerminalStructuralModel
from invariant.reporting.artifacts import write_run_artifacts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Invariant Markets quantitative research laboratory")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run", help="run the synthetic reference models")
    run_parser.add_argument("--config", required=True, type=Path, help="YAML scenario configuration")
    run_parser.add_argument(
        "--seed",
        type=int,
        help="override the YAML random seed; the effective seed is saved in config.yaml",
    )
    run_parser.add_argument(
        "--output-dir", type=Path, default=Path("runs"), help="directory for generated run artifacts"
    )
    empirical_parser = subparsers.add_parser(
        "run-empirical-terminal",
        help="run the S2b-a empirically constrained terminal return model",
    )
    empirical_parser.add_argument(
        "--config", required=True, type=Path, help="YAML empirical terminal configuration"
    )
    empirical_parser.add_argument(
        "--output-dir", type=Path, default=Path("runs"), help="directory for generated run artifacts"
    )
    coherence_parser = subparsers.add_parser(
        "run-empirical-coherence-dependence",
        help="run the S2b-a.1 empirical-coherence and dependence-frontier analysis",
    )
    coherence_parser.add_argument(
        "--config", required=True, type=Path, help="YAML coherence/dependence configuration"
    )
    coherence_parser.add_argument(
        "--output-dir", type=Path, default=Path("runs"), help="directory for generated run artifacts"
    )
    return parser


def run(
    config_path: Path, output_directory: Path, seed: int | None = None
) -> Path:
    """Run the full S2a grid plus the minimal Model B prototype."""

    config = load_config(config_path)
    if seed is not None:
        config = replace(config, random_seed=seed)
    event_counts = simulate_event_driven_prototype(config)
    result = TerminalStructuralModel().simulate(config, event_counts=event_counts)
    return write_run_artifacts(config, result, output_directory, config_source=config_path)


def main() -> None:
    """Parse command-line arguments and execute the selected command."""

    arguments = build_parser().parse_args()
    if arguments.command == "run":
        run_directory = run(arguments.config, arguments.output_dir, seed=arguments.seed)
        print(f"Run written to {run_directory}")
    elif arguments.command == "run-empirical-terminal":
        run_directory = run_empirically_constrained_terminal(
            arguments.config, arguments.output_dir
        )
        print(f"Run written to {run_directory}")
    elif arguments.command == "run-empirical-coherence-dependence":
        run_directory = run_empirical_coherence_dependence(
            arguments.config, arguments.output_dir
        )
        print(f"Run written to {run_directory}")


if __name__ == "__main__":
    main()
