from __future__ import annotations

from mwparserfromhell.nodes import Tag
from mwparserfromhell.wikicode import Template, Wikicode
from mwparserfromhell import parse
from more_itertools import peekable
from typing import List, Iterator, Tuple, Optional
from dataclasses import dataclass

INLINE_TEMPLATES = ["link", "l", "mention", "m", "qualifier", "gloss"]


def get_heading_node(wikicode: Wikicode):
    return next(wikicode.ifilter_headings())


def get_heading_string(heading_node: Wikicode):
    return heading_node.title.get(0)


def get_heading(wikicode: Wikicode):
    return get_heading_string(get_heading_node(wikicode))


def get_lead(wikicode: Wikicode):
    sections = wikicode.get_sections(levels=[], include_lead=True)
    return sections[0]


def get_level(wikicode: Wikicode, pos: int) -> int:
    level = 0
    while 1:
        next_tag = wikicode.nodes[pos + level + 1]
        if not (type(next_tag) == Tag and next_tag.wiki_markup == ":"):
            break
        level += 1
    return level


@dataclass
class TextTreeNode:
    contents: Optional[Wikicode]
    children: TextTreeList


TextTreeList = List[TextTreeNode]


def title_gen(wikicode: Wikicode) -> Iterator[Tuple[int, Tag]]:
    gen = wikicode._indexed_ifilter(matches="#", forcetype=Tag)
    prev_i = None
    for i, tag in gen:
        if tag != "#" or prev_i == i:
            continue
        yield i, tag
        prev_i = i


def parse_nested_list(wikicode: Wikicode) -> TextTreeList:
    gen = peekable(title_gen(wikicode))
    root: TextTreeNode = TextTreeNode(None, [])
    path = [root]
    prev_level = -1
    parent_levels: List[int] = []

    def true_level():
        return len(parent_levels) - 1

    for i, tag in gen:
        level = get_level(wikicode, i)
        if level > prev_level:
            parent_levels.append(prev_level)
        while parent_levels[-1] >= level:
            parent_levels.pop()
            if len(parent_levels) == 0:
                print("parent_levels", parent_levels)
                raise
            path = path[: true_level() + 2]
        try:
            parent = path[true_level()]
        except:
            print("level, prev_level", level, prev_level)
            print(path, true_level(), parent_levels)
            raise
        next_i, _ = gen.peek((None, None))
        new_node = TextTreeNode(Wikicode(wikicode.nodes[i + level + 1 : next_i]), [])
        parent.children.append(new_node)
        if level > prev_level:
            # len(path) <= level + 1:
            path.append(new_node)
            # assert len(path) == level + 2
        else:
            path[-1] = new_node
        prev_level = level
    return root.children


def double_strip(wikicode: Wikicode) -> str:
    stripped = wikicode.strip_code()
    double_stripped = parse(stripped).strip_code()
    double_stripped = double_stripped.replace("'''", "")
    double_stripped = double_stripped.replace("''", "")
    return double_stripped.strip()


def block_templates(contents: Wikicode) -> List[Template]:
    return [t for t in contents.filter_templates() if t.name not in INLINE_TEMPLATES]
