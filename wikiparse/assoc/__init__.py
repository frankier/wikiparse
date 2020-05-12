from typing import Optional, List, Union, Tuple
from pprint import pprint

from .models import AssocNode, PipelineResult, tree_has_gram
from .identispan import identispan_text_rm, AssocSpan
from ..exceptions import UnknownStructureException, ParseException, InterpretException
from ..context import ParseContext

__all__ = ["proc_assoc", "identispan_text_rm", "pipeline_span", "tree_has_gram"]


def is_bad_assoc(exc):
    nick = exc.log["nick"]
    return isinstance(nick, tuple) and nick[0] == "bad-assoc-bit"


def pipeline_span(
    ctx: ParseContext, span: AssocSpan
) -> Tuple[Optional[AssocNode], bool]:
    from .lex import lex_span
    from .parse import parse
    from .interpret import interpret_trees

    try:
        print("pipeline_span", ctx)
        lexed = list(lex_span(ctx, span))
        print("lexed")
        pprint(lexed)
        trees_iter = parse(lexed)
        interpreted_tree_iter = interpret_trees(ctx, trees_iter)
        return next(interpreted_tree_iter, (None, False))
    except UnknownStructureException as exc:
        if is_bad_assoc(exc):
            exc.add_span(span)
        raise


def pipeline_spans(ctx: ParseContext, spans: List[AssocSpan]) -> List[PipelineResult]:
    from mwparserfromhell.wikicode import Template

    result = []
    for span in spans:
        tree: Optional[
            Union[
                AssocNode, UnknownStructureException, ParseException, InterpretException
            ]
        ] = None
        try:
            tree, has_gram = pipeline_span(ctx, span)
        except UnknownStructureException as exc:
            if not is_bad_assoc(exc):
                raise
            # TODO: tests should be able to configure this to reraise
            tree = exc
            has_gram = False
        except (ParseException, InterpretException) as exc:
            # TODO: tests should be able to configure this to reraise
            tree = exc
            has_gram = False
        if isinstance(span.payload, Template):
            span.payload = str(span.payload)
        # has_gram = (
        # tree is not None
        # and not isinstance(tree, UnknownStructureException)
        # and tree_has_gram(tree)
        # )
        result.append(PipelineResult(span=span, tree=tree, tree_has_gram=has_gram))
    return result


def proc_assoc(ctx: ParseContext, defn: str) -> List[PipelineResult]:
    """
    This method is not used elsewhere here, but is used as an entry point by
    lextract to get information for building frames.
    """
    from .identispan import identispan_all

    spans = identispan_all(defn)
    return pipeline_spans(ctx, spans)
