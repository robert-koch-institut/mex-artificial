from pydantic import Field

from mex.common.models import EXTRACTED_MODEL_CLASSES
from mex.common.settings import BaseSettings


class ArtificialSettings(BaseSettings):
    """Artificial settings submodel definition for the artificial data creator."""

    count: int = Field(
        100,
        ge=len(EXTRACTED_MODEL_CLASSES) * 2,
        lt=10e6,
        description=(
            "Amount of artificial entities to create. At least 2 per entity type are "
            "required, to ensure valid linking between the entities."
        ),
    )
    chattiness: int = Field(
        10,
        gt=1,
        le=100,
        description="Maximum amount of words to produce for textual fields.",
    )
    seed: int = Field(
        0,
        description="The seed value for faker randomness.",
    )
    locale: list[str] = Field(
        ["de_DE", "en_US"],
        description="The locale to use for faker.",
    )
