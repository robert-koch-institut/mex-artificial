from mex.common.models import (
    MEX_PRIMARY_SOURCE_IDENTIFIER_IN_PRIMARY_SOURCE,
    MEX_PRIMARY_SOURCE_STABLE_TARGET_ID,
    ExtractedPrimarySource,
)
from mex.common.types import Text

DEFAULT_LOCALE = [
    "de_DE",
    "en_US",
]
DEFAULT_MODELS = [
    "AccessPlatform",
    "Activity",
    "BibliographicResource",
    "ContactPoint",
    "Distribution",
    "Organization",
    "OrganizationalUnit",
    "Person",
    "Resource",
    "Variable",
    "VariableGroup",
]
DEFAULT_SEED = 0
DEFAULT_CHATTINESS = 10
DEFAULT_COUNT = 100
DEFAULT_RULE_VALUE_PROBABILITY = 0.33
DEFAULT_GENERATION_ATTEMPTS = 10
DEFAULT_MAPPING_REFERENCE_COUNT = 5
DEFAULT_MAPPING_EXTRA_ITEMS = 2

MEX_PRIMARY_SOURCE = ExtractedPrimarySource.model_construct(
    hadPrimarySource=MEX_PRIMARY_SOURCE_STABLE_TARGET_ID,
    identifierInPrimarySource=MEX_PRIMARY_SOURCE_IDENTIFIER_IN_PRIMARY_SOURCE,
    title=[Text(value="MEX_PRIMARY_SOURCE")],
)
