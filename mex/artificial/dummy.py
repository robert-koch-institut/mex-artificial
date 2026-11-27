"""Dummy persons, organizational units and organizations.

These entities are compiled from the dummy data used throughout the MEx project:

- persons: `mex-extractors/assets/raw-data/ldap/data.ldif.TEMPLATE`,
  `mex-common/tests/ldap/conftest.py` and `mex-testing` wikidata test data
- organizational units: `mex-extractors/assets/raw-data/organigram`
- organizations: `mex-testing/assets/wikidata` and `mex-common/tests/wikidata`

Each entity lists all the ways it could be referred to in a primary source, e.g.
names, display names, short names, account names, emails or external identifiers.
These synonyms are used to anonymize `forValues` and `transformValues` of mapping
fields that reference persons, units or organizations.
"""

from typing import Final

from mex.artificial.models import DummyEntity
from mex.common.types import (
    Identifier,
    MergedOrganizationalUnitIdentifier,
    MergedOrganizationIdentifier,
    MergedPersonIdentifier,
)

DUMMY_PERSONS: Final[list[DummyEntity]] = [
    DummyEntity(
        identifier="ResolvedR",
        synonyms=[
            "Roland Resolved",
            "Resolved, Roland",
            "Resolved",
            "Roland",
            "ResolvedR",
            "resolvedr@rki.de",
            "42",
            "00000000-0000-4000-8000-000000000001",
        ],
    ),
    DummyEntity(
        identifier="FelicitasJ",
        synonyms=[
            "Juturna Felicitás",
            "Felicitás, Juturna",
            "Felicitás",
            "Juturna",
            "FelicitasJ",
            "felicitasj@rki.de",
            "70",
            "00000000-0000-4000-8000-000000000002",
        ],
    ),
    DummyEntity(
        identifier="FictitiousF",
        synonyms=[
            "Frieda Fictitious",
            "Fictitious, Frieda, Dr.",
            "Fictitious, Frieda",
            "Fictitious",
            "Frieda",
            "FictitiousF",
            "frieda",
            "fictitiousf@rki.de",
            "71",
            "00000000-0000-4000-8000-000000000003",
        ],
    ),
    DummyEntity(
        identifier="SampleS",
        synonyms=[
            "Sam Sample",
            "Sample, Sam",
            "Sample",
            "Sam",
            "SampleS",
            "SampleS@mail.tld",
            "1024",
        ],
    ),
    DummyEntity(
        identifier="Q42",
        synonyms=["Robert Koch", "Koch, Robert", "Q42"],
    ),
]

DUMMY_ORGANIZATIONAL_UNITS: Final[list[DummyEntity]] = [
    DummyEntity(
        identifier="parent-unit",
        synonyms=[
            "PRNT",
            "PRNT Abteilung",
            "PARENT Dept.",
            "Abteilung",
            "Department",
            "pu@example.com",
            "PARENT@example.com",
            "parent-unit",
        ],
    ),
    DummyEntity(
        identifier="child-unit",
        synonyms=[
            "C1",
            "CHLD",
            "C1 Sub-Unit",
            "C1 Unterabteilung",
            "CHLD Unterabteilung",
            "C1: Sub Unit",
            "child-unit",
        ],
    ),
    DummyEntity(
        identifier="fg99",
        synonyms=[
            "FG 99",
            "FG99",
            "Fachgebiet 99",
            "Group 99",
            "fg@example.com",
            "fg99",
        ],
    ),
]

DUMMY_ORGANIZATIONS: Final[list[DummyEntity]] = [
    DummyEntity(
        identifier="Q679041",
        synonyms=[
            "Robert Koch-Institut",
            "Robert Koch Institute",
            "RKI",
            "IRK",
            "Q679041",
            "https://www.wikidata.org/entity/Q679041",
        ],
    ),
    DummyEntity(
        identifier="Q26678",
        synonyms=[
            "TEST",
            "BMW",
            "Q26678",
            "https://www.wikidata.org/entity/Q26678",
        ],
    ),
]

DUMMY_ENTITIES_BY_IDENTIFIER_CLASS: Final[dict[type[Identifier], list[DummyEntity]]] = {
    MergedPersonIdentifier: DUMMY_PERSONS,
    MergedOrganizationalUnitIdentifier: DUMMY_ORGANIZATIONAL_UNITS,
    MergedOrganizationIdentifier: DUMMY_ORGANIZATIONS,
}
