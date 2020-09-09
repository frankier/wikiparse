import click
import click_log
import logging
import orjson
from pprint import pprint
from typing import Any, Dict, List, Optional, Tuple, TextIO

from wikiparse.parse import process_dump, process_pages, parse_enwiktionary_page
from wikiparse.db.insert import (
    insert_defns,
    insert_ety_head,
    insert_morph,
    insert_relation,
    insert_deriv,
)
from wikiparse.utils.cmd import Mutex
from wikiparse.utils.db import batch_commit, get_session
from wikiparse.utils.std import IterDirOrTar


@click.group()
@click_log.simple_verbosity_option()
def parse():
    pass


def set_stats_db(_ctx, _param, stats_db):
    from wikiparse.utils.stats_log import install_db_stats_logger

    if stats_db is not None:
        install_db_stats_logger(stats_db)


stats_db_opt = click.option(
    "--stats-db", envvar="STATS_DB", expose_value=False, callback=set_stats_db,
)


def set_mod_data_dir(_ctx, _param, mod_data):
    from wikiparse.utils.mod_data import set_jsons_path

    if mod_data is not None:
        set_jsons_path(mod_data)


mod_data_opt = click.option(
    "--mod-data",
    envvar="MOD_DATA",
    expose_value=False,
    callback=set_mod_data_dir,
    cls=Mutex,
    required=True,
    not_required_if=("fsts_dir",),
)


def set_fsts_dir(_ctx, _param, fsts_dir):
    from wikiparse.utils.fst import LazyFst

    if fsts_dir is not None:
        LazyFst.set_fst_dir(fsts_dir)


fsts_dir_opt = click.option(
    "--fsts-dir",
    envvar="FSTS_DIR",
    expose_value=False,
    callback=set_fsts_dir,
    cls=Mutex,
    required=True,
    not_required_if=("mod_data",),
)


@parse.command()
@click.argument("inf", type=click.File())
@stats_db_opt
@mod_data_opt
@fsts_dir_opt
@click.option("--outdir")
def parse_dump(inf, stats_db=None, outdir=None):
    logging.basicConfig(filename="example.log", level=logging.DEBUG)
    # logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
    process_dump(inf, outdir)


@parse.command()
@click.argument("indir", type=click.Path())
@stats_db_opt
@mod_data_opt
@fsts_dir_opt
@click.option("--outdir")
@click.option("--processes", type=int)
def parse_pages(indir, stats_db=None, outdir=None, processes=None):
    process_pages(indir, outdir, processes)


@parse.command()
@click.argument("filename", type=click.File())
def parse_file(filename):
    defns = parse_enwiktionary_page(filename, filename.read())
    if defns is None:
        print("No definitions found")
    pprint(defns)


def insert_dir_inner(db, indir: str, members: Optional[List[str]] = None):
    headword_id_map = {}
    all_morphs = []  # type: List[Tuple[int, Optional[Dict]]]
    all_heads = []  # type: List[Tuple[str, Dict[str, Any]]]

    with click.progressbar(
        IterDirOrTar(indir, members), label="Inserting defns"
    ) as words:

        def defns_batch(word_pair):
            lemma_name, wordf = word_pair
            # e.g. .snakemake_timestamp
            if lemma_name.startswith("."):
                return
            results = orjson.loads(wordf.read())
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

    all_derivs = []

    with click.progressbar(all_heads, label="Inserting heads") as heads:

        def head_batch(lemma_head):
            lemma, head = lemma_head
            tag = head.pop("tag")
            if tag == "etymology-heading":
                insert_ety_head(db, lemma, head, headword_id_map)
            elif tag == "relation":
                insert_relation(db, lemma, head, headword_id_map)
            elif tag == "deriv":
                # Defer deriv since any headwords not found during insertion are treated as redlinks
                all_derivs.append(lemma_head)
            else:
                assert False

        batch_commit(db, heads, head_batch)

    with click.progressbar(all_derivs, label="Inserting derivs") as derivs:

        def deriv_batch(lemma_head):
            lemma, head = lemma_head
            insert_deriv(db, lemma, head, headword_id_map)

        batch_commit(db, derivs, deriv_batch)


@parse.command()
@click.argument("indir", type=click.Path())
@click.argument("filterfile", type=click.File(mode="r"), required=False)
def insert_dir(indir: str, filterfile: Optional[TextIO]):
    members = None
    if filterfile is not None:
        members = []
        for line in filterfile:
            word = line.strip()
            if not word:
                continue
            members.append(word)
    insert_dir_inner(get_session(), indir, members)
