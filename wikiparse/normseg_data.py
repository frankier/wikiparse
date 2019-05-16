TEMPLATE_NORMSEG_MAP = {
    "comparative of": "-empi",
    "superlative of": "-in",
    "agent noun of": "-ja",
    "plural of": "-t",
}

CASE_NORMSEG_MAP = {
    "nominative": None,
    "genitive": "-n",
    "partitive": "-ta",
    "inessive": "-ssa",
    "elative": "-sta",
    "illative": "-seen",  # XXX: -an? -Vn?
    "adessive": "-lla",
    "ablative": "-lta",
    "allative": "-lle",
    "essive": "-na",
    "translative": "-ksi",
    "instructive": "-in",
    "abessive": "-tta",
    "comitative": "-ine",
}

PL_CASES = {"instructive", "comitative"}

PL_NORMSEG_MAP = {"singular": None, "plural": "-t"}

NOUN_FORM_OF_FIELDS_MAP = {"case": CASE_NORMSEG_MAP, "pl": PL_NORMSEG_MAP}

# TODO
# VERB_FORM_OF_FIELDS_MAP = {
# "pr": {},
# "pl": {},  # XXX: pr and pl need to be considered together really
# "mood": {},
# "tense": {},
# }
