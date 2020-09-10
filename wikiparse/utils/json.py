import orjson
from typing import Iterable
from mwparserfromhell.wikicode import Wikicode
from wikiparse.exceptions import (
    UnknownStructureException,
    ParseException,
    InterpretException,
)


def json_load(file_like):
    return orjson.loads(file_like.read())


def default(obj):
    if isinstance(obj, (
        UnknownStructureException,
        ParseException,
        InterpretException,
        Wikicode
    )):
        return str(obj)
    elif isinstance(obj, Iterable):
        return list(obj)
    raise TypeError


def dumps(obj):
    return orjson.dumps(obj, default=default)
