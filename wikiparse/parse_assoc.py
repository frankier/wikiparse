"""
Approximate EBNF --- see code for full detail

BITS = BIT ('+' BIT)+ (';' BIT)?
GRAM_NOTE = BIT | BITS
GRAM_NOTE_DEFN = '(' GRAM_NOTE ')' DEFN_TEXT
EQ_DEFN = ('(' GRAM_NOTE ')')+ '=' DEFN_TEXT
DEFN_FRAG = EQ_DEFN | GRAM_NOTE_DEFN

BIT is a bit messy:
BIT = BIT SUBJ_NOM_GRAM | OBJ_NOM_GRAM | VERB_VERB_GRAM | HEADWORD_MARKER | ASSOCIATED_WORD
Sometimes BIT can be a sequence --- if it contains ;, or if it tokenizes to multiple GRAM_WORDS
"""
import re
from mwparserfromhell import parse
from typing import List, Tuple

from .utils.nlp import BRACKET_RE, detect_fi_en
from .utils.wikicode import block_templates, double_strip
from .models import AssocBits
from .gram_words import (
    ASSOC_POS,
    TRANSITIVITY,
    PERSONAL,
    PARTICIPLE,
    grammar_word_tokeniser,
    GRAMMAR_WORDS,
    PERS,
    MOODS,
    PASS,
    ROLE,
    TENSE,
    CASES,
    RELATIONS,
    NOMINAL_WORDS,
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
GRAMMAR_WORD_RE_STR = r"\b({})\b".format("|".join(GRAMMAR_WORDS))
GRAMMAR_WORD_RE = re.compile(GRAMMAR_WORD_RE_STR)
GRAMMAR_HINT_RE_STR = r"(({})|~|\+)".format(GRAMMAR_WORD_RE_STR)
GRAMMAR_HINT_RE = re.compile(GRAMMAR_HINT_RE_STR)
GRAMMAR_NOTE_RE = re.compile(r"\([^\)]*{}[^\)]*\)".format(GRAMMAR_HINT_RE_STR))


def has_grammar_hint(txt: str) -> bool:
    return GRAMMAR_HINT_RE.search(txt) is not None


def has_grammar_word(txt: str) -> bool:
    return GRAMMAR_WORD_RE.search(txt) is not None


def tokenise_grammar_words(bit: str) -> List[str]:
    bit_tokens = bit.split()
    return grammar_word_tokeniser.tokenize(bit_tokens)


_parse_bit_fst = None


def xre_braces(expr: str) -> str:
    return "[" + expr + "]"


def xre_union(exprs: List[str]) -> str:
    return xre_braces(" | ".join(exprs))


def xre_untok(lit):
    return xre_braces(
        xre_braces(" ".join((xre_esc(bit) for bit in lit.split(" "))))
        + " : "
        + xre_esc(lit)
    )


def xre_untokuni(lits):
    return xre_union(xre_untok(lit) for lit in lits)


def xre_esc(lit):
    return '"' + lit.replace('"', '%"') + '"'


def xre_escuni(lits):
    return xre_union(xre_esc(lit) for lit in lits)


def xre_frombits(*bits):
    import hfst

    return hfst.regex("".join(bits))


def finalise_transducer(transducer):
    transducer.minimize()
    transducer.lookup_optimize()
    return transducer


class BitFst:
    _match_at_start_fst = None
    _fst = None

    @staticmethod
    def build_fst():
        # TODO:
        # Handle tagging main verb/other verb
        # e.g. saattaa: 'auxiliary, + first infinitive; in simple past tense'
        # Handle OR
        # e.g. käydä: intransitive, + inessive or adessive
        import hfst

        # Optional in CASE expression
        opt_in_case = (
            " (in:0 ",
            xre_untokuni(CASES),
            " [or:0 ",
            xre_untokuni(CASES),
            "]*)",
        )

        # Noun form descriptors / General
        noun_gen_fst = xre_frombits("[0:noun] ", xre_untokuni(NOMINAL_WORDS))

        # Noun form descriptors / POS / RELATION in CASE
        # e.g. noun/adjective in nominative or partitive
        noun_pos_case_fst = xre_frombits(
            "[0:noun] ", xre_untokuni(RELATIONS + ASSOC_POS), *opt_in_case
        )

        # Verb form descriptors / General
        gen_verb_words = PERS + PASS + TRANSITIVITY + PERSONAL + ROLE
        verb_gen_fst = xre_frombits("[0:verb] ", xre_untokuni(gen_verb_words))

        # Verb form descriptors / Mood
        mood_expr = xre_untokuni(MOODS), " (mood:0)"
        verb_mood_fst = xre_frombits(
            "[0:verb] (in:0) ", *mood_expr, " [or:0 ", *mood_expr, "]*"
        )

        # Verb form descriptors / Tense
        verb_tense_fst = xre_frombits(
            "(in:0) (simple:0) [0:verb] ", xre_untokuni(TENSE), " (tense:0)"
        )

        # Verb form descriptors / Infinitives
        norm_ords = "first:1st | 1st | second:2nd | 2nd | third:3rd | 3rd | fourth:4th"
        infinitive_fst = xre_frombits(
            "(with:0) [0:verb] (",
            xre_untokuni(PASS),
            ") [",
            norm_ords,
            " | 0:1st] infinitive",
            *opt_in_case,
        )

        # Verb form descriptors / Participles
        # e.g. passive past participle in translative
        # e.g. with active participle
        # XXX: "with" should maybe be treated like +
        participle_fst = xre_frombits(
            "(with:0) [0:verb] (",
            xre_untokuni(PASS),
            ") ",
            xre_untokuni(PARTICIPLE),
            *opt_in_case,
        )

        # Headword
        headword_fst = hfst.regex("%~:headword 0:%~")

        # Union FST
        return hfst.disjunct(
            (
                noun_gen_fst,
                noun_pos_case_fst,
                verb_gen_fst,
                verb_mood_fst,
                verb_tense_fst,
                infinitive_fst,
                participle_fst,
                headword_fst,
            )
        )

    @classmethod
    def build_match_at_start_fst(cls):
        import hfst

        transducer = cls.build_fst()
        end_then_id = hfst.regex("[?*]:0")
        transducer.input_project()
        transducer.concatenate(end_then_id)
        return transducer

    @classmethod
    def get_match_at_start_fst(cls):
        if cls._match_at_start_fst is None:
            cls._match_at_start_fst = finalise_transducer(
                cls.build_match_at_start_fst()
            )
        return cls._match_at_start_fst

    @classmethod
    def get_fst(cls):
        if cls._fst is None:
            cls._fst = finalise_transducer(cls.build_fst())
        return cls._fst

    @staticmethod
    def lookup_tokens(fst, tokens_tup):
        for _, output in fst.lookup(tokens_tup, output="raw"):
            yield tuple((tok for tok in output if tok))

    @classmethod
    def lookup_partial(
        cls, tokens: List[str], longest_only=False
    ) -> List[Tuple[List[str], List[str]]]:
        results = []
        tokens_tup = tuple(tokens)
        match_start_res = cls.lookup_tokens(cls.get_match_at_start_fst(), tokens_tup)
        if longest_only:
            new_match_start_res: List[List[str]] = []
            new_match_start_res_len = 0
            for match_input in match_start_res:
                match_input_len = len(match_input)
                if match_input_len > new_match_start_res_len:
                    new_match_start_res = []
                    new_match_start_res_len = match_input_len
                new_match_start_res.append(match_input)
            match_start_res = new_match_start_res
        for matched_input in match_start_res:
            outputs_res = cls.lookup_tokens(cls.get_fst(), matched_input)
            for output in outputs_res:
                results.append((output, tokens[len(matched_input) :]))
        return results


def parse_bit_tokens(tokens: List[str], first=False, after_semicolon=False):
    if not tokens:
        return
    lookup_res = BitFst.lookup_partial(tokens, longest_only=True)
    if len(lookup_res) == 0:
        # Might be assoc -- first rule out things that can't be
        first, rest = tokens[0], tokens[1:]
        if has_grammar_hint(first):
            unknown_structure(("bad-assoc-bit", "found-gram"), str(first))
        detected = detect_fi_en(first)
        if detected == "en":
            unknown_structure(("bad-assoc-bit", "eng-assoc"), str(first))
        if detected != "fi":
            unknown_structure(("bad-assoc-bit", "non-fin-assoc"), str(first))
        yield "assoc", first
        yield from parse_bit_tokens(rest, first=first, after_semicolon=after_semicolon)
        return
    if len(lookup_res) != 1:
        unknown_structure(("bad-assoc-bit", "too-many-matches"), repr(tokens))
    result, rest = lookup_res[0]
    tag = result[0]
    payload = " ".join(result[1:])
    if tag == "noun":
        yield "subj" if first else "obj", payload
    else:
        yield tag, payload
    yield from parse_bit_tokens(rest, first=first, after_semicolon=after_semicolon)


def parse_bit(bit: str, first=False, after_semicolon=False):
    tokens = double_strip(parse(bit)).split()
    yield from parse_bit_tokens(tokens, first=first, after_semicolon=after_semicolon)
    """
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
    """


def split_out_tidle(bits: List[str]) -> List[str]:
    new_bits = []
    num_tidles = 0
    for bit in bits:
        new_tidles = bit.count("~")
        if new_tidles == 0:
            new_bits.append(bit)
            continue
        num_tidles += new_tidles
        tidle_around = []
        sub_bits = list(bit.split("~"))
        for sub_bit_idx, sub_bit in enumerate(sub_bits):
            sub_bit = sub_bit.strip()
            if sub_bit:
                tidle_around.append(sub_bit)
            if sub_bit_idx < len(sub_bits) - 1:
                tidle_around.append("~")
        new_bits.extend(tidle_around)
    if num_tidles > 1:
        unknown_structure(("bad-assoc-bit", "too-many-tidles"), num_tidles)
    return new_bits


def strip_drop_bits(bits: List[str]) -> List[str]:
    new_bits = []
    for bit in bits:
        new_bit = bit.strip()
        if not new_bit:
            continue
        new_bits.append(new_bit)
    return new_bits


def parse_assoc_bits(txt: str):
    """
    Splits on +, ;, and ~.
    """
    bits = txt.split("+")
    last_after_semicolon = False
    if ";" in bits[-1]:
        last_bit = bits.pop()
        bits.extend(last_bit.split(";"))
        last_after_semicolon = True
    bits = strip_drop_bits(split_out_tidle(bits))
    for idx, bit in enumerate(bits):
        first = idx == 0
        last = idx == len(bits) - 1
        after_semicolon = last and last_after_semicolon
        bit = bit.strip().strip("'").strip()
        yield from parse_bit(bit, first=first, after_semicolon=after_semicolon)


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
            param_str = str(param)
            if has_grammar_hint(param_str):
                for or_part in param_str.split("'''''or'''''"):
                    yield from parse_assoc_bits(or_part)
            else:
                yield "qualifiers", param_str


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
        if not has_grammar_hint(before):
            unknown_structure("no-grammar-=")
        if "+" not in before:
            unknown_structure("need-+-before-=")
        for bracket in BRACKET_RE.findall(before):
            yield from parse_assoc_bits(bracket.strip("()"))
            before = before.replace(bracket, "")
        yield from parse_assoc_bits(before)
    else:
        matches = GRAMMAR_NOTE_RE.finditer(defn)
        for match in matches:
            match_text = match.group(0)
            bit = match_text.strip().strip("()").strip()
            try:
                # Conversion to list to evaluate eagerly at this point
                note_parsed = list(parse_assoc_bits(bit))
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
