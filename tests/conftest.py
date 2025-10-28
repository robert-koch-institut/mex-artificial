import pytest
from faker import Faker

from mex.artificial.helpers import create_faker, register_factories

pytest_plugins = ("mex.common.testing.plugin",)


@pytest.fixture(name="faker")
def init_faker() -> Faker:
    """Return a fully configured faker instance."""
    faker = create_faker(["en_US"], 0)
    register_factories(faker, 5)
    return faker
