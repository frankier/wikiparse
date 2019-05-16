import sys
from typing import Any, Dict, List, Tuple
from contextlib import contextmanager


class ExceptionWrapper(object):
    def __init__(self, ee):
        self.ee = ee
        __, __, self.tb = sys.exc_info()

    def re_raise(self):
        raise self.ee.with_traceback(self.tb)
        # for Python 2 replace the previous line by:
        # raise self.ee, None, self.tb


UNKNOWN_STRUCTURE_MSGS = {
    # Defns
    "expect-only": "Expected only {}. Got {}",
    "eng-assoc": "Putting English word '{}' in assoc not allowed.",
    "non-fin-assoc": "Putting non-Finnish word '{}' in assoc not allowed.",
    "lb-fi-unknown": "Can't deal with lb|fi|... {}th template param '{}'",
    "too-many-=s": "Can't deal with too many ='s",
    "no-grammar-=": "Can't deal with = without grammar stuff before it",
    "need-+-before-=": "Need + before =",
    "two-tmpl-in-defn": "Did not expect two templates in definition line",
    "not-ux-lb": "Only know how to deal with word form templates OR example templates, not {}",
    "not-fi": "Only know how to deal with ??|fi templates",
    "too-many-subsenses": "Too many subsenses: {}",
    "eng-example-only": "Can't have only English example for Finnish word!",
    "sense-under-example": "Senses can't live under examples",
    "leftover-example-tmpl": "Text left after extracting example template: '{}'",
    "unknown-under-unknown": "Unknown can't be belown unknown",
    "max-one-example-below": "Expected only one example below this one",
    "multiple-form-tmpls": "Excepted only one word form template, got: '{}'",
    # Etys
    "mwe-ety": "Multiword expression etymology section not supported yet",
    "multi-template-ety": "Multiple derrivation templates found in etymology",
    "unknown-template": "Unknown template found in etymology: '{}'",
}


class UnknownStructureException(Exception):
    def add_info(self, info):
        self.args += (info,)


def mk_unknown_structure(nick, *extra):
    exc = UnknownStructureException(
        UNKNOWN_STRUCTURE_MSGS[nick].format(*(repr(e) for e in extra))
    )
    exc.log = {
        "type": "word_event",
        "event": "unknown_structure",
        "nick": nick,
        "extra": extra,
    }
    return exc


def unknown_structure(nick, *extra):
    raise mk_unknown_structure(nick, *extra)


def expect_only(d: Dict[str, List[Any]], ks: Tuple[str, ...]):
    for k in d:
        if k not in ks:
            if len(d[k]):
                unknown_structure("expect-only", ks, d)


PERMISSIVE = 0
STRICT = 1
EXTRA_STRICT = 2
_strictness = PERMISSIVE


def get_strictness():
    return _strictness


def set_strictness(strictness):
    global _strictness
    _strictness = strictness


@contextmanager
def strictness(val):
    global _strictness
    oldval = _strictness
    _strictness = val
    yield
    _strictness = oldval
