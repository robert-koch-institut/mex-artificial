from mex.common.models import (
    MEX_PRIMARY_SOURCE_IDENTIFIER,
    MEX_PRIMARY_SOURCE_IDENTIFIER_IN_PRIMARY_SOURCE,
    MEX_PRIMARY_SOURCE_STABLE_TARGET_ID,
    ExtractedPrimarySource,
)

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

MEX_PRIMARY_SOURCE = ExtractedPrimarySource.model_construct(
    hadPrimarySource=MEX_PRIMARY_SOURCE_STABLE_TARGET_ID,
    identifier=MEX_PRIMARY_SOURCE_IDENTIFIER,
    identifierInPrimarySource=MEX_PRIMARY_SOURCE_IDENTIFIER_IN_PRIMARY_SOURCE,
    stableTargetId=MEX_PRIMARY_SOURCE_STABLE_TARGET_ID,
)
