from sqlalchemy import Column, Integer, String, ForeignKey, JSON, MetaData, Table

metadata = MetaData()


headword = Table(
    "headword",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String, unique=True),
)

inflection_of = Table(
    "inflection_of",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("lemma_id", Integer, ForeignKey("headword.id"), nullable=False),
    Column("form_id", Integer, ForeignKey("headword_pos.id"), nullable=False),
    Column("inflection", JSON, nullable=False),
)

derived_from = Table(
    "derived_from",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("parent_id", Integer, ForeignKey("headword.id"), nullable=False),
    Column("child_id", Integer, ForeignKey("headword.id"), nullable=False),
)

headword_pos = Table(
    "headword_pos",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("headword_id", Integer, ForeignKey("headword.id"), nullable=False),
    Column("pos", String, nullable=False),
)

word_sense = Table(
    "word_sense",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("headword_pos_id", Integer, ForeignKey("headword_pos.id"), nullable=False),
    Column(
        "wiktionary_word_sense_id",
        Integer,
        ForeignKey("wiktionary_word_sense.id"),
        nullable=False,
    ),
)

wiktionary_word_sense = Table(
    "wiktionary_word_sense",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("sense", String, nullable=False),
    Column("sense_id", String, nullable=False),
    Column("extra", JSON, nullable=False),
)

usage_example = Table(
    "usage_example",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("example", String, nullable=False),
    Column("gloss", String, nullable=False),
)
