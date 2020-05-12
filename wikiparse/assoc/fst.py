import hfst
from ..utils.fst import (
    braces,
    untokuni,
    seq,
    out,
    union,
    maptoks,
    fst_frombits,
    fst_fromseq,
    opt,
    optinp,
    inp,
    rep,
    esc,
    LazyFst,
    from_dict,
)
from ..data.gram_words import (
    TRANSITIVITY,
    PERSONAL,
    PARTICIPLE,
    MOODS,
    PASS,
    ROLE,
    TENSE,
    CASES,
    RELATIONS,
    GRAMMAR_WORDS,
    POS_HINT,
)


def output_tags(pairs):
    return union([seq(out(tag), untokuni(vals)) for tag, vals in pairs])


def build_bit_fst():
    # TODO:
    # Handle tagging main verb/other verb
    # e.g. saattaa: 'auxiliary, + first infinitive; in simple past tense'
    # Handle OR
    # e.g. käydä: intransitive, + inessive or adessive

    # Optional in CASE expression
    opt_in_case = opt(
        seq(
            inp("in"),
            optinp("the"),
            out("case"),
            untokuni(CASES),
            rep(seq(inp("or"), out("case"), untokuni(CASES),)),
            optinp("case"),
        )
    )

    # Noun form descriptors / General
    gen_nom_words = [
        ("case", CASES),
    ]
    noun_gen_fst = fst_fromseq(out("pos", "nom"), output_tags(gen_nom_words))

    # Noun form descriptors / POS / RELATION in CASE
    # e.g. noun/adjective in nominative or partitive
    noun_pos_case_txt = seq(
        union(
            [
                seq(
                    # ASSOC_POS
                    out("pos"),
                    union(["noun", "adjective"]),
                ),
                seq(out("pos", "nom", "rel"), untokuni(RELATIONS)),
            ]
        ),
        opt_in_case,
    )
    noun_pos_case_fst = fst_fromseq(noun_pos_case_txt)

    # Verb form descriptors / General
    gen_verb_words = [
        ("pass", PASS),
        ("trans", TRANSITIVITY),
        ("personal", PERSONAL),
        ("role", ROLE),
    ]
    verb_gen_fst = fst_fromseq(out("pos", "verb"), output_tags(gen_verb_words))

    # Verb form descriptors / Person
    verb_pers_fst = fst_fromseq(
        out("pos", "verb", "pers"),
        "[[{}] : sg3]".format(
            union(
                [
                    braces(
                        seq(
                            *(
                                esc(tok)
                                for tok in f"{third}{dash}{pers} singular".split(" ")
                            )
                        )
                    )
                    for third in ("3rd", "third")
                    for dash in (" ", "-")
                    for pers in ("pers.", "person")
                ]
            )
        ),
    )

    # Verb form descriptors / Mood
    mood_expr = untokuni(MOODS), optinp("mood")
    verb_mood_fst = fst_fromseq(
        optinp("in", "the"),
        out("pos", "verb", "mood"),
        *mood_expr,
        rep(seq(out("mood"), optinp("or"), *mood_expr)),
    )

    # Verb form descriptors / Tense
    verb_tense_fst = fst_fromseq(
        optinp("in", "the", "simple"),
        out("pos", "verb", "tense"),
        untokuni(TENSE),
        optinp("tense"),
    )

    # Verb form descriptors / Infinitives
    norm_ords = (
        "[first:1st | 1st | second:2nd | 2nd | third:3rd | 3rd | fourth:4th | 0:1st]"
    )
    infinitive_fst = fst_fromseq(
        optinp("with"),
        out("pos", "verb"),
        opt(seq(out("pass"), untokuni(PASS))),
        out("inf"),
        norm_ords,
        inp("infinitive"),
        opt_in_case,
    )

    # Verb form descriptors / Participles
    # e.g. passive past participle in translative
    # e.g. with active participle
    # XXX: "with" should maybe be treated like +
    participle_fst = fst_fromseq(
        optinp("with"),
        out("pos", "verb"),
        opt(seq(out("pass"), untokuni(PASS))),
        out("part"),
        untokuni(PARTICIPLE),
        opt_in_case,
    )

    # POS hint
    pos_hint_fst = fst_fromseq(
        out("pos"), from_dict({k: [v] for k, v in POS_HINT.items()})
    )

    # Headword
    headword_fst = fst_frombits(maptoks((esc("~"),), ("rel", "headword")))

    # Symbols
    emph_symbols = union(
        [
            maptoks((esc("+"),), ("sym", "plus")),
            maptoks((esc(";"),), ("sym", "semicolon")),
            maptoks((esc("or"),), ("sym", "or")),
            maptoks((esc("/"),), ("sym", "slash")),
        ]
    )
    symbol_fst = fst_frombits(
        union(
            [
                seq(emph_symbols, out("style", "none")),
                seq(inp("''"), emph_symbols, inp("''"), out("style", "italic")),
                seq(inp("'''"), emph_symbols, inp("'''"), out("style", "bold")),
                seq(
                    inp("'''''"), emph_symbols, inp("'''''"), out("style", "bolditalic")
                ),
                # ignore symbols we don't need
                inp(esc(",")),
                inp(esc("_")),
                inp(esc("[[")),
                inp(esc("]]")),
                # We're only using these with '''''or''''' at the moment
                # (Relying on longest match behaviour)
                inp(esc("''")),
                inp(esc("'''")),
                inp(esc("'''''")),
            ]
        )
    )

    # Union FST
    return hfst.disjunct(
        (
            noun_gen_fst,
            noun_pos_case_fst,
            verb_gen_fst,
            verb_pers_fst,
            verb_mood_fst,
            verb_tense_fst,
            infinitive_fst,
            participle_fst,
            pos_hint_fst,
            headword_fst,
            symbol_fst,
        )
    )


def build_lb_tmpl_bit_fst():
    from wikiparse.utils.mod_data import get

    non_gram = get("non_gram")
    pos_categories = get("pos_categories")
    for gram_word in GRAMMAR_WORDS:
        if gram_word not in pos_categories:
            continue
        del pos_categories[gram_word]
    return hfst.disjunct(
        (
            build_bit_fst(),
            fst_fromseq(out("nongramcat"), untokuni(non_gram),),
            fst_fromseq(out("poscat"), from_dict(pos_categories),),
        )
    )


bit_fst = LazyFst("build_bit_fst", build_bit_fst, assert_non_empty=True)
lb_tmpl_bit_fst = LazyFst(
    "build_lb_tmpl_bit_fst", build_lb_tmpl_bit_fst, assert_non_empty=True
)
