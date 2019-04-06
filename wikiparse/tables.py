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
    Column("inflection", JSON, nullable=False),
)

derived_from = Table(
    "derived_from",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("parent_id", Integer, ForeignKey("headword.id"), nullable=False),
    Column("child_id", Integer, ForeignKey("headword.id"), nullable=False),
)

word_sense = Table(
    "word_sense",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("inflection_of_id", Integer, ForeignKey("inflection_of.id"), nullable=True),
    Column("headword_id", Integer, ForeignKey("headword.id"), nullable=False),
    Column("etymology_index", Integer, nullable=True),
    Column("pos", String, nullable=False),
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
