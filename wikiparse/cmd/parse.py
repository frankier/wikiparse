import click
import click_log
import logging
from pprint import pprint
from typing import Any, Dict, List, Optional, Tuple

from wikiparse.parse import process_dump, parse_enwiktionary_page, get_finnish_words
from wikiparse.insert import (
    insert_defns,
    insert_derivation,
    insert_morph,
    insert_relation,
)
from wikiparse.stats_log import install_db_stats_logger
from wikiparse.utils.db import batch_commit, get_session
from wikiparse.utils import json_load
from wikiparse.utils.std import IterDirOrTar


@click.group()
@click_log.simple_verbosity_option()
def parse():
    pass


@parse.command()
@click.argument("inf", type=click.File())
@click.argument("words", required=False)
@click.option("--stats-db")
@click.option("--outdir")
def parse_dump(inf, words=None, stats_db=None, outdir=None):
    if stats_db is not None:
        install_db_stats_logger(stats_db)
    logging.basicConfig(filename="example.log", level=logging.DEBUG)
    # logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
    process_dump(inf, outdir, words)


@parse.command()
@click.argument("filename", type=click.File())
def parse_file(filename):
    defns = parse_enwiktionary_page(filename, open(filename).read())
    if defns is None:
        print("No definitions found")
    pprint(defns)


def insert_dir_inner(db, indir: str):
    headword_id_map = {}
    all_morphs = []  # type: List[Tuple[int, Optional[Dict]]]
    all_heads = []  # type: List[Tuple[str, Dict[str, Any]]]

    with click.progressbar(IterDirOrTar(indir), label="Inserting defns") as words:

        def defns_batch(word_pair):
            lemma_name, wordf = word_pair
            results = json_load(wordf)
            if "defns" in results:
                defns = results["defns"]
                headword_id, morphs = insert_defns(db, lemma_name, defns)
                headword_id_map[lemma_name] = headword_id
                all_morphs.extend(morphs)
            if "heads" in results:
                all_heads.extend(((lemma_name, head) for head in results["heads"]))

        batch_commit(db, words, defns_batch)

    with click.progressbar(all_morphs, label="Inserting inflections") as morphs:

        def morph_batch(id_morph):
            (word_sense_id, morph) = id_morph
            insert_morph(db, word_sense_id, morph, headword_id_map)

        batch_commit(db, morphs, morph_batch)

    with click.progressbar(all_heads, label="Inserting heads") as heads:

        def head_batch(lemma_head):
            lemma, head = lemma_head
            tag = head.pop("tag")
            if tag == "etymology":
                insert_derivation(db, lemma, head, headword_id_map)
            elif tag == "relation":
                insert_relation(db, lemma, head, headword_id_map)
            else:
                assert False

        batch_commit(db, heads, head_batch)


@parse.command()
@click.argument("indir")
def insert_dir(indir: str):
    insert_dir_inner(get_session(), indir)


@parse.command()
@click.argument("filename")
@click.argument("words")
def save_finnish_words(filename, words):
    sbf = get_finnish_words(filename, words)

    with open(words, "wb") as fh:
        sbf.tofile(fh)
