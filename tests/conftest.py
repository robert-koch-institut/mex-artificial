import pytest
from faker import Faker

from mex.artificial.helpers import create_faker, register_factories
from mex.artificial.identity import create_identities
from mex.common.models import EXTRACTED_MODEL_CLASSES

pytest_plugins = ("mex.common.testing.plugin",)


@pytest.fixture(name="faker")
def init_faker() -> Faker:
    """Return a fully configured faker instance."""
    faker = create_faker(["en_US"], 0)
    identities = create_identities(faker, len(EXTRACTED_MODEL_CLASSES) * 2)
    register_factories(faker, identities, 5)
    return faker
