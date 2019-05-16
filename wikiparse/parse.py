from __future__ import annotations

# from parsepred.monkeypatch_multiprocessing import do_monkeypatch
# do_monkeypatch()
import logging
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
from typing import Any, Dict, List, Union, Tuple, Iterator
import mwxml
from mwxml.iteration import Dump, page as mwxml_iteration_page

from wikiparse.utils.wikicode import get_heading, get_lead, parse_nested_list
from wikiparse.stats_log import get_stats_logger, set_curword

from .gram_words import POS
from .parse_defn import get_senses
from .parse_ety import get_ety
from .exceptions import (
    ExceptionWrapper,
    UnknownStructureException,
    get_strictness,
    PERMISSIVE,
)
from .utils.iter import orelse

tblib.pickling_support.install()
DetectorFactory.seed = 0


def handle_pos_sections(
    sections: List[Wikicode]
) -> Iterator[Tuple[str, Tuple[str, ...], Any]]:
    """
    Takes a list of sections and yield tagged, pathed, parsed fragments are
    titled as second level titles, e.g. "Etymology" "Verb".
    """
    for def_section in sections:
        str_def_title = str(get_heading(def_section)).strip()
        try:
            if str_def_title == "Etymology":
                def_section.remove(def_section.get(0))
                etymology = get_lead(def_section)
                for act, payload in get_ety(etymology):
                    yield act, (str_def_title,), payload
            elif str_def_title in POS:
                def_section.remove(def_section.get(0))
                definitions = get_lead(def_section)
                for act, payload in get_senses(parse_nested_list(definitions)):
                    yield act, (str_def_title,), payload
            else:
                get_stats_logger().append(
                    {"type": "unknown_pos_title", "title": str_def_title}
                )
        except UnknownStructureException as exc:
            yield "exception", (str_def_title,), exc


def handle_etymology_sections(
    sections: List[Wikicode]
) -> Iterator[Tuple[str, Tuple[str, ...], Any]]:
    """
    Takes a list of sections and yield tagged, pathed, parsed fragments are
    titled as first level titles, e.g. "Etymology 2".
    """
    for def_section in sections:
        str_def_title = str(get_heading(def_section))
        if str_def_title.startswith("Etymology "):
            for act, path, payload in handle_pos_sections(
                def_section.get_sections(levels=[4])
            ):
                yield act, (str_def_title,) + path, payload


def parse_enwiktionary_page(lemma: str, content: str) -> Tuple[Dict, List[Any]]:
    set_curword(lemma)
    parsed = parse(content, skip_style_tags=True)
    defn_lists: Dict = {}
    heads = []
    for lang_section in parsed.get_sections(levels=[2]):
        lang_title = get_heading(lang_section)
        if lang_title != "Finnish":
            continue
        for act, path, payload in orelse(
            handle_etymology_sections(lang_section.get_sections(levels=[3])),
            handle_pos_sections(lang_section.get_sections(levels=[3])),
        ):
            if act == "defn":
                if len(path) == 1:
                    defn_lists[path[0]] = payload
                elif len(path) == 2:
                    defn_lists.setdefault(path[0], {})[path[1]] = payload
                else:
                    raise
            elif act == "head":
                heads.append(payload.tagged_dict())
            elif act == "exception":
                if get_strictness() == PERMISSIVE:
                    logging.exception("Ignored since in permissive mode: %s", payload)
                else:
                    raise payload
                if hasattr(payload, "log"):
                    loggable = payload.log
                    loggable["word"] = lemma
                    loggable["path"] = path
                    get_stats_logger().append(loggable)
            else:
                raise
    return defn_lists, heads


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

    # Dict with DefnListDictTree2L, List[Any]
    def page_info(
        dump
    ) -> Iterator[Tuple[str, Union[ExceptionWrapper, Dict[str, Any]]]]:
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
                results = {}  # type: Dict[str, Any]

                try:
                    defns, heads = parse_enwiktionary_page(page.title, revision.text)
                except Exception as exc:
                    get_stats_logger().append(
                        {"type": "word_event", "word": page.title, "event": "failure"}
                    )
                    yield (page.title, ExceptionWrapper(exc))
                    continue
                if defns is not None:
                    if defns_is_empty(defns):
                        get_stats_logger().append(
                            {
                                "type": "word_event",
                                "word": page.title,
                                "event": "defns_empty",
                            }
                        )
                    else:
                        get_stats_logger().append(
                            {
                                "type": "word_event",
                                "word": page.title,
                                "event": "got_defns",
                            }
                        )
                        results["defns"] = defns
                if heads:
                    results["heads"] = heads
                if results:
                    yield page.title, results
        finally:
            get_stats_logger().append({"type": "total_count", "count": total})

    makedirs(outdir, exist_ok=True)
    successful = 0
    for lemma, results in page_info(Dump.from_file(inf)):
        try:
            if isinstance(results, ExceptionWrapper):
                print("Error while processing {}.".format(lemma))
                print("(Rank: {})".format(get_rank(lemma)))
                try:
                    results.re_raise()
                except Exception:
                    traceback.print_exc(file=sys.stdout)
            else:
                print("Success", lemma)
                with open(pjoin(outdir, lemma), "w") as fp:
                    ujson.dump(results, fp)
            sys.stdout.flush()
            sys.stderr.flush()
            successful += 1
            if successful % 1000 == 0:
                sys.stdout.write(".")
                sys.stdout.flush()
        except:
            print("Exception while processing", lemma, results)
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
