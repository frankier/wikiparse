from itertools import count
from mwparserfromhell.wikicode import Wikicode, Template
from .exceptions import mk_unknown_structure
from .data.template import ALL_DERIV_TEMPLATES
from .utils.template import template_matchers, lang_template_has, lang_template_get
from .models import DerivationType, Etymology, EtymologyBit, RelationType, Relation
from finntk.data.wiktionary_normseg import (
    TEMPLATE_NORMSEG_MAP,
    NOUN_FORM_OF_FIELDS_MAP,
    VERB_FORM_OF_FIELDS_MAP,
    PL_NORMSEG_MAP,
    CASE_NORMSEG_MAP,
    PARTICIPLES_NORM,
    PARTICIPLES_MAP,
    FI_INFINITIVES,
    FI_INFINITIVE_OF_ABBRVS,
    FI_INFINITIVE_DEFAULT_CASES,
)
from .utils.iter import orelse
from typing import List


def check_ety(ety: Etymology):
    if any(not bit.headword for bit in ety.bits):
        return "exception", mk_unknown_structure("empty-bit-in-ety")
    else:
        return "ety-head", ety


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
        yield check_ety(
            Etymology(
                DerivationType.compound
                if template_name == "compound"
                else DerivationType.derivation,
                bits,
                str(template),
            )
        )


def proc_anywhere_derivation_template(template: Template):
    template_name = str(template.name)
    if template_name in ("comparative of", "superlative of", "agent noun of"):
        # e.g. {{comparative of|banaalisti|POS=adverb|lang=fi}}
        # {{superlative of|banaalisti|POS=adverb|lang=fi}}
        yield check_ety(
            Etymology(
                DerivationType.derivation,
                [
                    EtymologyBit(headword=str(lang_template_get(template, 2))),
                    EtymologyBit(headword=TEMPLATE_NORMSEG_MAP[template_name]),
                ],
                str(template),
            )
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


def extract_normsegs(template, feat_map):
    for feat, normseg_mapping in feat_map.items():
        if normseg_mapping is None:
            # Passthrough (suffix)
            if not template.has(feat):
                continue
            seg = str(template.get(feat).value)
        elif isinstance(feat, str):
            if not template.has(feat):
                continue
            feat_val = str(template.get(feat).value)
            if feat_val not in normseg_mapping:
                continue
            seg = normseg_mapping[feat_val]
        else:
            assert feat == ("pr", "pl")  # Special cased
            if not template.has("pr"):
                continue
            pr_feat = str(template.get("pr").value).replace(" ", "-")
            pl_feat = (
                str(template.get("pl").value) if template.has("pl") else "singular"
            )
            if (pr_feat, pl_feat) not in normseg_mapping:
                continue
            seg = normseg_mapping[(pr_feat, pl_feat)]
        if seg is not None:
            yield seg


def add_normsegs(normsegs, new_normsegs):
    if new_normsegs is None:
        return
    elif isinstance(new_normsegs, str):
        normsegs.append(new_normsegs)
    else:
        normsegs.extend(new_normsegs)


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
        if template_name == "plural of":
            child = str(lang_template_get(template, 2))
        else:
            child = str(template.get(1))
        inflection_bits: List[str] = []
        if template_name in ["fi-verb form", "fi-form of"]:
            if template.has("case"):
                # It's a nominal
                fields_map = NOUN_FORM_OF_FIELDS_MAP
            else:
                # Assume it's a verb
                fields_map = VERB_FORM_OF_FIELDS_MAP
            inflection_bits = list(extract_normsegs(template, fields_map))
        elif template_name == "fi-participle of":
            participle = str(template.get("t").value)
            if participle in PARTICIPLES_NORM:
                participle = PARTICIPLES_NORM[participle]
            add_normsegs(inflection_bits, PARTICIPLES_MAP[participle])
            if template.has("plural"):
                inflection_bits.append(PL_NORMSEG_MAP["plural"])
            if template.has("case"):
                case_normseg = CASE_NORMSEG_MAP[str(template.get("case").value)]
                add_normsegs(inflection_bits, case_normseg)
        elif template_name == "fi-infinitive of":
            infinitive = str(template.get("t").value)
            add_normsegs(inflection_bits, FI_INFINITIVES[infinitive])
            if template.has("c"):
                case_name = FI_INFINITIVE_OF_ABBRVS[str(template.get("c").value)]
            else:
                case_name = FI_INFINITIVE_DEFAULT_CASES[infinitive]
            case_normseg = CASE_NORMSEG_MAP[case_name]
            add_normsegs(inflection_bits, case_normseg)
        else:
            add_normsegs(inflection_bits, TEMPLATE_NORMSEG_MAP[template_name])
        if template.has("suffix"):
            inflection_bits.append(str(template.get("suffix").value))
        # XXX: TODO log unprocessed template info
        if len(inflection_bits) > 0:
            yield check_ety(
                Etymology(
                    DerivationType.inflection,
                    [EtymologyBit(headword=child)]
                    + [EtymologyBit(headword=inf) for inf in inflection_bits],
                    str(template),
                )
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
        yield "exception", mk_unknown_structure("unknown-template-ety", list(t_match))
