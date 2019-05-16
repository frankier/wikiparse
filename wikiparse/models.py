from __future__ import annotations

import enum
from typing import List, Optional, TypeVar, Dict, Union
from dataclasses import asdict, dataclass, field, fields
from wikiparse.utils.wikicode import TextTreeList


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


Self = TypeVar("Self")


class MergeMixin:
    def merge(self: Self, other: Self):
        for self_field in fields(self):
            getattr(self, self_field.name).extend(getattr(other, self_field.name))


@dataclass
class AssocBits(MergeMixin):
    # Inflectional information about the subject
    subj: List[str] = field(default_factory=list)
    # Inflectional information about the verb
    verb: List[str] = field(default_factory=list)
    # Inflectional information about the object
    obj: List[str] = field(default_factory=list)
    # Associated words/collations
    assoc: List[str] = field(default_factory=list)
    # Unstructured grammar notes that we've failed to parse (or are unparseable)
    extra_grammar: List[str] = field(default_factory=list)
    # Qualifiers
    qualifiers: List[str] = field(default_factory=list)


@dataclass
class Defn:
    raw_defn: str
    cleaned_defn: str
    stripped_defn: str
    assoc: AssocBits
    subsenses: List[Defn] = field(default_factory=list)

    fi_examples: List[Example] = field(default_factory=list)
    bi_examples: List[Example] = field(default_factory=list)
    morph: Optional[Dict] = None


@dataclass
class Example(MergeMixin):
    fi: Optional[List[str]] = None
    en: Optional[List[str]] = None


@dataclass
class DefnTreeFrag(MergeMixin):
    senses: List[Defn] = field(default_factory=list)
    fi_examples: List[Example] = field(default_factory=list)
    en_examples: List[Example] = field(default_factory=list)
    bi_examples: List[Example] = field(default_factory=list)
    unk_examples: List[str] = field(default_factory=list)


@dataclass
class Etymology:
    type: DerivationType
    bits: List[str]
    raw_frag: str

    def tagged_dict(self):
        d = asdict(self)
        d["tag"] = "etymology"
        return d


@dataclass
class Relation:
    type: RelationType
    parent: str
    raw_frag: str

    def tagged_dict(self):
        d = asdict(self)
        d["tag"] = "relation"
        return d


T = TypeVar("T")
DictTree2L = Union[Dict[str, T], Dict[str, Dict[str, T]]]
TextTreeDictTree2L = DictTree2L[TextTreeList]
DefnListDictTree2L = DictTree2L[List[Defn]]
