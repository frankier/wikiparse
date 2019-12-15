import re
from mwparserfromhell import parse
from typing import List

from .utils.nlp import BRACKET_RE, EQUALS_RE, detect_fi_en, has_grammar_word
from .utils.wikicode import block_templates
from .models import AssocBits
from .gram_words import (
    TRANSITIVITY,
    PERSONAL,
    VERB_WORDS,
    VERB_TO_NOMINAL,
    NOMINAL_WORDS,
    grammar_word_tokeniser,
    GRAMMAR_WORDS,
)
from .exceptions import (
    get_strictness,
    EXTRA_STRICT,
    unknown_structure,
    UnknownStructureException,
)

BIT_STOPWORDS = [
    "in",
    # XXX: should capture information about this
    "or",
]
GRAMMAR_NOTE_RE = re.compile(r"\([^\)]*\b({})\b[^\)]*\)".format("|".join(GRAMMAR_WORDS)))


def tokenise_grammar_words(bit: str) -> List[str]:
    bit_tokens = bit.split()
    return grammar_word_tokeniser.tokenize(bit_tokens)


def parse_bit(bit: str, prefer_subj=False, prefer_nom=False):
    bit = parse(bit.strip("'")).strip_code()
    if bit in NOMINAL_WORDS or bit in (VERB_WORDS + VERB_TO_NOMINAL) and prefer_nom:
        if prefer_subj:
            yield "subj", bit
        else:
            yield "obj", bit
    elif bit in VERB_WORDS:
        yield "verb", bit
    else:
        bit_tokens = tokenise_grammar_words(bit)
        for sw in BIT_STOPWORDS:
            if sw in bit_tokens:
                bit_tokens.remove(sw)
        bit = " ".join(bit_tokens)
        if ";" in bit:
            bits = bit.split(";")
            for bit in bits:
                yield from parse_bit(bit.strip())
        elif len(bit_tokens) > 1:
            # XXX: This is far too aggressive. Luckily the last case should
            # catch most problems
            prefer_nom = any(vtn in bit_tokens for vtn in VERB_TO_NOMINAL)
            for bit in bit_tokens:
                yield from parse_bit(bit, prefer_nom=prefer_nom)
        elif bit == "~":
            yield "headword", None
        elif bit:
            detected = detect_fi_en(bit)
            if detected == "en":
                unknown_structure("eng-assoc", str(bit))
            if detected != "fi":
                unknown_structure("non-fin-assoc", str(bit))
            yield "assoc", bit


def parse_assoc_bits(txt: str):
    bits = txt.split("+")
    first = True
    for bit in bits:
        bit = bit.strip().strip("'").strip()
        yield from parse_bit(bit, prefer_subj=first)
        first = False


def parse_bit_or_bits(bit: str):
    if "+" in bit:
        yield from parse_assoc_bits(bit)
    else:
        yield from parse_bit(bit)


def filter_lb_template(templates):
    filtered = [template for template in templates if template.name == "lb"]
    if filtered:
        assert len(filtered) == 1
        return filtered[0]
    return None


def proc_lb_template_assoc(templates):
    lb_template = filter_lb_template(templates)
    if lb_template:
        for idx, param in enumerate(lb_template.params[1:]):
            if param == "_":
                continue

            if param in (TRANSITIVITY + PERSONAL):
                yield "verb", str(param)
            elif "+" in param:
                yield from parse_assoc_bits(param)
            else:
                yield "qualifiers", str(param)


def proc_text_assoc(defn):
    """
    This method extracts grammar stuff from grammar notes that exist only as
    text.
    """

    new_defn = defn
    if "=" in defn:
        if defn.count("=") > 1:
            unknown_structure("too-many-=s")
        before, after = defn.split("=")
        new_defn = after
        if not has_grammar_word(before):
            unknown_structure("no-grammar-=")
        if "+" not in before:
            unknown_structure("need-+-before-=")
        for bracket in BRACKET_RE.findall(before):
            yield from parse_bit_or_bits(bracket.strip("()"))
            before = before.replace(bracket, "")
        yield from parse_assoc_bits(before)
    else:
        matches = GRAMMAR_NOTE_RE.finditer(defn)
        for match in matches:
            match_text = match.group(0)
            bit = match_text.strip().strip("()").strip()
            try:
                # Conversion to list to evaluate eagerly at this point
                note_parsed = list(parse_bit_or_bits(bit))
            except UnknownStructureException:

                # XXX: Should probably not catch all UnknownStructureException
                # exceptions but just when an en word goes into assoc (or avoid
                # exceptions

                if get_strictness() == EXTRA_STRICT:
                    raise
                yield "extra_grammar", bit
            else:
                yield from note_parsed
            new_defn = defn.replace(match_text, "")
            new_defn = new_defn.replace("  ", " ")
    yield "defn", defn


def rm_gram_assoc(defn):
    """
    This method deals with the same things as proc_text_assoc, but only removes
    them. This means we work in two passes, an extraction pass and a removal
    pass.
    """
    if "=" in defn:
        if defn.count("=") > 1:
            unknown_structure("too-many-=s")
        before, after = defn.split("=")
        return after
    else:
        matches = GRAMMAR_NOTE_RE.finditer(defn)
        for match in matches:
            match_text = match.group(0)
            defn = defn.replace(match_text, "")
        return defn


def proc_assoc(defn: str):
    """
    This method is not used elsewhere here, but is used as an entry point by
    lextract to get information for building frames.
    """
    parsed_defn = parse(defn)
    templates = block_templates(parsed_defn)
    yield from proc_lb_template_assoc(templates)
    defn_dirty = False
    for template in templates:
        parsed_defn.remove(template)
        defn_dirty = True
    if defn_dirty:
        defn = str(parsed_defn)
    for cmd, payload in proc_text_assoc(defn):
        if cmd == "defn":
            continue
        yield cmd, payload


def mk_assoc_bits(assoc_cmds) -> AssocBits:
    assoc = AssocBits()
    for assoc_cmd, bit in assoc_cmds:
        if assoc_cmd == "headword":
            # XXX: This could have useful positional information, but for now
            # we just throw it away
            continue
        getattr(assoc, assoc_cmd).append(bit)
    return assoc
