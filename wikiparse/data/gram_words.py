from nltk.tokenize import MWETokenizer


POS = [
    "Verb",
    "Noun",
    "Proper noun",
    "Number",
    "Letter",
    "Conjunction",
    "Symbol",
    "Abbreviation",
    "Phrase",
    "Postposition",
    "Pronoun",
    "Suffix",
    "Prefix",
    "Initialism",
    "Contraction",
    "Interjection",
    "Participle",
    "Numeral",
    "Adjective",
    "Preposition",
    "Adverb",
    "Particle",
    "Clitic",
    "Punctuation mark",
    "Acronym",
    "Ordinal number",
    "Idiom",
    "Proverb",
]

TRANSITIVITY = ["transitive", "intransitive"]
PERS = [
    "3rd-pers. singular",
    "3rd pers. singular",
    "3rd-person singular",
    "3rd person singular",
]
INFS = ["infinitive"]
PARTICIPLE = ["participle"]
MOODS = ["conditional", "indicative"]
PASS = ["passive", "active"]
IMPERSONAL = [
    "impersonal",
    "monopersonal",
]
PERSONAL = ["personal", "by person"]
ROLE = ["auxiliary"]  # aka fine grained pos
TENSE = ["past", "present"]
# XXX: We can have for example: "in simple past tense" - in this case simple
# should be removed so we don't try to put it in assoc
VERB_WORDS = (
    PERS
    + INFS
    + PARTICIPLE
    + MOODS
    + PASS
    + TRANSITIVITY
    + IMPERSONAL
    + PERSONAL
    + ROLE
    + TENSE
)
POS_HINT = {"coordinating": "conj"}


CASES = [
    # gram (obj)
    "nominative",
    "genitive",
    "genitive-accusative",
    "accusative",
    "partitive",
    # internal
    "inessive",
    "elative",
    "illative",
    # external
    "adessive",
    "ablative",
    "allative",
    # state-y
    "essive",
    "translative",
    # marginal
    "instructive",
    "abessive",
    "commitative",
]
ASSOC_POS = ["noun/adjective", "noun", "adjective"]
RELATIONS = ["direct object"]
NOMINAL_WORDS = CASES + ASSOC_POS + RELATIONS

GRAMMAR_WORDS = VERB_WORDS + PARTICIPLE + NOMINAL_WORDS

grammar_word_tokeniser = MWETokenizer(separator=" ")
for grammar_word in GRAMMAR_WORDS:
    bits = grammar_word.split(" ")
    if len(bits) > 1:
        grammar_word_tokeniser.add_mwe(bits)

UNINTERESTING = ["colloquial", "slang", "arithmetic"]
