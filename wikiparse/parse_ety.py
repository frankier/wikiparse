from itertools import count
from mwparserfromhell.wikicode import Wikicode, Template
from .exceptions import mk_unknown_structure
from .template_data import ALL_DERIV_TEMPLATES
from .template_utils import template_matchers, lang_template_has, lang_template_get
from .models import DerivationType, Etymology, EtymologyBit, RelationType, Relation
from .normseg_data import TEMPLATE_NORMSEG_MAP
from .utils.iter import orelse


def proc_ety_only_derivation_template(template: Template):
    template_name = str(template.name)
    if template_name in ("prefix", "suffix", "affix", "compound"):
        # e.g. {{suffix|fi|ajaa|ja}}
        # e.g. {{compound|fi|toimi|alt1=toimeen|tulo}}.
        """
        prefix:
        |sc=
        Script code. See Wiktionary:Scripts
        |t1=, |t2=
        Glosses
        |tr1=, |tr2=
        Transliteration of word 1 and word 2 respectively (for non-Latin scripts)
        |alt1=, |alt2=
        Alternate text to display instead of the links.
        |pos1=, |pos2=
        Part-of-speech information. Additional unquoted explanatory text, coming after the transliteration and gloss.
        |nocat=1
        Suppresses categorization

        compound:
        |1=
        the language where the compound got formed.
        |nocat=1
        disables the categorization. This parameter needs to be used when the template is used in a language that is not |1=.
        |alt1=, |alt2= …
        Alternative display form of each part. Because Module:links will strip diacritics from a word when appropriate, this may not always be needed.
        |tr1=, |tr2= …
        Transliteration of each part.
        |t1=, |t2= …
        Translation gloss for each part
        |pos1=, |pos2= …
        Part-of-speech gloss for each part.
        """
        bits = []
        for param_num in count(1):
            alt_param_name = "alt{}".format(param_num)
            norm_param_num = param_num + 1
            bit = {}
            if lang_template_has(template, norm_param_num):
                bit["headword"] = str(lang_template_get(template, norm_param_num))
            else:
                break
            if template.has(alt_param_name):
                bit["alt"] = str(template.get(alt_param_name).value)
            bits.append(EtymologyBit(**bit))
        yield "ety-head", Etymology(
            DerivationType.compound
            if template_name == "compound"
            else DerivationType.derivation,
            bits,
            str(template),
        )


def proc_anywhere_derivation_template(template: Template):
    template_name = str(template.name)
    if template_name in ("comparative of", "superlative of", "agent noun of"):
        # e.g. {{comparative of|banaalisti|POS=adverb|lang=fi}}
        # {{superlative of|banaalisti|POS=adverb|lang=fi}}
        yield "ety-head", Etymology(
            DerivationType.derivation,
            [
                EtymologyBit(headword=str(lang_template_get(template, 2))),
                EtymologyBit(headword=TEMPLATE_NORMSEG_MAP[template_name]),
            ],
            str(template),
        )


REL_TMPL_TYPE_MAP = {
    "alternative form of": RelationType.alt_form,
    "alt form": RelationType.alt_form,
    "misspelling of": RelationType.misspelling,
    "abbreviation of": RelationType.abbrv,
    "short for": RelationType.abbrv,
    "contraction of": RelationType.abbrv,
}


def proc_relation_template(template: Template):
    template_name = str(template.name)
    if template_name == ("synonym of", "syn"):
        for param_num in count(2):
            if not lang_template_has(template, param_num):
                break
            yield "head", Relation(
                RelationType.synonym, lang_template_get(template, 2), str(template)
            )
    elif template_name in REL_TMPL_TYPE_MAP:
        yield "head", Relation(
            REL_TMPL_TYPE_MAP[template_name],
            lang_template_get(template, 2),
            str(template),
        )


def proc_form_template(template: Template):
    # e.g.
    template_name = str(template.name)
    if template_name in (
        "fi-verb form",
        "plural of",
        "fi-participle of",
        "fi-infinitive of",
        "fi-form of",
    ):
        # XXX TODO
        if template_name == "plural of":
            child = str(lang_template_get(template, 2))
        else:
            child = str(template.get(1))
        yield "ety-head", Etymology(
            DerivationType.inflection, [EtymologyBit(headword=child), EtymologyBit(headword="-inflection")], str(template)
        )


def proc_ety_derivation_template(template):
    return orelse(
        proc_ety_only_derivation_template(template),
        proc_anywhere_derivation_template(template),
    )


def proc_defn_head_template(template):
    return orelse(
        proc_anywhere_derivation_template(template),
        proc_relation_template(template),
        proc_form_template(template),
    )


def get_ety(wikicode: Wikicode):
    if " + " in wikicode:
        yield "exception", mk_unknown_structure("mwe-ety")
    templates = wikicode.filter_templates()
    t_match = template_matchers(templates)
    deriv_templates = t_match.intersection(ALL_DERIV_TEMPLATES)
    if len(deriv_templates) > 1:
        yield "exception", mk_unknown_structure("multi-template-ety")
    elif len(deriv_templates) == 1:
        yield from proc_ety_derivation_template(
            templates[t_match.index(deriv_templates[0])]
        )
    else:
        pass
    other_templates = t_match.difference(ALL_DERIV_TEMPLATES)
    for t_match in other_templates:
        yield "exception", mk_unknown_structure("unknown-template", str(t_match))
