from faker import Faker

from mex.artificial.identity import IdentityMap
from mex.artificial.provider import (
    BuilderProvider,
    IdentityProvider,
    LinkProvider,
    PatternProvider,
    TemporalEntityProvider,
    TextProvider,
)


def create_faker(locale: str, seed: int) -> Faker:
    """Create and initialize a new faker instance with the given locale and seed."""
    faker = Faker(locale)
    faker.seed_instance(seed)
    return faker


def create_factories(faker: Faker, identities: IdentityMap) -> Faker:
    """Create faker providers and register them on each factory."""
    for factory in faker.factories:
        factory.add_provider(IdentityProvider(factory, identities))
        factory.add_provider(LinkProvider(factory))
        factory.add_provider(PatternProvider(factory))
        factory.add_provider(BuilderProvider(factory))
        factory.add_provider(TextProvider(factory))
        factory.add_provider(TemporalEntityProvider(factory))
    return faker
