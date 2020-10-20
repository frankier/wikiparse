from sqlalchemy import (
    Column,
    Enum,
    Integer,
    String,
    ForeignKey,
    JSON,
    MetaData,
    Table,
    Boolean,
)
from ..enums import DerivationType, RelationType

metadata = MetaData()


headword = Table(
    "headword",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String, unique=True),
    Column("redlink", Boolean, default=False),
)

inflection_of = Table(
    "inflection_of",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("lemma_id", Integer, ForeignKey("headword.id"), nullable=False),
    Column("inflection", JSON, nullable=False),
)

etymology = Table(
    "etymology",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("etymology_index", Integer, nullable=True),
    Column(
        "headword_id", Integer, ForeignKey("headword.id"), nullable=False, index=True
    ),
    Column("poses", JSON, nullable=False),
)

derivation = Table(
    "derivation",
    metadata,
    Column("id", Integer, primary_key=True),
    Column(
        "etymology_id", Integer, ForeignKey("etymology.id"), nullable=False, index=True
    ),
    Column("type", Enum(DerivationType), nullable=False),
    Column("extra", JSON, nullable=False),
)

derivation_seg = Table(
    "derivation_seg",
    metadata,
    Column("id", Integer, primary_key=True),
    Column(
        "derivation_id",
        Integer,
        ForeignKey("derivation.id"),
        nullable=False,
        index=True,
    ),
    Column("derived_seg_id", Integer, ForeignKey("headword.id"), nullable=False),
    Column("alt", String),
)

relation = Table(
    "relation",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("parent_id", Integer, ForeignKey("headword.id"), nullable=False),
    Column("child_id", Integer, ForeignKey("headword.id"), nullable=False),
    Column("type", Enum(RelationType), nullable=False),
    Column("extra", JSON, nullable=False),
)

derived_term = Table(
    "derived_term",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("headword_id", Integer, ForeignKey("headword.id"), nullable=False),
    Column("derived_id", Integer, ForeignKey("headword.id"), nullable=True),
    Column("disp", String, nullable=False),
    Column("gloss", String, nullable=False),
    Column("extra", JSON, nullable=False),
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

meta = Table(
    "meta",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("key", String, unique=True, nullable=False),
    Column("value", String, nullable=False),
)
