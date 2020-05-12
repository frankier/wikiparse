from __future__ import annotations

from typing import List, Optional, TypeVar, Dict, Union
from dataclasses import asdict, dataclass, field
from wikiparse.utils.wikicode import TextTreeList
from .assoc.models import PipelineResult
from .enums import DerivationType, RelationType
from .utils.dataclasses import MergeMixin


@dataclass
class Defn:
    raw_defn: str
    cleaned_defn: str
    stripped_defn: str
    grams: List[PipelineResult]
    subsenses: List[Defn] = field(default_factory=list)

    fi_examples: List[Example] = field(default_factory=list)
    bi_examples: List[Example] = field(default_factory=list)
    non_gloss: bool = False
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
class EtymologyHeading:
    ety_idx: Optional[int]
    etys: List[Etymology]
    poses: List[str]

    def tagged_dict(self):
        d = asdict(self)
        d["tag"] = "etymology-heading"
        return d


@dataclass
class EtymologyBit:
    headword: str
    alt: Optional[str] = None


@dataclass
class Etymology:
    type: DerivationType
    bits: List[EtymologyBit]
    raw_frag: str


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
