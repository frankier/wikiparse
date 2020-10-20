from __future__ import annotations

# from parsepred.monkeypatch_multiprocessing import do_monkeypatch
# do_monkeypatch()
import logging
import os
import sys
import tblib.pickling_support
from mwparserfromhell import parse
from mwparserfromhell.wikicode import Wikicode
from langdetect import DetectorFactory
import traceback
from os import makedirs
from os.path import join as pjoin
from typing import Any, Dict, List, Union, Tuple, Iterator, Optional
from mwxml.iteration import Dump, page as mwxml_iteration_page
from multiprocessing import Pool
from shutil import copyfile

from wikiparse.utils.wikicode import get_heading, get_lead, parse_nested_list
from wikiparse.utils.stats_log import get_stats_logger
from wikiparse.utils.json import dumps

from .context import ParseContext
from .data.gram_words import POS
from .parse_deriv import get_deriv
from .parse_defn import get_senses
from .parse_ety import get_ety
from .models import EtymologyHeading
from .exceptions import (
    ExceptionWrapper,
    UnknownStructureException,
    get_exception_filter,
)
from .utils.iter import orelse

tblib.pickling_support.install()
DetectorFactory.seed = 0


def get_ety_idx(etymology):
    return int(etymology.split(" ")[-1])


def handle_pos_specific_sections(
    ctx: ParseContext, sections: List[Wikicode]
) -> Iterator[Tuple[str, Any]]:
    for pos_spec_section in sections:
        str_def_title = str(get_heading(pos_spec_section)).strip()
        if str_def_title == "Derived terms":
            yield from get_deriv(ctx, pos_spec_section)


def handle_pos_sections(
    ctx: ParseContext, sections: List[Wikicode], skip_ety: bool = False
) -> Iterator[Tuple[str, Tuple[str, ...], Any]]:
    """
    Takes a list of sections and yield tagged, pathed, parsed fragments are
    titled as second level titles, e.g. "Etymology" "Verb".
    """
    for def_section in sections:
        str_def_title = str(get_heading(def_section)).strip()
        try:
            if str_def_title == "Etymology" and not skip_ety:
                def_section.remove(def_section.get(0))
                etymology = get_lead(def_section)
                for act, payload in get_ety(etymology):
                    yield act, (str_def_title,), payload
            elif str_def_title in POS:
                yield "pos", (str_def_title,), str_def_title
                ctx.pos_heading = str(str_def_title)
                def_section.remove(def_section.get(0))
                definitions = get_lead(def_section)
                for act, payload in get_senses(ctx, parse_nested_list(definitions)):
                    yield act, (str_def_title,), payload
                for act, payload in handle_pos_specific_sections(
                    ctx, def_section.get_sections()
                ):
                    yield act, (str_def_title,), payload
            else:
                get_stats_logger().append(
                    {"type": "unknown_pos_title", "title": str_def_title}
                )
        except UnknownStructureException as exc:
            yield "exception", (str_def_title,), exc


class EtymologyGatherer:
    def __init__(self):
        self.etys = []
        self.poses = []

    def filter(self, stream):
        for act, path, payload in stream:
            if act == "ety-head":
                self.etys.append(payload)
                continue
            if act == "pos":
                self.poses.append(payload)
                continue
            yield act, path, payload

    def etymology_heading(self, ety_idx):
        return EtymologyHeading(ety_idx, self.etys, self.poses)


def handle_etymology_sections(
    ctx: ParseContext, sections: List[Wikicode], skip_ety: bool = False
) -> Iterator[Tuple[str, Tuple[str, ...], Any]]:
    """
    Takes a list of sections and yield tagged, pathed, parsed fragments are
    titled as first level titles, e.g. "Etymology 2".
    """
    for def_section in sections:
        str_def_title = str(get_heading(def_section))
        if str_def_title.startswith("Etymology "):
            etys = EtymologyGatherer()
            for act, path, payload in etys.filter(
                handle_pos_sections(
                    ctx, def_section.get_sections(levels=[4]), skip_ety=skip_ety
                )
            ):
                yield act, (str_def_title,) + path, payload
            yield "ety-sec-head", (str_def_title,), etys.etymology_heading(
                get_ety_idx(str_def_title),
            )


def parse_enwiktionary_page(
    lemma: str, content: str, skip_ety: bool = False
) -> Tuple[Dict, List[Any]]:
    parsed = parse(content, skip_style_tags=True)
    defn_lists: Dict = {}
    heads = []
    got_ety_sec_head = False
    etys = EtymologyGatherer()
    ctx = ParseContext(lemma)
    for lang_section in parsed.get_sections(levels=[2]):
        lang_title = get_heading(lang_section)
        if lang_title != "Finnish":
            continue
        for act, path, payload in etys.filter(
            orelse(
                handle_etymology_sections(
                    ctx, lang_section.get_sections(levels=[3]), skip_ety=skip_ety
                ),
                handle_pos_sections(
                    ctx, lang_section.get_sections(levels=[3]), skip_ety=skip_ety
                ),
            )
        ):
            if act == "defn":
                if len(path) == 1:
                    defn_lists[path[0]] = payload
                elif len(path) == 2:
                    defn_lists.setdefault(path[0], {})[path[1]] = payload
                else:
                    raise
            elif act == "ety-sec-head":
                got_ety_sec_head = True
                heads.append(payload.tagged_dict())
            elif act == "head":
                heads.append(payload.tagged_dict())
            elif act == "deriv":
                # TODO: Doesn't 100% make sense as head since it often appears
                # under a POS section so we are losing information here atm
                heads.append(payload.tagged_dict())
            elif act == "exception":
                exception_filter = get_exception_filter()
                if exception_filter(payload):
                    raise payload
                logging.exception("Ignored due to exception filter : %s", payload)
                if hasattr(payload, "log"):
                    loggable = payload.log
                    loggable["word"] = lemma
                    loggable["path"] = path
                    get_stats_logger().append(loggable)
            else:
                raise
    if not got_ety_sec_head:
        heads.append(etys.etymology_heading(None).tagged_dict())
    return defn_lists, heads


def defns_is_empty(nested_senses: Any) -> bool:  # TODO: specify better type
    if nested_senses is None:
        return True
    if isinstance(nested_senses, list):
        return len(nested_senses) == 0
    return all((defns_is_empty(child) for child in nested_senses.values()))


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


def proc_text(
    title: str, text: str
) -> Optional[Tuple[str, Union[Dict[str, Any], ExceptionWrapper]]]:
    results = {}  # type: Dict[str, Any]

    try:
        defns, heads = parse_enwiktionary_page(title, text)
    except Exception as exc:
        get_stats_logger().append(
            {"type": "word_event", "word": title, "event": "failure"}
        )
        return title, ExceptionWrapper(exc)
    if defns is not None:
        if defns_is_empty(defns):
            get_stats_logger().append(
                {"type": "word_event", "word": title, "event": "defns_empty"}
            )
        else:
            get_stats_logger().append(
                {"type": "word_event", "word": title, "event": "got_defns"}
            )
            results["defns"] = defns
    if heads:
        results["heads"] = heads
    if results:
        return title, results
    return None


def log_total(total):
    get_stats_logger().append({"type": "total_count", "count": total})


def proc_result(outdir, lemma, results):
    try:
        if isinstance(results, ExceptionWrapper):
            print("Error while processing {}.".format(lemma))
            try:
                results.re_raise()
            except Exception:
                traceback.print_exc(file=sys.stdout)
        else:
            print("Success", lemma)
            with open(pjoin(outdir, lemma), "wb") as fp:
                fp.write(dumps(results))
    except:
        print("Exception while processing", lemma, results)
        raise


class ProcessPageFile:
    def __init__(self, outdir, entries, *args, **kwargs):
        self.outdir = outdir
        self.entries = entries
        self.args = args
        self.kwargs = kwargs

    def worker_init(self):
        get_stats_logger().reopen()

    def __getstate__(self):
        return {"outdir": self.outdir}

    def __iter__(self):
        pool = Pool(*self.args, initializer=self.worker_init, **self.kwargs)
        try:
            yield from pool.imap_unordered(self, self.entries)
        finally:
            pool.terminate()

    def __call__(self, entry):
        from urllib.parse import unquote

        name, path = entry
        if name == "__metadata__.json":
            copyfile(path, pjoin(self.outdir, "__metadata__.json"))
            return
        title = unquote(name)
        results = proc_text(title, open(path).read())
        if results is not None:
            proc_result(self.outdir, title, results[1])


def process_pages(indir, outdir, processes=None):
    entries = ((dir_entry.name, dir_entry.path) for dir_entry in os.scandir(indir))
    total = 0
    for _ in ProcessPageFile(outdir, entries, processes=processes):
        total += 1
    log_total(total)


def process_dump(inf, outdir):
    # Dict with DefnListDictTree2L, List[Any]
    def page_info(
        dump,
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
                ):
                    continue
                revision = next(page)
                if revision.text is None or "==Finnish==" not in revision.text:
                    continue
                res = proc_text(page.title, revision.text)
                if res:
                    yield res
        finally:
            log_total(total)

    makedirs(outdir, exist_ok=True)
    for lemma, results in page_info(Dump.from_file(inf)):
        proc_result(outdir, lemma, results)
