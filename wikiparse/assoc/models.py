from __future__ import annotations
from dataclasses import dataclass, field
import enum
from typing import (
    Dict,
    List,
    Optional,
    Union,
    Tuple,
    Any,
    Iterator,
    Set,
)
from typing_extensions import Protocol, runtime_checkable
from mwparserfromhell.wikicode import Wikicode
from ..exceptions import UnknownStructureException, ParseException, InterpretException


# @dataclass
# class OrToken:
# has_italics: bool = False
# has_bool: bool = False
# isolate_template_arg: bool = False

# Lex/tokens


@dataclass
class EmptyNode:
    pass


class CombTokenType(enum.Enum):
    plus = 1
    semicolon = 2
    template_bar = 3
    or_or = 4
    slash_or = 5


COMB_TOKEN_LOOKUP = {
    "plus": CombTokenType.plus,
    "semicolon": CombTokenType.semicolon,
    "or": CombTokenType.or_or,
    "slash": CombTokenType.slash_or,
}


@dataclass
class CombToken:
    symbol: CombTokenType
    has_italics: bool = False
    has_bold: bool = False


class BracketTokenPole(enum.Enum):
    opener = 1
    closer = 2


class BracketTokenVar(enum.Enum):
    curly = 1
    lb_template = 2


@dataclass
class BracketToken:
    polarity: BracketTokenPole
    variety: BracketTokenVar


class Eqable(Protocol):
    def __eq__(self, other: Any) -> bool:
        ...


@runtime_checkable
class SupportsShape(Protocol):
    def shape(self) -> Eqable:
        ...


class WordType(enum.Enum):
    headword = 1
    subj = 2
    obj = 3
    assoc = 4


@dataclass
class AssocWord:
    word_type: Optional[WordType] = None
    form: Optional[str] = None
    link: Optional[str] = None
    pos: Optional[Set[str]] = None
    inflection_bits: Dict[str, List[str]] = field(default_factory=dict)
    gram_role_bits: List[str] = field(default_factory=list)
    lex_raw: List[Tuple[str, str]] = field(default_factory=list)

    def shape(self) -> Tuple[bool, bool, int, int, int]:
        return (
            self.word_type is not None,
            self.form is not None,
            self.pos is not None,
            len(self.inflection_bits),
            len(self.gram_role_bits),
        )


# Parse/trees


@runtime_checkable
class ContainerNode(Protocol):
    @classmethod
    def from_contents(cls, it: Iterator[AssocNode]):
        ...

    def contents(self) -> Iterator[AssocNode]:
        ...


class ChildrenContainerNode:
    @classmethod
    def from_contents(cls, it):
        return cls(list(it))

    def contents(self):
        yield from self.children


@dataclass
class AssocNodeOr(ChildrenContainerNode):
    children: List[AssocNode]


@dataclass
class AssocWordOr(ChildrenContainerNode):
    children: List[Union[AssocWord, AssocWordSeq]]


def coherent_types(children) -> bool:
    return not children or all(
        (type(child) == type(children[0]) for child in children)  # noqa
    )


def coherent_shapes(children) -> bool:
    if not children:
        return True
    if not coherent_types(children):
        return False
    first_child = children[0]
    if not isinstance(first_child, SupportsShape):
        return False
    reference_shape = first_child.shape()
    return all(
        (
            isinstance(child, SupportsShape) and child.shape() == reference_shape
            for child in children
        )
    )


@dataclass
class AssocWordSeq(ChildrenContainerNode):
    children: List[Union[AssocFrame, AssocWordNode]]


AssocWordNode = Union[AssocWordOr, AssocWord, AssocWordSeq]


def walk(root: AssocNode) -> Iterator[AssocNode]:
    yield root
    if isinstance(root, ContainerNode):
        for child in root.contents():
            yield from walk(child)


def map_contents(mapper, container: ContainerNode) -> ContainerNode:
    return type(container).from_contents(
        (mapper(child) for child in container.contents())
    )


def flat_map_contents(mapper, container: ContainerNode) -> ContainerNode:
    return type(container).from_contents(
        (grandchild for child in container.contents() for grandchild in mapper(child))
    )


def tree_has_gram(root: AssocNode) -> bool:
    for node in walk(root):
        if not isinstance(node, AssocWord):
            continue
        return True
    return False


@dataclass
class AssocFrame:
    extra: List[str] = field(default_factory=list)
    qualifiers: List[str] = field(default_factory=list)


@dataclass
class PlusNode(ChildrenContainerNode):
    children: List[AssocNode]  # type: ignore


@dataclass
class BarNode(ChildrenContainerNode):
    children: List[AssocNode]  # type: ignore


@dataclass
class SemicolonNode:
    left: AssocNode  # type: ignore
    right: AssocNode  # type: ignore

    @classmethod
    def from_contents(cls, it):
        return cls(*it)

    def contents(self) -> Iterator[AssocNode]:
        yield self.left
        yield self.right


@dataclass
class OptionalNode:
    child: AssocNode  # type: ignore

    @classmethod
    def from_contents(cls, it):
        return cls(*it)

    def contents(self) -> Iterator[AssocNode]:
        yield self.child


AssocNode = Union[OptionalNode, PlusNode, BarNode, SemicolonNode, AssocNodeOr, AssocFrame, AssocWordNode, EmptyNode]  # type: ignore


# Tokens again


@dataclass
class TreeFragToken:
    inner: Union[AssocFrame, AssocWordNode]


Token = Union[CombToken, BracketToken, TreeFragToken]


# Identispans


class AssocSpanType(enum.Enum):
    lb_template = 1
    bracket = 2
    before_eq = 3
    qualifier_template = 4
    deriv = 5


@dataclass
class AssocSpan:
    typ: AssocSpanType
    payload: Wikicode


# Pipeline results: identispans + trees


@dataclass
class PipelineResult:
    span: AssocSpan
    tree: Optional[
        Union[AssocNode, UnknownStructureException, ParseException, InterpretException]
    ]
    tree_has_gram: bool = False


# MWE protocols


class MWETokenProtocol(Protocol):
    payload: Optional[str]
    payload_is_lemma: bool
    # Poses are implicitly OR'd
    poses: Set[str]
    # Feats can only have a single value
    feats: Dict[str, str]


class MWEProtocol(Protocol):
    tokens: List[MWETokenProtocol]
    headword: Optional[int]
