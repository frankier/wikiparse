"""
Identify spans of assoc (= collocations + grammar notes with cases such as
elative inline with definitions). They usually look a bit like the brackets
in the previous sentence.
"""

import re
from typing import List, Iterable, Optional
from ..data.gram_words import GRAMMAR_WORDS
from ..exceptions import unknown_structure
from .models import AssocSpan, AssocSpanType
from mwparserfromhell import parse


GRAMMAR_WORD_RE_STR = r"\b({})\b".format("|".join(GRAMMAR_WORDS))
GRAMMAR_WORD_RE = re.compile(GRAMMAR_WORD_RE_STR)
GRAMMAR_HINT_RE_STR = r"(({})|~|\+)".format(GRAMMAR_WORD_RE_STR)
GRAMMAR_HINT_RE = re.compile(GRAMMAR_HINT_RE_STR)
GRAMMAR_NOTE_RE = re.compile(r"\([^\)]*{}[^\)]*\)".format(GRAMMAR_HINT_RE_STR))


def has_grammar_hint(txt: str) -> bool:
    return GRAMMAR_HINT_RE.search(txt) is not None


def has_grammar_word(txt: str) -> bool:
    return GRAMMAR_WORD_RE.search(txt) is not None


def iter_grammar_notes(defn) -> Iterable[str]:
    matches = GRAMMAR_NOTE_RE.finditer(defn)
    for match in matches:
        yield match.group(0)


def filter_lb_template(templates):
    filtered = [template for template in templates if template.name == "lb"]
    if filtered:
        if len(filtered) > 1:
            unknown_structure("more-than-one-lb")
        return filtered[0]
    return None


def identispan_lb_tmpl(templates) -> Optional[AssocSpan]:
    lb_tmpl = filter_lb_template(templates)
    if not lb_tmpl:
        return None
    return AssocSpan(typ=AssocSpanType.lb_template, payload=lb_tmpl,)


def identispan_text(defn: str) -> List[AssocSpan]:
    """
    This method extracts grammar stuff from grammar notes that exist only as
    text.
    """
    from ..utils.nlp import BRACKET_RE

    spans: List[AssocSpan] = []
    if "=" in defn:
        if defn.count("=") > 1:
            unknown_structure("too-many-=s")
        before = defn.split("=", 1)[0]
        if not has_grammar_hint(before):
            unknown_structure("no-grammar-=")
        if "+" not in before:
            unknown_structure("need-+-before-=")
        for bracket in BRACKET_RE.findall(before):
            spans.append(
                AssocSpan(typ=AssocSpanType.bracket, payload=bracket.strip("()"),)
            )
            before = before.replace(bracket, "")
        spans.append(AssocSpan(typ=AssocSpanType.before_eq, payload=parse(before)))
        return spans
    else:
        for match_text in iter_grammar_notes(defn):
            spans.append(
                AssocSpan(
                    typ=AssocSpanType.bracket,
                    payload=parse(match_text.strip().strip("()").strip()),
                )
            )
            defn = defn.replace(match_text, "")
        return spans


def identispan_all(defn: str) -> List[AssocSpan]:
    from ..utils.wikicode import block_templates

    result: List[AssocSpan] = []
    parsed_defn = parse(defn)
    templates = block_templates(parsed_defn)
    tmpl_span = identispan_lb_tmpl(templates)
    if tmpl_span is not None:
        result.append(tmpl_span)
    defn_dirty = False
    for template in templates:
        parsed_defn.remove(template)
        defn_dirty = True
    if defn_dirty:
        defn = str(parsed_defn)
    result.extend(identispan_text(defn))
    return result


def identispan_text_rm(defn):
    """
    This method deals with the same things as identispan, but only removes
    them. This means we work in two passes, an extraction pass and a removal
    pass.
    """

    if "=" in defn:
        if defn.count("=") > 1:
            unknown_structure("too-many-=s")
        before, after = defn.split("=")
        return after
    else:
        for match_text in iter_grammar_notes(defn):
            defn = defn.replace(match_text, "")
        return defn
