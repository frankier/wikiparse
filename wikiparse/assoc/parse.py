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
from typing import Iterator, List, Tuple, Union
from pprint import pprint

from more_itertools import peekable

from ..exceptions import ParseException
from .models import (
    Token,
    TreeFragToken,
    AssocWordSeq,
    AssocWord,
    AssocNode,
    BracketToken,
    BracketTokenPole,
    BracketTokenVar,
    CombToken,
    CombTokenType,
    OptionalNode,
    EmptyNode,
    PlusNode,
    BarNode,
    SemicolonNode,
    AssocNodeOr,
)


CostParseIteratorExc = Iterator[Tuple[int, Union[AssocNode, ParseException]]]
CostParseIterator = Iterator[Tuple[int, AssocNode]]


def cost(x):
    return 0


def add_to_costs(x, it):
    yield from it


def skip_exceptions(peek):
    while isinstance(peek.peek(None), Exception):
        next(peek)


class SimpleJoiner:
    def unbiased(self, first_choice, second_choice):
        first_peek = peekable(first_choice)
        second_peek = peekable(second_choice)
        skip_exceptions(first_peek)
        skip_exceptions(second_peek)
        while 1:
            first = first_peek.peek(None)
            second = second_peek.peek(None)
            if first is None:
                yield from second_peek
                return
            if second is None:
                yield from first_peek
                return
            # Okay, slightly biased towards first
            if cost(first) <= cost(second):
                yield next(first_peek)
                skip_exceptions(first_peek)
            else:
                yield next(second_peek)
                skip_exceptions(second_peek)

    def biased_first(self, first_choice, alt_choice):
        choice = None
        while 1:
            choice = next(first_choice, None)
            if choice is None:
                break
            if not isinstance(choice, Exception):
                yield choice
                break
        yield from self.unbiased(first_choice, alt_choice)


default_joiner = SimpleJoiner()


def then_skip(joiner, first_choice, alt_choice, pos, lexed, min_bp):
    first_iter = first_choice(pos, lexed, min_bp)
    alt_iter = add_to_costs(1, alt_choice(pos + 1, lexed, min_bp))
    return joiner.biased_first(first_iter, alt_iter)


def infix_binding_power(tok: CombToken):
    if tok.symbol == CombTokenType.plus:
        return 8
    elif tok.symbol == CombTokenType.semicolon:
        return 4
    elif tok.symbol == CombTokenType.template_bar:
        return 2
    elif tok.symbol == CombTokenType.or_or:
        # TODO: Does italics alone actually change the precidence?
        if tok.has_bold:
            return 6
        else:
            return 10
    elif tok.symbol == CombTokenType.slash_or:
        return 12
    else:
        assert False
    # TODO: Need to integrate AssocWordSeq (which has power 9? or 11?)


def parse_bracket_pair(
    pos: int, lexed: List[Token], min_bp: int = 0
) -> CostParseIteratorExc:
    start_tok = lexed[pos]
    if (
        not isinstance(start_tok, BracketToken)
        or start_tok.polarity != BracketTokenPole.opener
    ):
        yield pos, ParseException(f"Excepted an opening bracket, got: {start_tok}", [])
        return
    for pos_after, inside in parse_left(pos + 1, lexed, min_bp):
        end_tok = lexed[pos_after]
        if (
            not isinstance(end_tok, BracketToken)
            or end_tok.polarity != BracketTokenPole.closer
            or end_tok.variety != start_tok.variety
        ):
            yield pos, ParseException(
                f"Couldn't match starting token {start_tok} with {end_tok}",
                [start_tok, inside, end_tok],
            )
            return
        if start_tok.variety == BracketTokenVar.curly:
            yield pos_after + 1, OptionalNode(inside)
        else:
            yield pos_after + 1, inside


def get_opt(l, idx):
    return l[idx] if idx < len(l) else None


def parse_left(pos: int, lexed: List[Token], min_bp: int = 0) -> CostParseIterator:
    print("parse_left", pos)
    tok = get_opt(lexed, pos)
    pprint(tok)
    if tok is None or (
        isinstance(tok, BracketToken) and tok.polarity == BracketTokenPole.closer
    ):
        # Ended too early
        yield pos, EmptyNode()
    elif isinstance(tok, CombToken):
        # Started too late
        yield from parse_infix(EmptyNode(), pos, lexed, min_bp)
    elif isinstance(tok, BracketToken):
        yield from then_skip(
            default_joiner, parse_bracket_pair, parse_left, pos, lexed, min_bp
        )
    else:
        assert isinstance(tok, TreeFragToken)
        yield from parse_infix(tok.inner, pos + 1, lexed, min_bp)


def comb_bin(comb, left, pos, lexed, min_bp):
    for next_pos, right in parse_left(pos + 1, lexed, min_bp):
        yield next_pos, comb(left, right)


def comb_poly(comb, left, pos, lexed, min_bp):
    print("comb_poly", comb, left)
    for next_pos, right in parse_left(pos + 1, lexed, min_bp):
        children = []
        if isinstance(left, comb):
            children.extend(left.children)
        else:
            children.append(left)
        if isinstance(right, comb):
            children.extend(right.children)
        else:
            children.append(right)
        yield next_pos, comb(children)


def parse_infix(
    left: AssocNode, pos: int, lexed: List[Token], min_bp: int = 0
) -> CostParseIterator:
    print("parse_infix", pos)
    pprint(left)
    tok = get_opt(lexed, pos)
    pprint(tok)
    if isinstance(tok, TreeFragToken):
        if isinstance(left, AssocWordSeq):
            result = AssocWordSeq(children=left.children + [tok.inner])
        elif isinstance(left, AssocWord):
            result = AssocWordSeq(children=[left, tok.inner])
        else:
            raise ParseException(
                "Tried to infix/postfix a TreeFragToken after {left}, which isn't an AssocWordSeq or an AssocWord"
            )
            return
        yield from parse_infix(result, pos + 1, lexed, min_bp)
    elif isinstance(tok, CombToken):
        bp = infix_binding_power(tok)
        print("bp, min_bp", bp, min_bp)
        if bp < min_bp:
            yield pos, left
            return
        if tok.symbol == CombTokenType.plus:
            yield from comb_poly(PlusNode, left, pos, lexed, bp)
        elif tok.symbol == CombTokenType.semicolon:
            yield from comb_bin(SemicolonNode, left, pos, lexed, bp)
        elif tok.symbol == CombTokenType.template_bar:
            yield from comb_poly(BarNode, left, pos, lexed, bp)
        elif tok.symbol == CombTokenType.or_or:
            yield from comb_bin(
                lambda left, right: AssocNodeOr([left, right]), left, pos, lexed, bp
            )
        else:
            assert tok.symbol == CombTokenType.slash_or
    else:
        assert tok is None or (
            isinstance(tok, BracketToken) and tok.polarity == BracketTokenPole.closer
        )
        yield pos, left


def parse(lexed: List[Token]) -> CostParseIterator:
    return parse_left(0, lexed)
    """
    lexed_peek = peekable(lexed)
    peek = lexed_peek.peek(None)
    if peek is None or (isinstance(peek, BracketToken) and peek:
        yield EmptyNode()
        return
    tok = next(lexed_peek)
    left = parse_left(tok, lexed)
    Token = Union[, , ]
        if
        # BITS = (BIT) ('+' BIT)+ (';' BIT)?
        if isinstance(tok, )
    if "+" in bracket_contents:
        token_bits = bracket_contents.split("+")
        token_bits[0]

        if ";" in token_bits[-1]:
            last_bit = token_bits.pop()
            token_bits.extend(last_bit.split(";"))
            last_after_semicolon = True
        bits = strip_drop_bits(split_out_tidle(bits))
        for idx, bit in enumerate(bits):
            first = idx == 0
            last = idx == len(bits) - 1
            after_semicolon = last and last_after_semicolon
            bit = bit.strip().strip("'").strip()
    else:
        bracket_contents
        merge_tokens()


def lex_then_parse(lexable: str) -> List[AssocNode]:
    return parse(lex_bit(lexable))
    """
