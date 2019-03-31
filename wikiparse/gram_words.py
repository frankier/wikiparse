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
    "infinitive",
    "first infinitive",
    "1st infinitive",
    "second infinitive",
    "2nd infinitive",
    "third infinitive",
    "3rd infinitive",
    "fourth infinitive",
    "4th infinitive",
]
MOODS = ["conditional mood", "conditional", "indicative mood", "indicative"]
PASS = ["passive", "active"]
PERSONAL = ["impersonal", "personal", "by person"]  # == personal
ROLE = ["auxiliary"]
TENSE = ["past", "present"]
VERB_WORDS = PERS + MOODS + PASS + TRANSITIVITY + PERSONAL + ROLE + TENSE

VERB_TO_NOMINAL = ["participle"]

CASES = [
    "elative",
    "essive",
    "nominative",
    "partitive",
    "illative",
    "genitive",
    "genitive-accusative",
    "accusative",
    "translative",
]
ASSOC_POS = ["noun/adjective", "noun", "adjective"]
RELATIONS = ["direct object"]
NOMINAL_WORDS = CASES + ASSOC_POS + RELATIONS

GRAMMAR_WORDS = VERB_WORDS + VERB_TO_NOMINAL + NOMINAL_WORDS

grammar_word_tokeniser = MWETokenizer(separator=" ")
for grammar_word in GRAMMAR_WORDS:
    bits = grammar_word.split(" ")
    if len(bits) > 1:
        grammar_word_tokeniser.add_mwe(bits)

UNINTERESTING = ["colloquial", "slang", "arithmetic"]
