LANG_TEMPLATES = {
    # defn/ex
    "ux",
    "uxi",
    "lb",
    # ety derivs
    "prefix",
    "suffix",
    "affix",
    "compound",
    # ety/defn: derivs
    "plural of",
    "comparative of",
    "superlative of",
    "agent noun of",
    # defn rels
    "synonym of",
    "syn of",
    "synonyms",
    "syn",
    "antonyms",
    "ant",
    "hypernyms",
    "hyper",
    "alternative form of",
    "alt form",
    "misspelling of",
    "abbreviation of",
    "short for",
    "contraction of",
}

FORM_TEMPLATES = {
    ("fi-verb form of",),
    ("plural of", "fi"),
    ("fi-participle of",),
    ("fi-infinitive of",),
    ("fi-form of",),
}

DERIV_TEMPLATES = {
    ("comparative of", "fi"),
    ("superlative of", "fi"),
    ("agent noun of", "fi"),
}

NON_GLOSS_TEMPLATES = {
    ("non-gloss definition",),
    ("n-g",),
}

ETY_ONLY_DERIV_TEMPLATES = {
    ("prefix", "fi"),
    ("suffix", "fi"),
    ("affix", "fi"),
    ("compound", "fi"),
}

REL_TEMPLATES = {
    ("synonym of", "fi"),
    ("syn of", "fi"),
    ("synonyms", "fi"),
    ("syn", "fi"),
    ("antonyms", "fi"),
    ("ant", "fi"),
    ("hypernyms", "fi"),
    ("hyper", "fi"),
    ("alternative form of", "fi"),
    ("alt form" "fi"),
    ("misspelling of", "fi"),
    ("abbreviation of", "fi"),
    ("short for", "fi"),
    ("contraction of", "fi"),
}

ALL_DERIV_TEMPLATES = DERIV_TEMPLATES | ETY_ONLY_DERIV_TEMPLATES

DEFN_TEMPLATES = (
    FORM_TEMPLATES
    | REL_TEMPLATES
    | DERIV_TEMPLATES
    | NON_GLOSS_TEMPLATES
    | {("lb", "fi")}
)

UX_TEMPLATES = {("ux", "fi"), ("uxi", "fi")}

# TODO: Cross language bor/der/cog
