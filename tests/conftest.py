from pathlib import Path

import pytest

from invariant.calibration.constraints import load_empirical_constraints, load_source_registry
from invariant.core.config import load_config
from invariant.experiments.config import load_selection_frontier_config
from invariant.experiments.model_factory import load_empirical_base


@pytest.fixture(scope="session")
def repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def base_config(repository_root):
    return load_config(repository_root / "configs" / "base.yaml")


@pytest.fixture
def source_registry(repository_root):
    return load_source_registry(repository_root / "data" / "calibration" / "source_registry.yaml")


@pytest.fixture
def empirical_constraints(repository_root, source_registry):
    return load_empirical_constraints(
        repository_root / "data" / "calibration" / "empirical_constraints_v1.yaml",
        source_registry,
    )


@pytest.fixture(scope="session")
def selection_frontier_config(repository_root):
    return load_selection_frontier_config(
        repository_root / "configs" / "selection_frontier_v1.yaml"
    )


@pytest.fixture(scope="session")
def empirical_base_spec(repository_root, selection_frontier_config):
    _, _, spec = load_empirical_base(selection_frontier_config, repository_root)
    return spec
