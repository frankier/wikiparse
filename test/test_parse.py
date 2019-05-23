import os
from os.path import join as pjoin
from wikiparse.insert import flatten_senses
from wikiparse.parse import parse_enwiktionary_page
from wikiparse.utils.wikicode import parse_nested_list
from wikiparse.exceptions import EXTRA_STRICT, strictness
from nose2.tools import params
from mwparserfromhell import parse

cur_dir = os.path.dirname(os.path.realpath(__file__))


MIN_LENGTHS = {"kertoa": 3, "pitaa": 8, "saada": 8, "sanoa": 1, "tulla": 7}


def read_data(entry):
    data_dir = pjoin(cur_dir, "data")
    return open(pjoin(data_dir, entry)).read()


@params(*MIN_LENGTHS.keys())
def test_parse_min_results(entry):
    """
    Smoke test to check parsing returns a minimum number of definitions.
    """
    defns, _heads = parse_enwiktionary_page(entry, read_data(entry))

    got_senses = len(list(flatten_senses(defns)))
    min_senses = MIN_LENGTHS[entry]
    assert got_senses >= min_senses, "Needed {} senses for {} but got {}".format(
        min_senses, entry, got_senses
    )


@params("ja", "humalassa", "on", "kertoa", "tulla")
def test_parse_no_exceptions(entry):
    with strictness(EXTRA_STRICT):
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


def test_vuotta_head_gram():
    defns, _heads = parse_enwiktionary_page("vuotta", read_data("vuotta"))
    ety1_form = defns["Etymology 1"]["Noun"][0].morph
    assert ety1_form and ety1_form["case"] == "abessive"
    ety2_form = defns["Etymology 2"]["Noun"][0].morph
    assert ety2_form and ety2_form["case"] == "partitive"
