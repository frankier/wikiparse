from typing import List, Optional, Iterator, Tuple, Any
from dataclasses import dataclass, asdict
from mwparserfromhell.wikicode import Wikicode, Text, Template
from more_itertools import peekable
import re

from .assoc.models import (
    AssocSpan,
    AssocSpanType,
    AssocNode,
    AssocWord,
    PlusNode,
    walk,
    PipelineResult,
    TreeFragToken,
)
from .assoc.interpret import interpret_trees
from .context import ParseContext
from .exceptions import UnknownStructureException


WORD_RE = re.compile(r"^\w+$")


@dataclass
class Deriv:
    link: Optional[str]
    disp: Optional[str]
    gloss: Optional[str]
    cats: List[str]
    grams: List[PipelineResult]

    def tagged_dict(self):
        d = asdict(self)
        d["tag"] = "deriv"
        return d


DER_CONTAINERS = {
    base + num + extra
    for base in ["col", "der"]
    for num in ["", "1", "2", "3", "4", "5"]
    for extra in ["", "-u"]
} | {"derived terms"}


def handle_deriv(
    ctx: ParseContext,
    linkish: Wikicode,
    disp: Optional[str] = None,
    gloss: Optional[str] = None,
    cats: List[str] = [],
):
    """
    At this point we have found all the bits, but we don't yet know:

     1. Whether linkish can truely be a link, or if it container non linky
        stuff like templates

     2. Whether linkish also contains grammar notes
    """
    from .assoc.parse import parse
    from .assoc.lex import lex_span

    span = AssocSpan(typ=AssocSpanType.deriv, payload=linkish)
    linkish_str = str(linkish).strip()
    if WORD_RE.match(linkish_str):
        # If it's just a single word we can safely assume it's Finnish and shortcut lex_span
        lexed = [TreeFragToken(AssocWord(form=linkish_str))]
    else:
        try:
            lexed = list(lex_span(ctx, span))
        except UnknownStructureException as exc:
            return "exception", exc
    trees_iter = parse(lexed)
    peek_trees_iter = peekable(trees_iter)
    # _, tree = next(trees_iter, (None, None))
    _, tree = peek_trees_iter.peek((None, None))
    if tree is not None:
        link, num_words, num_notes = search_link(tree)
        interpreted_iter = interpret_trees(ctx, peek_trees_iter)
        interpreted, has_gram = next(interpreted_iter, (None, False))
    else:
        num_words = 0
        num_notes = 0
        interpreted = None
        has_gram = False
    assert interpreted is None or isinstance(interpreted, PlusNode)
    if num_words == 1 and num_notes and link:
        # Link is found already as unambigous
        pass
    elif not num_notes:
        # No gram notes so make whole thing link
        # TODO: Should probably strip links and templates
        link = str(linkish)
    else:
        # Gram notes but clear link for a Wiktionary headword, so just set to None
        link = None
    return "deriv", Deriv(link, disp, gloss, cats, [PipelineResult(span, interpreted, has_gram)])


def search_link(root: AssocNode) -> Tuple[Optional[str], int, int]:
    """
    In the case there is a grammar note, but exactly one link on exactly one
    AssocWord, then we would like to get this link as the surface canonical
    form of the deriv
    """
    num_words = 0
    num_notes = 0
    link = None
    for node in walk(root):
        if not isinstance(node, AssocWord):
            continue
        if node.form:
            num_words += 1
        else:
            num_notes += 1
        if node.link is not None:
            link = node.link
    return link, num_words, num_notes


def handle_der_container(ctx: ParseContext, template: Wikicode) -> Iterator[Deriv]:
    """
    e.g.
    {{der2|fi|title=phrasal verbs
    |{{l|fi|[[pitää ääntä|''pitää'' ääntä]] + ''elative''|t=to [[make]] (a) [[noise]] about something {{q|e.g. about an egregious problem}}}}
    or e.g.
    {{der3|fi|title=nouns
    |pidike
    |pidin
    """
    idx = 1
    cats = []
    if template.has("title"):
        cats.append(str(template.get("title").value).strip())
    while 1:
        if not template.has(idx):
            break
        bit = template.get(idx).value
        idx += 1
        str_bit = str(bit)
        if str_bit == "fi":
            continue
        l_fi_templates = [
            idx
            for idx, template in bit._indexed_ifilter(recursive=False, forcetype=Template)
            if is_l_fi(template)
        ]
        if len(l_fi_templates) == 1:
            res = get_deriv_lb_template(ctx, bit, l_fi_templates[0])
            if res is not None:
                yield res
        elif len(l_fi_templates) == 0:
            yield handle_deriv(ctx, bit, cats=cats)
        else:
            assert False, "too many {{l|fi ... }} templates"


def is_l_fi(template: Wikicode):
    if not isinstance(template, Template):
        return False
    if template.name != "l":
        return False
    lang = str(template.get(1).value)
    return lang == "fi"


def get_tail_text(root: Wikicode, lb_idx: int) -> Optional[Wikicode]:
    """
    If an {{l|fi ...}} is followed by some text after a colon, we might want to
    put it in its description.
    """
    gathered = []
    idx = lb_idx
    idx += 1
    try:
        node = root.get(idx)
    except IndexError:
        return None
    if not isinstance(node, Text) or not node.value.startswith(":"):
        return None
    node.value = node.value[1:].strip()
    gathered.append(node)
    idx += 1
    while 1:
        try:
            node = root.get(idx)
        except IndexError:
            break
        if is_l_fi(node):
            break
        gathered.append(node)
        idx += 1
    return Wikicode(gathered)


def get_deriv_lb_template(ctx: ParseContext, parent: Wikicode, tmpl_idx: int):
    template = parent.get(tmpl_idx)
    if not template.has(2):
        return None
    link = template.get(2).value
    disp = None
    gloss = None
    cats = []
    if template.has(3):
        disp = str(template.get(3).value)
    if template.has("gloss"):
        gloss = str(template.get("gloss").value)
    if template.has("pos"):
        cats.append(str(template.get("pos").value))
    # TODO: Categories outside template
    if not gloss:
        tail_wikicode = get_tail_text(parent, tmpl_idx)
        gloss = str(tail_wikicode) if tail_wikicode else None
    return handle_deriv(ctx, link, disp, gloss, cats)


def get_deriv(ctx: ParseContext, pos_spec: Wikicode) -> Iterator[Tuple[str, Any]]:
    """
    e.g.
    {{der-top}}
    * adjectives: {{l|fi|tuleva}}
    ...
    * {{l|fi|tulla voimaan}}: {{q|of a law}} to {{l|en|take effect}}
    {{der-bottom}}
    """
    templates = pos_spec._indexed_ifilter(recursive=False, forcetype=Template)
    for idx, template in templates:
        name = str(template.name)
        if name in DER_CONTAINERS:
            for deriv in handle_der_container(ctx, template):
                yield deriv
        elif is_l_fi(template):
            deriv = get_deriv_lb_template(ctx, pos_spec, idx)
            if deriv is not None:
                yield deriv
