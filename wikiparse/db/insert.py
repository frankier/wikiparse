from . import tables
from wikiparse.utils.db import insert_get_id, insert
from typing import cast, Dict, List, Optional, TypeVar, Tuple, Iterator
from ..models import DictTree2L, DerivationType, RelationType
from ..parse import get_ety_idx


T = TypeVar("T")


def flatten_subsenses(senses, prefix: str):
    for sense_idx, sense in enumerate(senses):
        new_prefix = prefix + str(sense_idx + 1)
        yield new_prefix, sense
        yield from flatten_subsenses(sense.get("subsenses", ()), new_prefix + ".")


def flatten(nested_senses, ety, prefix):
    for pos, senses in nested_senses.items():
        for label, sense in flatten_subsenses(senses, f"{prefix}{pos}."):
            yield label, ety, pos, sense


def flatten_senses(
    nested_senses: DictTree2L[List[T]],
) -> Iterator[Tuple[str, int, str, T]]:
    if isinstance(next(iter(nested_senses.values())), list):
        nested_senses = cast(Dict[str, List[T]], nested_senses)
        yield from flatten(nested_senses, None, "")
    else:
        nested_senses = cast(Dict[str, Dict[str, List[T]]], nested_senses)
        for etymology, outer_senses in nested_senses.items():
            ety = get_ety_idx(etymology)
            yield from flatten(outer_senses, ety, etymology.replace(" ", "") + ".")


def insert_defns(
    session, lemma_name: str, defns: DictTree2L[List[Dict]]
) -> Tuple[int, List[Tuple[int, Optional[Dict]]]]:
    morphs = []  # type: List[Tuple[int, Optional[Dict]]]
    headword_id = insert_get_id(session, tables.headword, name=lemma_name)
    for full_id, ety, pos, sense in flatten_senses(
        defns
    ):  # type: Tuple[str, int, str, Dict]
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

    return headword_id, morphs


def ensure_lemma(session, lemma, headword_id_map):
    if lemma in headword_id_map:
        lemma_id = headword_id_map[lemma]
    else:
        lemma_id = insert_get_id(session, tables.headword, name=lemma)
        headword_id_map[lemma] = lemma_id
    return lemma_id


def insert_morph(session, word_sense_id, morph, headword_id_map):
    morph.pop("type")
    lemma = morph.pop("lemma")
    lemma_id = ensure_lemma(session, lemma, headword_id_map)
    inflection_of_id = insert_get_id(
        session, tables.inflection_of, lemma_id=lemma_id, inflection=morph
    )
    session.execute(
        tables.word_sense.update()
        .where(tables.word_sense.c.id == word_sense_id)
        .values(inflection_of_id=inflection_of_id)
    )


def insert_ety_head(session, lemma: str, ety_head, headword_id_map):
    lemma_id = ensure_lemma(session, lemma, headword_id_map)
    ety_head_id = insert_get_id(
        session,
        tables.etymology,
        etymology_index=ety_head.pop("ety_idx"),
        headword_id=lemma_id,
        poses=ety_head.pop("poses"),
    )
    etys = ety_head.pop("etys")
    for ety in etys:
        derivation_id = insert_get_id(
            session,
            tables.derivation,
            etymology_id=ety_head_id,
            type=DerivationType(ety.pop("type")),
            extra={"raw_frag": ety.pop("raw_frag")},
        )
        for bit in ety.pop("bits"):
            child_lemma_id = ensure_lemma(session, bit["headword"], headword_id_map)
            insert(
                session,
                tables.derivation_seg,
                derivation_id=derivation_id,
                derived_seg_id=child_lemma_id,
                alt=bit["alt"],
            )


def insert_relation(session, lemma: str, rel, headword_id_map):
    lemma_id = ensure_lemma(session, lemma, headword_id_map)
    parent_lemma_id = ensure_lemma(session, rel.pop("parent"), headword_id_map)
    insert(
        session,
        tables.relation,
        parent_id=parent_lemma_id,
        child_id=lemma_id,
        type=RelationType(rel.pop("type")),
        extra={"raw_frag": rel.pop("raw_frag")},
    )


def insert_deriv(session, lemma: str, deriv, headword_id_map):
    lemma_id = ensure_lemma(session, lemma, headword_id_map)
    link = deriv.get("link")
    if link is not None:
        child_lemma_id = ensure_lemma(session, link, headword_id_map)
    else:
        child_lemma_id = None
    insert(
        session,
        tables.derived_term,
        headword_id=lemma_id,
        derived_id=child_lemma_id,
        disp=deriv.get("disp"),
        gloss=deriv.get("gloss"),
        extra=deriv,
    )


def insert_defns_safe(session, lemma_name: str, defns: DictTree2L[List[Dict]]):
    try:
        insert_defns(session, lemma_name, defns)
    except:
        session.rollback()
        raise
    else:
        session.commit()
