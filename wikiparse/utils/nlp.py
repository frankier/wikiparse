from langdetect import detect_langs
from langdetect.lang_detect_exception import LangDetectException
from typing import Optional
import re


OUR_LANGS = ("en", "fi")
BRACKET_RE = re.compile(r"\([^\)]*\)")
EQUALS_RE = re.compile(r"=\s*")


def detect_fi_en(content: str) -> Optional[str]:
    try:
        langs = detect_langs(content)
    except LangDetectException:
        return None
    for lang in langs:
        if lang.lang in OUR_LANGS:
            return lang.lang
    return None
