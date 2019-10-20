from sqlalchemy.sql import func
from sqlalchemy.sql import select, literal
from .tables import (
    headword, word_sense, inflection_of, etymology,
    derivation_seg, relation
)

WORD_SENSE_COLS = [
    word_sense.c.sense_id,
    word_sense.c.pos,
    word_sense.c.etymology_index,
    word_sense.c.sense,
    word_sense.c.extra,
]

RELATED = [
    ("Inflections", inflection_of, "lemma_id"),
    ("Etymologies", etymology, "headword_id"),
    ("Segment in derivations", derivation_seg, "derived_seg_id"),
    ("Parent of relation", relation, "parent_id"),
    ("Child of relation", relation, "child_id"),
    ("Word senses", word_sense, "headword_id"),
]


def lemma_info_query_id(name, sense_id):
    return \
        select([literal(name).label("headword")] + WORD_SENSE_COLS)\
        .select_from(
            word_sense,
        ).where(
            word_sense.c.id == sense_id
        )


def lemma_info_query(lemmas):
    return \
        select([
            headword.c.name,
        ] + WORD_SENSE_COLS).select_from(
            headword.join(
                word_sense,
                word_sense.c.headword_id == headword.c.id
            )
        ).where(
            headword.c.name.in_(lemmas)
        ).order_by(
            headword.c.name, word_sense.c.pos, word_sense.c.etymology_index
        )


def headword_rels_counts_query(lemmas):
    aliases = []
    for name, table, col in RELATED:
        table_alias = table.alias()
        col_alias = getattr(table_alias.c, col)
        aliases.append((table_alias, col_alias))
    select_cols = [
        headword.c.name,
    ]
    for table_alias, col_alias in aliases:
        select_cols.append(func.count(col_alias))
    from_clause = headword
    for (name, table, col), (table_alias, col_alias) in zip(RELATED, aliases):
        from_clause = from_clause.outerjoin(table_alias, col_alias == headword.c.id)
    query = select(select_cols).select_from(from_clause).where(headword.c.name.in_(lemmas))
    return query
