from typing import List, Iterator

from mwparserfromhell.wikicode import Template
from more_itertools import chunked
from nltk.tokenize.regexp import RegexpTokenizer

from .fst import bit_fst, lb_tmpl_bit_fst
from .models import (
    Token,
    TreeFragToken,
    AssocWord,
    WordType,
    CombToken,
    CombTokenType,
    COMB_TOKEN_LOOKUP,
    BracketTokenPole,
    BracketTokenVar,
    BracketToken,
)
from ..context import ParseContext
from ..utils.fst import LazyFst
from ..utils.nlp import detect_fi_en
from ..data.gram_words import grammar_word_tokeniser
from ..exceptions import unknown_structure
from .identispan import AssocSpan, AssocSpanType


def tokenise_grammar_words(bit: str) -> List[str]:
    bit_tokens = bit.split()
    return grammar_word_tokeniser.tokenize(bit_tokens)


ORABLE_TAGS = ["case", "mood", "pass", "inf", "tense"]
SINGLE_TAGS = ["trans", "part"]
GRAM_ROLE_TAGS = ["role", "personal"]


def lex_bit_tokens(
    ctx: ParseContext, fst: LazyFst, tokens: List[str]
) -> Iterator[Token]:
    from .identispan import has_grammar_hint

    if not tokens:
        return
    lookup_res = fst.lookup_partial(tokens, longest_only=True)
    print("TOKENS", tokens)
    print("LOOKUP_RES", lookup_res)
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
        yield TreeFragToken(AssocWord(form=first))
        yield from lex_bit_tokens(ctx, fst, rest)
        return
    if len(lookup_res) != 1:
        unknown_structure(("bad-assoc-bit", "too-many-matches"), repr(tokens))
    result, rest = lookup_res[0]
    # lex_raw: Dict[str, str] = {}
    pair_iter = chunked(result, 2)
    for pair in pair_iter:
        print("pair", pair)
        assert len(pair) == 2
        tag, payload = pair
        # if tag in lex_raw and tag not in ORABLE_TAGS:
        # unknown_structure(("bad-assoc-bit", "too-many-tags"))
        # else:
        # lex_raw[tag] = payload
        if tag == "sym":
            if payload not in COMB_TOKEN_LOOKUP:
                unknown_structure(("bad-assoc-bit", "unknown-value"), tag, payload)
                continue
            sym = COMB_TOKEN_LOOKUP[payload]
            style_tag, style_payload = next(pair_iter)
            if style_tag != "style" or style_payload not in (
                "none",
                "bold",
                "italic",
                "bolditalic",
            ):
                unknown_structure(
                    ("bad-assoc-bit", "unknown-value"), style_tag, style_payload
                )
                continue
            has_italics = "italic" in style_payload
            has_bold = "bold" in style_payload
            yield CombToken(symbol=sym, has_italics=has_italics, has_bold=has_bold)
        elif tag == "pos":
            if payload == "nom":
                pos = {"noun", "adjective"}
            else:
                pos = {payload}
            yield TreeFragToken(AssocWord(pos=pos))
        elif tag == "rel":
            if payload == "direct object":
                word_type = WordType.obj
            elif payload == "headword":
                word_type = WordType.headword
            else:
                unknown_structure(("bad-assoc-bit", "unknown-value"), tag, payload)
            yield TreeFragToken(AssocWord(word_type=word_type))
        elif tag == "pers":
            # TODO: Need to stop ~ from becoming headword in this case
            if payload != "sg3":
                unknown_structure(("bad-assoc-bit", "unknown-pers"), payload)
            assoc_word = AssocWord(inflection_bits={tag: [payload]})
            if ctx.pos_heading == "Verb":
                assoc_word.word_type = WordType.headword
            yield TreeFragToken(assoc_word)
        elif tag in GRAM_ROLE_TAGS:
            # XXX: These are almost always associated with the actual headword
            yield TreeFragToken(AssocWord(gram_role_bits=[payload]))
        elif tag in ORABLE_TAGS + SINGLE_TAGS:
            yield TreeFragToken(AssocWord(inflection_bits={tag: [payload]}))
        elif tag in ("nongramcat", "poscat"):
            # Ignore (for now at least)
            continue
        else:
            unknown_structure(("bad-assoc-bit", "unknown-tag"), tag)
    yield from lex_bit_tokens(ctx, fst, rest)


def filter_double_headword(tokens: Iterator[Token]) -> Iterator[Token]:
    def is_headword(token):
        return (
            isinstance(token, TreeFragToken)
            and isinstance(token.inner, AssocWord)
            and token.inner.word_type == WordType.headword
        )

    def is_sg3_headword(token):
        return is_headword(token) and "sg3" in token.inner.inflection_bits.get(
            "pers", []
        )

    saved = []
    has_sg3_headword = False
    for token in tokens:
        print("token", token)
        saved.append(token)
        if is_sg3_headword(token):
            has_sg3_headword = True
    print("has_sg3_headword", has_sg3_headword)
    if not has_sg3_headword:
        yield from saved
        return
    for token in saved:
        print("token", token)
        if is_headword(token) and not is_sg3_headword(token):
            print("unsetting", token)
            assert isinstance(token, TreeFragToken) and isinstance(
                token.inner, AssocWord
            )
            # Should it be explicitly NOT headword?
            token.inner.word_type = None
        yield token


def lex_bit(ctx: ParseContext, fst: LazyFst, bit: str) -> Iterator[Token]:
    stripped = bit  # parse(bit).strip_code()
    tokenizer = RegexpTokenizer(r"[^\s'/\[\]]+|'+|/|\[\[|\]\]")
    tokens = tokenizer.tokenize(stripped)
    tokens = ["~" if tok == ctx.headword else tok for tok in tokens]
    yield from filter_double_headword(lex_bit_tokens(ctx, fst, tokens))


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


# def lex_assoc_bits(txt: str) -> Iterator[Token]:
# """
# Splits on +, ;, and ~.
# """
# bits = txt.split("+")
# last_after_semicolon = False
# if ";" in bits[-1]:
# last_bit = bits.pop()
# bits.extend(last_bit.split(";"))
# last_after_semicolon = True
# bits = strip_drop_bits(split_out_tidle(bits))
# for idx, bit in enumerate(bits):
# first = idx == 0
# last = idx == len(bits) - 1
# after_semicolon = last and last_after_semicolon
# bit = bit.strip().strip("'").strip()
# yield from lex_bit(bit, first=first, after_semicolon=after_semicolon)


def unparse_lb_template(ctx: ParseContext, lb_template: Template) -> Iterator[Token]:
    """
    This "unparses" an lb template and instead gets us to the lexing stage
    """
    yield BracketToken(
        polarity=BracketTokenPole.opener, variety=BracketTokenVar.lb_template
    )
    for idx, param in enumerate(lb_template.params[1:]):
        if idx > 0:
            yield CombToken(symbol=CombTokenType.template_bar)
        yield from lex_bit(ctx, lb_tmpl_bit_fst, str(param))
    yield BracketToken(
        polarity=BracketTokenPole.closer, variety=BracketTokenVar.lb_template
    )


def lex_span(ctx: ParseContext, assoc_span: AssocSpan) -> Iterator[Token]:
    if assoc_span.typ == AssocSpanType.lb_template:
        assert isinstance(assoc_span.payload, Template)
        return unparse_lb_template(ctx, assoc_span.payload)
    else:
        assert assoc_span.typ in (AssocSpanType.bracket, AssocSpanType.before_eq)
        assert isinstance(assoc_span.payload, str)
        return lex_bit(ctx, bit_fst, assoc_span.payload)
