from wikiparse import tables
from wikiparse.utils.db import insert_get_id
from typing import cast, Dict, List, TypeVar, Tuple, Iterator
from .models import DictTree2L


T = TypeVar("T")


def flatten(nested_senses, ety, prefix):
    for pos, senses in nested_senses.items():
        for sense_idx, sense in enumerate(senses):  # type: Tuple[int, T]
            yield prefix + "{}.{}".format(pos, sense_idx + 1), ety, pos, sense


def flatten_senses(nested_senses: DictTree2L[List[T]]) -> Iterator[Tuple[str, str, T]]:
    if isinstance(next(iter(nested_senses.values())), list):
        nested_senses = cast(Dict[str, List[T]], nested_senses)
        return flatten(nested_senses, None, "")
    else:
        nested_senses = cast(Dict[str, Dict[str, List[T]]], nested_senses)
        for etymology, outer_senses in nested_senses.items():
            ety = int(etymology.split(" ")[-1])
            yield from flatten(outer_senses, ety, etymology.replace(" ", "") + ".")


def insert_defns(session, lemma_name: str, defns: DictTree2L[List[Dict]]):
    morphs = []
    headword_id = insert_get_id(session, tables.headword, name=lemma_name)
    for full_id, ety, pos, sense in flatten_senses(defns):  # type: Tuple[str, str, Dict]
        stripped_defn = sense["stripped_defn"]
        sense.pop("bi_examples", {})
        sense.pop("fi_examples", {})

        word_sense_id = insert_get_id(
            session,
            tables.word_sense,
            inflection_of_id=None,
            headword_id=headword_id,
            etymology_index=ety,
            pos=pos,
            sense=stripped_defn,
            sense_id=full_id,
            extra=sense,
        )

        morph = sense.get("morph")
        if morph and morph.get("type") == "form":
            morphs.append((word_sense_id, morph))

    return (headword_id, lemma_name), morphs


def insert_morph(session, word_sense_id, morph, headword_id_map):
    morph.pop("type")
    lemma = morph.pop("lemma")
    if lemma in headword_id_map:
        lemma_id = headword_id_map[lemma]
    else:
        lemma_id = insert_get_id(session, tables.headword, name=lemma)
        headword_id_map[lemma] = lemma_id
    inflection_of_id = insert_get_id(
        session,
        tables.inflection_of,
        lemma_id=lemma_id,
        inflection=morph,
    )
    session.execute(
        tables.word_sense
        .update()
        .where(tables.word_sense.c.id == word_sense_id)
        .values(inflection_of_id=inflection_of_id)
    )


def insert_defns_safe(session, lemma_name: str, defns: DictTree2L[List[Dict]]):
    try:
        insert_defns(session, lemma_name, defns)
    except:
        session.rollback()
        raise
    else:
        session.commit()
