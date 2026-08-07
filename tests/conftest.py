import pytest
from faker import Faker

from mex.artificial.helpers import create_faker
from mex.common.models import BASE_MODEL_CLASSES

pytest_plugins = ("mex.common.testing.plugin",)


@pytest.fixture(name="faker")
def init_faker() -> Faker:
    """Return a fully configured faker instance."""
    return create_faker(["en_US"], 0, 5)


@pytest.fixture
def ids_by_type() -> dict[str, list[str]]:
    """Return a mapping of stemTypes to lists of dummy identifiers."""
    return {
        model.stemType: [
            f"{model.stemType}{str(i).zfill(21 - len(model.stemType))}"
            for i in range(1, 9)
        ]
        for model in BASE_MODEL_CLASSES
    }
