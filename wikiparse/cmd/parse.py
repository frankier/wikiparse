import click
import click_log
import logging
import os
from os.path import join as pjoin, isdir, basename
import ujson
from pprint import pprint
from tarfile import TarFile

from wikiparse.parse import process_dump, parse_enwiktionary_page, get_finnish_words
from wikiparse.insert import insert_defns, insert_morph
from wikiparse.stats_log import install_db_stats_logger
from wikiparse.utils.db import batch_commit, get_session


class IterDirOrTar(object):
    def __init__(self, indir):
        self.indir = indir

    def __len__(self):
        if isdir(self.indir):
            return len(os.listdir(self.indir))
        else:
            tf = TarFile(self.indir)
            return sum((1 for m in tf.getmembers() if m.isfile()))

    def __iter__(self):
        if isdir(self.indir):
            for word in os.listdir(self.indir):
                with open(pjoin(self.indir, word)) as defn_fp:
                    yield word, ujson.load(defn_fp)
        else:
            tf = TarFile(self.indir)
            for member in tf.getmembers():
                if member.isfile():
                    yield basename(member.name), ujson.loads(
                        tf.extractfile(member).read()
                    )


@click.group()
@click_log.simple_verbosity_option()
def parse():
    pass


@parse.command()
@click.argument("filename")
@click.argument("words", required=False)
@click.option("--stats-db")
@click.option("--outdir")
def parse_dump(filename: str, words=None, stats_db=None, outdir=None):
    if stats_db is not None:
        install_db_stats_logger(stats_db)
    logging.basicConfig(filename="example.log", level=logging.DEBUG)
    # logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
    if filename.endswith(".xml"):
        process_dump(filename, outdir, words)
    else:
        defns = parse_enwiktionary_page(filename, open(filename).read())
        if defns is None:
            print("No definitions found")
        pprint(defns)


def insert_dir_inner(db, indir: str):
    headword_id_map = {}
    all_morphs = []
    with click.progressbar(IterDirOrTar(indir), label="Inserting defns") as words:
        def defns_batch(elem):
            word, defns = elem
            (headword_id, lemma_name), morphs = insert_defns(db, word, defns)
            headword_id_map[lemma_name] = headword_id
            all_morphs.extend(morphs)
        batch_commit(db, words, defns_batch)
    with click.progressbar(all_morphs, label="Inserting inflections") as morphs:
        def morph_batch(id_morph):
            (word_sense_id, morph) = id_morph
            insert_morph(db, word_sense_id, morph, headword_id_map)
        batch_commit(db, morphs, morph_batch)


@parse.command()
@click.argument("indir")
@click.argument("db")
def insert_dir(indir: str, db: str):
    insert_dir_inner(get_session(db), indir)


@parse.command()
@click.argument("filename")
@click.argument("words")
def save_finnish_words(filename, words):
    sbf = get_finnish_words(filename, words)

    with open(words, "wb") as fh:
        sbf.tofile(fh)
