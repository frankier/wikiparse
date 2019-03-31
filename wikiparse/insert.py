from wikiparse.utils.db import insert_get_id, insert
from typing import cast, Dict, List, TypeVar, Tuple, Iterator
from .models import DictTree2L


T = TypeVar("T")


def flatten_senses(nested_senses: DictTree2L[List[T]]) -> Iterator[Tuple[str, str, T]]:
    if isinstance(next(iter(nested_senses.values())), list):
        nested_senses = cast(Dict[str, List[T]], nested_senses)
        for pos, senses in nested_senses.items():
            for sense_idx, sense in enumerate(senses):  # type: Tuple[int, T]
                yield "{}.{}".format(pos, sense_idx + 1), pos, sense
    else:
        nested_senses = cast(Dict[str, Dict[str, List[T]]], nested_senses)
        for etymology, outer_senses in nested_senses.items():
            for pos, senses in outer_senses.items():
                for sense_idx, sense in enumerate(senses):
                    yield (
                        "{}.{}.{}".format(
                            etymology.replace(" ", ""), pos, sense_idx + 1
                        ),
                        pos,
                        sense,
                    )


def insert_defns(session, lemma_name: str, defns: DictTree2L[List[Dict]]):
    from wikiparse import tables

    try:
        headword_id = insert_get_id(session, tables.headword, name=lemma_name)
        for full_id, pos, sense in flatten_senses(defns):  # type: Tuple[str, str, Dict]
            headword_pos_id = insert_get_id(
                session, tables.headword_pos, headword_id=headword_id, pos=pos
            )
            stripped_defn = sense["stripped_defn"]
            sense.pop("bi_examples", {})
            sense.pop("fi_examples", {})
            wiktionary_word_sense_id = insert_get_id(
                session,
                tables.wiktionary_word_sense,
                sense=stripped_defn,
                sense_id=full_id,
                extra=sense,
            )
            insert(
                session,
                tables.word_sense,
                headword_pos_id=headword_pos_id,
                wiktionary_word_sense_id=wiktionary_word_sense_id,
            )

            head_gram = sense.pop("head_gram", [])
            for head_gram in head_gram:
                if head_gram.get("type") != "form":
                    continue
                head_gram.pop("type")
                lemma = head_gram.pop("lemma")
                lemma_id, created = insert_get_id(session, tables.headword, name=lemma)
                insert(
                    session,
                    tables.inflection_of,
                    lemma_id=lemma_id,
                    form_id=headword_pos_id,
                    inflection=head_gram,
                )
    except:
        session.rollback()
        raise
    else:
        session.commit()
