import enum


class DerivationType(enum.Enum):
    unknown = 0
    inflection = 1
    derivation = 2
    compound = 3
    mwe = 4
    multiple = 5


class RelationType(enum.Enum):
    unknown = 0
    synonym = 1
    antonym = 2
    relevant = 3
    alt_form = 4
    misspelling = 5
    abbrv = 6
