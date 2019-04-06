from __future__ import annotations

# from parsepred.monkeypatch_multiprocessing import do_monkeypatch
# do_monkeypatch()
import sys
import tblib.pickling_support
from mwparserfromhell import parse
from mwparserfromhell.wikicode import Wikicode
from langdetect import DetectorFactory
import traceback
from os import makedirs
from os.path import join as pjoin
import ujson
from pybloom import ScalableBloomFilter
from typing import Any, Dict, List, Union, Optional, Tuple, Iterator
import mwxml
from mwxml.iteration import Dump, page as mwxml_iteration_page

from wikiparse.utils.wikicode import (
    get_heading_node,
    get_heading_string,
    get_heading,
    get_lead,
    parse_nested_list,
    TextTreeList,
)
from wikiparse.stats_log import get_stats_logger, set_curword

from .gram_words import POS
from .parse_defn import map_tree_to_senses
from .exceptions import ExceptionWrapper
from .models import DefnListDictTree2L, TextTreeDictTree2L

tblib.pickling_support.install()
DetectorFactory.seed = 0


def get_pos(sections: List[Wikicode]) -> Dict[str, TextTreeList]:
    defn_lists = {}
    for def_section in sections:
        def_title_node = get_heading_node(def_section)
        def_title = get_heading_string(def_title_node)
        if def_title in POS:
            def_section.remove(def_section.get(0))
            definitions = get_lead(def_section)
            str_def_title = str(def_title)
            defn_lists[str_def_title] = parse_nested_list(definitions)
        else:
            get_stats_logger().append(
                {"type": "unknown_pos_title", "title": str(def_title)}
            )
    return defn_lists


def get_etymology(sections: List[Wikicode]) -> Dict[str, Dict[str, TextTreeList]]:
    defn_lists = {}
    for def_section in sections:
        def_title_node = get_heading_node(def_section)
        def_title = get_heading_string(def_title_node)
        if def_title.startswith("Etymology "):
            pos_defns = get_pos(def_section.get_sections(levels=[4]))
            defn_lists[str(def_title)] = pos_defns
    return defn_lists


def parse_enwiktionary_page(lemma: str, content: str) -> Optional[DefnListDictTree2L]:
    set_curword(lemma)
    parsed = parse(content, skip_style_tags=True)
    # XXX: Need to deal with multiple parts of speech
    empty_dict: Dict[str, TextTreeList] = {}
    defn_lists: TextTreeDictTree2L = empty_dict
    for lang_section in parsed.get_sections(levels=[2]):
        lang_title = get_heading(lang_section)
        if lang_title != "Finnish":
            continue
        defn_lists = get_etymology(lang_section.get_sections(levels=[3]))
        if not defn_lists:
            defn_lists = get_pos(lang_section.get_sections(levels=[3]))
    if defn_lists:
        return map_tree_to_senses(defn_lists)
    return None


def defns_is_empty(nested_senses: Any) -> bool:  # TODO: specify better type
    if nested_senses is None:
        return True
    if isinstance(nested_senses, list):
        return len(nested_senses) == 0
    return all((defns_is_empty(child) for child in nested_senses.values()))


_lemma_ranks = None


def get_rank(lemma: str):
    global _lemma_ranks
    if _lemma_ranks is None:
        try:
            _lemma_ranks = list(line[:-1] for line in open("data/words"))
        except FileNotFoundError:
            return "no rank data in data/words"
    try:
        return _lemma_ranks.index(lemma) + 1
    except:
        return "no rank"


class TextOnlyRevisionMonkeyPatch:
    """
    This is a monkeypatch for mwxml to speed things up by just fetching the revision text.
    """

    def __init__(self, text=None):
        self.text = text
        self.page = None

    @classmethod
    def from_element(cls, element) -> TextOnlyRevisionMonkeyPatch:
        for sub_element in element:
            tag = sub_element.tag
            if tag == "text":
                text_deleted = sub_element.attr("deleted") is not None
                if not text_deleted:
                    return cls(sub_element.text)
        return cls()


mwxml_iteration_page.Revision = TextOnlyRevisionMonkeyPatch


def process_dump(inf, outdir, sbf=None):
    if sbf is not None:
        with open(sbf, "rb") as fh:
            sbf = ScalableBloomFilter.fromfile(fh)

    def page_info(
        dump
    ) -> Iterator[Tuple[str, Union[DefnListDictTree2L, ExceptionWrapper]]]:
        get_stats_logger().reopen()
        total = 0
        try:
            for page in dump.pages:
                total += 1
                if (
                    page.namespace != 0
                    or page.title.startswith("User:")
                    or "/" in page.title
                    or (sbf is not None and page.title not in sbf)
                ):
                    continue
                revision = next(page)
                if revision.text is None or "==Finnish==" not in revision.text:
                    continue
                try:
                    defns = parse_enwiktionary_page(page.title, revision.text)
                except Exception as exc:
                    get_stats_logger().append(
                        {"type": "word_event", "word": page.title, "event": "failure"}
                    )
                    # print('EXCEPTION!')
                    # print(page.title, exc)
                    yield (page.title, ExceptionWrapper(exc))
                else:
                    if defns is not None:
                        if defns_is_empty(defns):
                            get_stats_logger().append(
                                {
                                    "type": "word_event",
                                    "word": page.title,
                                    "event": "empty",
                                }
                            )
                        else:
                            get_stats_logger().append(
                                {
                                    "type": "word_event",
                                    "word": page.title,
                                    "event": "success",
                                }
                            )
                            yield page.title, defns
        finally:
            get_stats_logger().append({"type": "total_count", "count": total})

    makedirs(outdir, exist_ok=True)
    successful = 0
    for lemma, defns in page_info(Dump.from_file(inf)):
        try:
            if isinstance(defns, ExceptionWrapper):
                print("Error while processing {}.".format(lemma))
                print("(Rank: {})".format(get_rank(lemma)))
                try:
                    defns.re_raise()
                except Exception:
                    traceback.print_exc(file=sys.stdout)
            else:
                print("Success", lemma)
                with open(pjoin(outdir, lemma), "w") as fp:
                    ujson.dump(defns, fp)
            sys.stdout.flush()
            sys.stderr.flush()
            successful += 1
            if successful % 1000 == 0:
                sys.stdout.write(".")
                sys.stdout.flush()
        except:
            print("Exception while processing", lemma, defns)
            raise
    print("Got {}".format(successful))


def get_finnish_words(filename, words):
    def detect_finnish(dump, path):
        for page in dump.pages:
            revision = next(page)
            if revision.text is not None and "==Finnish==" not in revision.text:
                # Short cut parsing
                continue
            parsed = parse(revision.text, skip_style_tags=True)
            for lang_section in parsed.get_sections(levels=[2]):
                lang_title = get_heading(lang_section)
                if lang_title == "Finnish":
                    yield page.title
                    break

    finnish_words = 0
    sbf = ScalableBloomFilter(mode=ScalableBloomFilter.SMALL_SET_GROWTH)
    for lemma in mwxml.map(detect_finnish, [filename]):
        sbf.add(lemma)
        finnish_words += 1
    print("Finnish words: {}", finnish_words)

    return sbf
