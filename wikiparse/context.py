from dataclasses import dataclass
from typing import Optional


@dataclass
class ParseContext:
    headword: str
    pos_heading: Optional[str] = None
