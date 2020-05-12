from ..exceptions import InterpretException
from ..context import ParseContext
from .models import (
    AssocWord,
    AssocFrame,
    AssocWordSeq,
    ContainerNode,
    AssocNodeOr,
    PlusNode,
    BarNode,
    walk,
    AssocNode,
    map_contents,
    WordType,
    OptionalNode,
    EmptyNode,
    tree_has_gram,
)
from itertools import chain
from typing import Callable, Optional, List, Tuple, Iterable, Iterator
from prettyprinter import pprint, install_extras

install_extras(exclude=["django", "ipython", "ipython_repr_pretty"])


def intersect_none(s1, s2):
    if s1 is None:
        return s2
    if s2 is None:
        return s1
    return s1.intersection(s2)


def uni(dl1, dl2):
    all_keys = {*dl1.keys(), *dl2.keys()}
    res = {}
    for key in all_keys:
        res[key] = dl1.get(key, []) + dl2.get(key, [])
    return res


def merge_assoc_words(a1: AssocWord, a2: AssocWord) -> Optional[AssocWord]:
    res = AssocWord()
    if a1.word_type is not None and a2.word_type is not None:
        return None
    res.word_type = a1.word_type or a2.word_type
    if a1.form is not None and a2.form is not None:
        return None
    res.form = a1.form or a2.form
    pos = intersect_none(a1.pos, a2.pos)
    if pos == set():
        return None
    res.pos = pos
    res.inflection_bits = uni(a1.inflection_bits, a2.inflection_bits)
    res.gram_role_bits = a1.gram_role_bits + a2.gram_role_bits
    res.lex_raw = a1.lex_raw + a2.lex_raw
    return res


def merge_many_assoc_words(assoc_words: List[AssocWord]) -> AssocWord:
    acc = AssocWord()
    for assoc_word in assoc_words:
        new_acc = merge_assoc_words(acc, assoc_word)
        if new_acc is None:
            raise InterpretException(f"Can't merge bits {assoc_words}")
        acc = new_acc
    return acc


def walk_merge_assoc_word_seq(node: AssocNode):
    if isinstance(node, AssocWordSeq):
        assoc_words = []
        others = []
        for node in node.children:
            if isinstance(node, AssocWord):
                assoc_words.append(node)
            else:
                others.append(node)
        merged = merge_many_assoc_words(assoc_words)
        if others:
            return AssocWordSeq([merged, *others])
        else:
            return merged
    elif isinstance(node, ContainerNode):
        return map_contents(walk_merge_assoc_word_seq, node)
    else:
        return node


def is_root(node: AssocNode):
    return isinstance(node, (AssocNodeOr, PlusNode))


def is_assoc_word(node: AssocNode):
    return isinstance(node, AssocWord)


def get_root(
    pred: Callable[[AssocNode], bool], node: AssocNode
) -> Tuple[Optional[AssocNode], List[AssocNode]]:
    if pred(node):
        return node, []
    elif isinstance(node, ContainerNode):
        result_idx = None
        results = []
        for idx, child in enumerate(node.contents()):
            child_result, other = get_root(pred, child)
            if child_result is not None:
                results.append(child_result)
                result_idx = idx
        if len(results) > 1:
            raise InterpretException(f"Got too many potential roots: {results}")
        elif len(results) == 1:
            others = [
                child for idx, child in enumerate(node.contents()) if idx != result_idx
            ]
            return results[0], others
    return None, []


def map_headwords(node: AssocNode, matcher, mapper) -> Tuple[bool, AssocNode]:
    if matcher(node):
        return True, mapper(node)
    elif isinstance(node, ContainerNode):
        gots = []
        child_results = []
        for child_node in node.contents():
            got, child_result = map_headwords(child_node, matcher, mapper)
            gots.append(got)
            child_results.append(child_result)
        if isinstance(node, AssocNodeOr):
            if all(child_results):
                our_got = True
            elif not any(child_results):
                our_got = False
            else:
                raise InterpretException(
                    f"Either each branch of an AssocNodeOr should have a headword, or none should: {list(node.contents())}"
                )
        else:
            num_arms = sum(gots)
            if num_arms > 1:
                raise InterpretException(
                    f"Only one arm of a container node should have a headword got {num_arms} ({gots}) from {list(node.contents())}"
                )
            our_got = bool(num_arms)
        return our_got, type(node).from_contents(child_results)
    return False, node


def ensure_headword(ctx: ParseContext, root: PlusNode):
    pos_heading = ctx.pos_heading
    assert pos_heading is not None

    def headword() -> AssocWord:
        assert pos_heading is not None
        return AssocWord(word_type=WordType.headword, pos={pos_heading.lower()})

    # Step 4.0 (Done at lexing stage) If there is a 3rd pers sing. it is
    #          the headword -- even in preference to '~'
    if any(
        (
            isinstance(child, AssocWord) and child.word_type == WordType.headword
            for child in root.children
        )
    ):
        pass
        # headword reason = ~
        # or headword reason = 3rd pers sing

    # Step 4.i If there is single word of same pos as headword it is
    #          probably the headword
    elif (
        len(root.children) == 1
        and isinstance(root.children[0], AssocWord)
        and root.children[0].word_type is None
        and root.children[0].pos is not None
        and pos_heading.lower() in root.children[0].pos
    ):
        # headword reason = single word of same pos
        root.children[0].word_type = WordType.headword

    # Step 4.ii Otherwise if there is an EmptyNode, make that the headnode
    elif any((isinstance(child, EmptyNode) for child in root.children)):
        # headword reason = EmptyNode
        for idx in chain((0, -1), range(1, len(root.children) - 1)):
            if isinstance(root.children[idx], EmptyNode):
                root.children[idx] = headword()
                break
    # Step 4.iii. Just put headword at beginning otherwise
    else:
        # headword reason = default beginning
        root.children.insert(0, headword())


def is_empty_plusnode(node: AssocNode):
    return isinstance(node, PlusNode) and all(
        (isinstance(child, EmptyNode) for child in node.contents())
    )


def remove_empty_plusnodes(node: AssocNode):
    if isinstance(node, ContainerNode):
        return type(node).from_contents(
            (
                remove_empty_plusnodes(child)
                for child in node.contents()
                if not is_empty_plusnode(child)
            )
        )
    return node


def interpret_trees(ctx: ParseContext, trees_iter: Iterable[Tuple[int, AssocNode]]):
    for _cost, tree in trees_iter:
        # If it doesn't have any grams -- it's not work interpreting
        has_gram = tree_has_gram(tree)
        if not has_gram:
            yield tree, False
        print("PRE MERGE")
        pprint(tree)
        # Step 1. Merge all AssocWordSeqs
        merged_tree = walk_merge_assoc_word_seq(tree)
        print("merged")
        pprint(merged_tree)
        # Step 1.i Find any PlusNodes with only EmptyNodes and delete them
        #  TODO: This perhaps occurs because of incorrect presidence of BarNode
        #  vs PlusNode -- an alternative would be to reparse with different
        #  precidence
        without_empty_plus = remove_empty_plusnodes(merged_tree)
        print("without_empty_plus")
        pprint(without_empty_plus)
        # Step 2. Find potential root node
        root, others = get_root(is_root, without_empty_plus)
        if root:
            pass  # root reason = only plus
        else:
            # Try to make root if one not found
            assoc_word_root, others = get_root(is_assoc_word, merged_tree)
            assert assoc_word_root is not None
            assert isinstance(assoc_word_root, AssocWord)
            root = PlusNode([assoc_word_root])

            # XXX: Possiblity at this point if there's more than once, we
            # should use POS or inflection_bits to decide whether they get
            # merged or concatonated
        assert isinstance(root, PlusNode)
        print("ROOT")
        pprint(root)
        pprint(others)
        # Step 3. Merge others
        merged_others = merge_many_assoc_words(
            [
                node
                for other in others
                for node in walk(other)
                if isinstance(node, AssocWord)
            ]
        )

        # Step 4. Ensure there is a headword
        ensure_headword(ctx, root)

        # Step 5. Put others onto headword
        got_headwords, consolidated_root = map_headwords(
            root,
            (
                lambda node: isinstance(node, AssocWord)
                and node.word_type == WordType.headword
            ),
            lambda hw: merge_assoc_words(hw, merged_others),
        )
        assert got_headwords
        assert isinstance(consolidated_root, PlusNode)

        # Step 6. Remove any remaining EmptyNodes
        final_root = PlusNode.from_contents(
            (
                child
                for child in consolidated_root.contents()
                if not isinstance(child, EmptyNode)
            )
        )
        print("FINAL_ROOT")
        pprint(final_root)
        yield final_root, True


def gen_conf_net(conf_net: Iterator[List[AssocNode]]) -> Iterator[List[AssocNode]]:
    options = next(conf_net, None)
    if options is None:
        yield []
        return
    for rest in gen_conf_net(conf_net):
        for tok in options:
            yield [tok] + rest


def flatten_comb(node: ContainerNode):
    conf_net = []
    for child in node.contents():
        conf_net.append(list(flatten(child)))
    for children in gen_conf_net(iter(conf_net)):
        yield children


def flatten(node: AssocNode) -> Iterator[AssocNode]:
    if isinstance(node, AssocNodeOr):
        for child in node.children:
            yield from flatten(child)
    elif isinstance(node, (PlusNode, BarNode)):
        yield from (PlusNode(children) for children in flatten_comb(node))
    elif isinstance(node, OptionalNode):
        yield node
        yield EmptyNode()
    elif isinstance(node, AssocWordSeq):
        yield from (AssocWordSeq(children) for children in flatten_comb(node))
    elif isinstance(node, EmptyNode):
        yield AssocWord()
    else:
        print("node", node)
        assert isinstance(node, (AssocWord, AssocFrame))
        yield node
