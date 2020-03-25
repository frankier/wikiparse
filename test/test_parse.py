import os
import re
from os.path import join as pjoin
from wikiparse.insert import flatten_senses
from wikiparse.parse import parse_enwiktionary_page
from wikiparse.parse_ety import proc_form_template
from wikiparse.utils.wikicode import parse_nested_list
from wikiparse.exceptions import (
    UnknownStructureException,
    EXTRA_STRICT,
    strictness,
    exception_filter,
)
from nose2.tools import params
from mwparserfromhell import parse
import ujson


def filter_unk(exc):
    if not isinstance(exc, UnknownStructureException):
        return True
    print('exc.log["nick"]', exc.log["nick"])
    return exc.log["nick"] != "unknown-template-ety"


cur_dir = os.path.dirname(os.path.realpath(__file__))


MIN_LENGTHS = {"kertoa": 3, "pitaa": 8, "saada": 8, "sanoa": 1, "tulla": 7}


def read_data(entry):
    data_dir = pjoin(cur_dir, "data")
    return open(pjoin(data_dir, entry)).read()


def flat_roundtrip_senses(defns):
    res = {}
    roundtripped = ujson.loads(ujson.dumps(defns))
    for full_id, _ety, _pos, sense in flatten_senses(roundtripped):
        res[full_id] = sense
    return res


@params(*MIN_LENGTHS.keys())
@exception_filter(filter_unk)
def test_parse_min_results(entry):
    """
    Smoke test to check parsing returns a minimum number of definitions.
    """
    defns, _heads = parse_enwiktionary_page(entry, read_data(entry))

    got_senses = len(flat_roundtrip_senses(defns))
    min_senses = MIN_LENGTHS[entry]
    assert got_senses >= min_senses, "Needed {} senses for {} but got {}".format(
        min_senses, entry, got_senses
    )


@params("ja", "humalassa", "on", "kertoa", "tulla")
@strictness(EXTRA_STRICT)
def test_parse_no_exceptions(entry):
    parse_enwiktionary_page(entry, read_data(entry), skip_ety=True)


TULLA_LIST = """
# {{lb|fi|intransitive}} to [[come]]
#: ''Hän '''tulee'''.''
#:: ''She '''comes'''.''
# {{lb|fi|intransitive|''elative'' + 3rd-pers. singular + ''noun/adjective in nominative or partitive'' '''''or''''' tulla by person + ''translative''}} to [[become]], [[get]], [[go]], [[turn]]
#: ''Hänestä '''tuli''' rikas.''
#:: ''She '''became''' rich.''
#: ''He '''tulivat''' hulluiksi.''
#:: ''They '''went''' crazy.''
# {{lb|fi|intransitive|impersonal|''genitive +'' 3rd-pers. singular + ''infinitive''}} to [[have]] to do, [[be]] to do, [[should]] do, be [[supposed to]] do
#: ''Minun '''tulee''' tehdä tämä huomiseksi.''
#:: ''I '''have to''' do this by tomorrow.''
# {{lb|fi|intransitive}} Auxiliary verb for emphasized future tense. Usually, the [[nonpast|nonpast tense]] should be used instead of this.
#: ''Nimeni on Tapani ja tapani '''tulette''' tuntemaan.
#:: ''My name is Tapani and you '''will''' learn my manners.''
# {{lb|fi|intransitive| + passive past participle in translative}} Auxiliary verb for passive voice.
#: ''Hän '''tuli''' valituksi''.
#:: ''He '''was''' chosen.''
#: ''Tapa tai '''tule''' tapetuksi''.
#:: ''Kill or '''be''' killed.''
# {{lb|fi|intransitive|slang}} to [[cum]], [[orgasm]]
# {{lb|fi|intransitive|''+ active past participle in translative''}} to [[manage]] to do (more or less unintentionally), [[succeed]] in doing (more or less unintentionally)
#: ''Hän '''tuli''' tehneeksi pahan virheen.''
#:: ''She '''managed''' to make a big mistake.''
""".strip()


def test_parse_nested_list_tulla():
    wikicode = parse(TULLA_LIST, skip_style_tags=True)
    result = parse_nested_list(wikicode)
    assert len(result) == 7
    assert sum(bool(elem.children) for elem in result) == 6


@exception_filter(filter_unk)
def test_vuotta_head_gram():
    defns, _heads = parse_enwiktionary_page("vuotta", read_data("vuotta"))
    ety1_form = defns["Etymology 1"]["Noun"][0].morph
    assert ety1_form and ety1_form["case"] == "abessive"
    ety2_form = defns["Etymology 2"]["Noun"][0].morph
    assert ety2_form and ety2_form["case"] == "partitive"


@params(
    ("ammattikorkeakoulu", "ammatti", "korkeakoulu"),
    ("voima", "voida", "-?ma"),
    ("aivojuovio", "aivo", "juova", "-?io"),
)
@exception_filter(filter_unk)
def test_compound_fi(compound, *subwords):
    defns, heads = parse_enwiktionary_page(compound, read_data(compound))
    found = 0
    for head in heads:
        if head["tag"] != "etymology-heading":
            continue
        assert head["ety_idx"] is None
        assert len(head["etys"]) == 1
        assert len(head["etys"][0]["bits"]) == len(subwords)
        for bit, subword in zip(head["etys"][0]["bits"], subwords):
            assert re.match(subword, bit["headword"])
        found += 1
    assert found == 1


@params(
    (
        "{{fi-form of|käydä|pr=first person|pl=singular|mood=indicative|tense=present}}",
        ("käydä", "-n"),
    ),
    ("{{fi-participle of|t=nega|puhua}}", ("puhua", "-ma", "-ton")),
    ("{{fi-form of|mikä|case=translative|pl=singular}}", ("mikä", "-ksi")),
)
def test_form_tags(template_str, expected):
    wikicode = parse(template_str)
    template = wikicode.filter_templates()[0]
    results = list(proc_form_template(template))
    assert len(results) == 1
    assert results[0][0] == "ety-head"
    assert tuple((bit.headword for bit in results[0][1].bits)) == expected


@exception_filter(filter_unk)
def test_pitaa_gram_rm():
    defns, _heads = parse_enwiktionary_page("pitaa", read_data("pitaa"))
    to_like_defn = defns["Verb"][0]
    assert "like" in to_like_defn.cleaned_defn
    assert "elative" not in to_like_defn.cleaned_defn
    to_prefer_defn = to_like_defn.subsenses[0]
    assert "prefer" in to_prefer_defn.cleaned_defn
    assert "elative" not in to_prefer_defn.cleaned_defn
    assert "=" not in to_prefer_defn.cleaned_defn


@exception_filter(filter_unk)
def test_saattaa():
    defns, heads = parse_enwiktionary_page("saattaa", read_data("saattaa"))
    verb_4_1 = defns["Verb"][3].subsenses[0].cleaned_defn
    assert "might" in verb_4_1
    assert "do, probably do" in verb_4_1


def test_syn_doesnt_become_sense():
    # TODO: Avoid parsing this syn into its own sense
    # TODO: Add it as a relation
    #   Step 1. to headword
    #   Step 2. to sense
    """
    defns, _heads = parse_enwiktionary_page("kayda", read_data("kayda"))
    assert len(defns["Verb"][3].subsenses) == 0
    """
    return


def test_empty_defn():
    # TODO: When defn contains only a relation, it should be put on the headword and no sense added
    """
    defns, _heads = parse_enwiktionary_page("kummaksua", read_data("kummaksua"))
    assert len(defns) == 0
    """
    return


@exception_filter(filter_unk)
def test_maki_not_gram_note():
    defns, heads = parse_enwiktionary_page("maki", read_data("maki"))
    assert (
        "a relatively large, usually rounded elevation of earth"
        in defns["Noun"][0].cleaned_defn
    )


THING = """
==Finnish==

===Noun===
{{fi-noun}}

# A [[thing]] (~ elative {{m|xxx}})
"""


@exception_filter(filter_unk)
def test_gram_note_has_formatting():
    defns, heads = parse_enwiktionary_page("test", THING)
    assert "thing" in defns["Noun"][0].cleaned_defn
    assert "elative" not in defns["Noun"][0].cleaned_defn
