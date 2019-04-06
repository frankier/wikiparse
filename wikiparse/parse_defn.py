import re
from .models import DefnTreeFrag
from mwparserfromhell.wikicode import Wikicode, Template
from typing import cast, Any, List, Optional, Dict
import logging
from mwparserfromhell import parse
from langdetect import detect_langs
from langdetect.lang_detect_exception import LangDetectException
from boltons.setutils import IndexedSet

from dataclasses import asdict
from wikiparse.utils.wikicode import double_strip, TextTreeNode, TextTreeList
from .models import AssocBits, Defn, Example, TextTreeDictTree2L, DefnListDictTree2L

from .gram_words import (
    TRANSITIVITY,
    PERSONAL,
    VERB_WORDS,
    VERB_TO_NOMINAL,
    NOMINAL_WORDS,
    GRAMMAR_WORDS,
    grammar_word_tokeniser,
)
from .exceptions import (
    unknown_structure,
    UnknownStructureException,
    expect_only,
    get_strictness,
    PERMISSIVE,
    EXTRA_STRICT,
)

EARLY_THRESH = 5
BIT_STOPWORDS = [
    "in",
    # XXX: should capture information about this
    "or",
]
INLINE_TEMPLATES = ["link", "l", "mention", "m", "qualifier"]
OUR_LANGS = ("en", "fi")
DEFN_TEMPLATE_START = re.compile(r"{{(lb|lbl|label)\|fi\|")
BRACKET_RE = re.compile(r"\(.*\)")
GRAMMAR_NOTE_RE = re.compile(r"\(.*({}).*\)".format("|".join(GRAMMAR_WORDS)))

FI_2ND_TEMPLATES = {"ux", "lb"}
LANG_PARAM_TEMPLATES = {"plural of"}
FORM_TEMPLATES = {
    ("fi-verb form of",),
    ("plural of", "fi"),
    ("fi-participle of",),
    ("fi-infinitive of",),
    ("fi-form of",),
}
DEFN_FORM_TEMPLATES = FORM_TEMPLATES | {("lb", "fi")}


def has_grammar_word(txt: str) -> bool:
    return any(grammar_word in txt for grammar_word in GRAMMAR_WORDS)


def detect_fi_en(content: str) -> Optional[str]:
    try:
        langs = detect_langs(content)
    except LangDetectException:
        return None
    for lang in langs:
        if lang.lang in OUR_LANGS:
            return lang.lang
    return None


def detect_sense(contents: str) -> bool:
    if "=" in contents or DEFN_TEMPLATE_START.search(str(contents)):
        return True
    # XXX: Can probably be more fine grained here
    if has_grammar_word(contents) and "usage" not in contents:
        return True
    return False


def detect_new_sense(contents: str) -> bool:
    template_match = DEFN_TEMPLATE_START.search(str(contents))
    bracket_match = BRACKET_RE.search(contents)
    if "=" in contents:
        before, after = contents.split("=", 1)
        return has_grammar_word(before)
    elif template_match and 0 <= template_match.start(0) < EARLY_THRESH:
        return True
    elif bracket_match and bracket_match.start() < EARLY_THRESH:
        return True
    return False


def tokenise_grammar_words(bit: str) -> List[str]:
    bit_tokens = bit.split()
    return grammar_word_tokeniser.tokenize(bit_tokens)


def parse_bit(bit: str, prefer_subj=False, prefer_nom=False) -> AssocBits:
    result = AssocBits()
    bit = parse(bit.strip("'")).strip_code()
    if bit in NOMINAL_WORDS or bit in (VERB_WORDS + VERB_TO_NOMINAL) and prefer_nom:
        if prefer_subj:
            result.subj.append(bit)
        else:
            result.obj.append(bit)
    elif bit in VERB_WORDS:
        result.verb.append(bit)
    else:
        bit_tokens = tokenise_grammar_words(bit)
        for sw in BIT_STOPWORDS:
            if sw in bit_tokens:
                bit_tokens.remove(sw)
        bit = " ".join(bit_tokens)
        if ";" in bit:
            bits = bit.split(";")
            for bit in bits:
                result.merge(parse_bit(bit.strip()))
        elif len(bit_tokens) > 1:
            # XXX: This is far too aggressive. Luckily the last case should
            # catch most problems
            prefer_nom = any(vtn in bit_tokens for vtn in VERB_TO_NOMINAL)
            for bit in bit_tokens:
                result.merge(parse_bit(bit, prefer_nom=prefer_nom))
        elif bit == "~":
            # XXX: This could have useful positional information, but for now
            # we just throw it away
            pass
        elif bit:
            detected = detect_fi_en(bit)
            if detected == "en":
                unknown_structure("eng-assoc", str(bit))
            if detected != "fi":
                unknown_structure("non-fin-assoc", str(bit))
            result.assoc.append(bit)
    return result


def parse_assoc_bits(txt: str) -> AssocBits:
    result = AssocBits()
    bits = txt.split("+")
    first = True
    for bit in bits:
        bit = bit.strip().strip("'").strip()
        result.merge(parse_bit(bit, prefer_subj=first))
        first = False
    return result


# def remove_extra_words(txt):
# return txt.replace('in ', '').strip()


def parse_bit_or_bits(bit: str) -> AssocBits:
    if "+" in bit:
        return parse_assoc_bits(bit)
    else:
        return parse_bit(bit)


def filter_lb_template(templates):
    filtered = [template for template in templates if template.name == "lb"]
    if filtered:
        assert len(filtered) == 1
        return filtered[0]
    return None


def get_defn_info(defn: str) -> Defn:
    raw_defn = defn
    parsed_defn = parse(defn)
    defn_dirty = False
    templates = block_templates(parsed_defn)
    lb_template = filter_lb_template(templates)
    assoc = AssocBits()
    if lb_template:
        for idx, param in enumerate(lb_template.params[1:]):
            if param == "_":
                continue

            if param in (TRANSITIVITY + PERSONAL):
                assoc.verb.append(str(param))
            elif "+" in param:
                assoc.merge(parse_assoc_bits(param))
            else:
                assoc.qualifiers.append(str(param))
    for template in templates:
        parsed_defn.remove(template)
        defn_dirty = True
    for template in parsed_defn.filter_templates():
        if template.name != "qualifier":
            continue
        assoc.qualifiers.append(str(template.get(1)))
        parsed_defn.remove(template)
        defn_dirty = True
    if defn_dirty:
        defn = str(parsed_defn)
    # XXX: If there's already some info this might be in brackets because it's
    # optional -- should detect this case
    matches = GRAMMAR_NOTE_RE.finditer(defn)
    for match in matches:
        # print('MATCH', match, type(match))
        match_text = match.group(0)
        bit = match_text.strip().strip("()").strip()
        try:
            note_parsed = parse_bit_or_bits(bit)
        except UnknownStructureException:

            # XXX: Should probably not catch all UnknownStructureException
            # exceptions but just when an en word goes into assoc (or avoid
            # exceptions

            if get_strictness() == EXTRA_STRICT:
                raise
            assoc.extra_grammar.append(bit)
        else:
            assoc.merge(note_parsed)
        defn = defn.replace(match_text, "")
        defn = defn.replace("  ", " ")

    if "=" in defn:
        if defn.count("=") > 1:
            unknown_structure("too-many-=s")
        before, after = defn.split("=")
        # print('BEFORE', before)
        if not has_grammar_word(before):
            unknown_structure("no-grammar-=")
        if "+" not in before:
            unknown_structure("need-+-before-=")
        for bracket in BRACKET_RE.findall(before):
            assoc.merge(parse_bit_or_bits(bracket.strip("()")))
            before = before.replace(bracket, "")
        assoc.merge(parse_assoc_bits(before))
        defn = after

    return Defn(
        raw_defn=raw_defn,
        cleaned_defn=defn,
        stripped_defn=double_strip(parse(defn)),
        assoc=assoc,
    )


def flatten_templates(contents: Wikicode):
    for template in contents.filter_templates():
        if template.name == "gloss":
            contents.replace(template, "({})".format(template.get(1)))


def block_templates(contents: Wikicode) -> List[Template]:
    return [t for t in contents.filter_templates() if t.name not in INLINE_TEMPLATES]


def template_matcher(template):
    name = str(template.name)
    if name in LANG_PARAM_TEMPLATES:
        return (name, str(template.get("lang").value))
    elif name in FI_2ND_TEMPLATES:
        return (name, str(template.get(1)))
    else:
        return (name,)


def template_matchers(templates):
    return IndexedSet((template_matcher(template) for template in templates))


def proc_form_template(tmpl: Template):
    name = str(tmpl.name)
    form_gram = {"type": "form", "template": name}
    if name == "plural of":
        form_gram["lemma"] = str(tmpl.get(1).value)
    else:
        for idx, param in enumerate(tmpl.params):
            if not str(param.name).isdigit():
                form_gram[str(param.name)] = str(param.value)
            if idx == len(tmpl.params) - 1:
                form_gram["lemma"] = str(param.value)
    return form_gram


def proc_sense(
    contents: Wikicode,
    children_result: DefnTreeFrag,
    form_template: Optional[Template] = None,
) -> DefnTreeFrag:
    result = DefnTreeFrag()
    morph_dict = None
    if form_template is not None:
        morph_dict = proc_form_template(form_template)
    # Sense
    # multiple senses
    defns = contents.split(";")
    prev_idx = 0
    cur_idx = 1
    for sub_defn in defns[1:]:
        if not detect_new_sense(sub_defn):
            # Not a new definition -- merge into previous definition
            defns[prev_idx] = "{};{}".format(defns[prev_idx], sub_defn)
            del defns[cur_idx]
        else:
            prev_idx += 1
            cur_idx += 1
    if len(defns) > 2:
        unknown_structure("too-many-subsenses", len(defns))
    sense_dicts = []
    for defn_txt in defns:
        defn_info = get_defn_info(defn_txt)
        if morph_dict is not None:
            defn_info.morph = morph_dict
        sense_dicts.append(defn_info)
    example_type = None
    examples: List[Any] = []
    if len(children_result.bi_examples):
        expect_only(asdict(children_result), ("bi_examples", "senses"))
        example_type = "bi_examples"
        examples = children_result.bi_examples
    elif len(children_result.fi_examples):
        expect_only(asdict(children_result), ("fi_examples", "unk_examples", "senses"))
        example_type = "fi_examples"
        examples = children_result.fi_examples + [
            Example(fi=children_result.unk_examples)
        ]
    elif len(children_result.en_examples):
        expect_only(asdict(children_result), ("en_examples", "unk_examples", "senses"))
        # print('children_result', children_result)
        unknown_structure("eng-example-only")
    elif len(children_result.unk_examples):
        expect_only(asdict(children_result), ("unk_examples", "senses"))
        example_type = "fi_examples"
        examples = children_result.unk_examples
    else:
        # No examples
        pass
    if example_type:
        if len(defns) == len(examples):
            # Assume each one subexample for each subsense
            for sense_dict, example in zip(sense_dicts, examples):
                setattr(sense_dict, example_type, [example])
        else:
            # Put all examples under first sense
            setattr(sense_dicts[0], example_type, examples)
    sense_dict = sense_dicts[0]
    subsenses = children_result.senses + sense_dicts[1:]
    if len(subsenses):
        sense_dict.subsenses = subsenses
    result.senses.append(sense_dict)
    return result


def proc_example(
    contents: Wikicode,
    children_result: DefnTreeFrag,
    template: Optional[Template] = None,
) -> DefnTreeFrag:
    result = DefnTreeFrag()
    # Example
    if len(children_result.senses):
        unknown_structure("sense-under-example")
    if template:
        en = None
        try:
            en = str(template.get(3))
        except ValueError:
            try:
                en = str(template.get("t"))
            except ValueError:
                pass
        fi = str(template.get(2))
        if en is None:
            result.fi_examples.append(Example(fi=[fi]))
        else:
            result.bi_examples.append(Example(fi=[fi], en=[en]))
        stripped = double_strip(contents)
        if stripped:
            unknown_structure("leftover-example-tmpl", stripped)
    else:
        example = double_strip(contents)
        lang = detect_fi_en(example)

        def add_with_child(parent_lang: str, child_lang: str):
            child_key = "{}_examples".format(child_lang)
            expect_only(asdict(children_result), (child_key, "unk_examples"))
            child_examples = (
                getattr(children_result, child_key) + children_result.unk_examples
            )
            if len(child_examples) == 1:
                result.bi_examples.append(
                    Example(**{parent_lang: [example], child_lang: child_examples})
                )
            else:
                getattr(result, "{}_examples".format(parent_lang)).append(example)

        if lang == "fi":
            add_with_child("fi", "en")
        elif lang == "en":
            add_with_child("en", "fi")
        else:
            # unknown
            if len(children_result.unk_examples):
                unknown_structure("unknown-under-unknown")
            fi_ex = children_result.fi_examples
            en_ex = children_result.en_examples
            if len(fi_ex + en_ex) > 1:
                unknown_structure("max-one-example-below")
            if len(fi_ex):
                add_with_child("en", "fi")
            elif len(en_ex):
                add_with_child("fi", "en")
            else:
                result.unk_examples.append(example)
    return result


def get_senses_and_examples_defn(defn: TextTreeNode, level: int) -> DefnTreeFrag:
    children_result = get_senses_and_examples(defn.children, level + 1)
    contents = defn.contents
    flatten_templates(contents)
    templates = block_templates(contents)
    t_match = template_matchers(templates)
    is_lb_template = False
    is_ux_template = False
    is_form_template = False
    form_template = None
    ux_template = None
    if not t_match:
        # No template
        pass
    elif t_match.issubset(DEFN_FORM_TEMPLATES):
        is_lb_template = True
        form_templates_matches = t_match.intersection(FORM_TEMPLATES)
        if form_templates_matches:
            if len(form_templates_matches) > 1:
                unknown_structure(
                    "multiple-form-tmpls", repr(list(form_templates_matches))
                )
            is_form_template = True
            form_template = templates[t_match.index(form_templates_matches[0])]
    elif t_match.issubset({("ux", "fi")}):
        is_ux_template = True
        ux_template = templates[0]
    else:
        unknown_structure("not-ux-lb", ", ".join([repr(m) for m in t_match]))
    is_sense = level == 0 or detect_sense(str(contents)) or is_lb_template
    if is_sense and not is_ux_template:
        if is_form_template:
            return proc_sense(contents, children_result, form_template)
        else:
            return proc_sense(contents, children_result)
    else:
        if is_ux_template:
            return proc_example(contents, children_result, ux_template)
        else:
            return proc_example(contents, children_result)


def get_senses_and_examples(nested_list: TextTreeList, level: int) -> DefnTreeFrag:
    result = DefnTreeFrag()
    for defn in nested_list:
        try:
            result.merge(get_senses_and_examples_defn(defn, level))
        except UnknownStructureException as e:
            e.add_info(defn)
            if get_strictness() == PERMISSIVE:
                logging.exception("Ignored since in permissive mode: %s", defn)
            else:
                raise e
        except Exception as e:
            print("Exception caused by ", defn)
            raise e
    return result


def get_senses(nested_list: TextTreeList) -> List[Defn]:
    return get_senses_and_examples(nested_list, 0).senses


def map_tree_to_senses(defn_lists: TextTreeDictTree2L) -> DefnListDictTree2L:
    if defn_lists:
        if isinstance(next(iter(defn_lists.values())), list):
            defn_lists = cast(Dict[str, TextTreeList], defn_lists)
            return {pos: get_senses(defn_list) for pos, defn_list in defn_lists.items()}
        else:
            defn_lists = cast(Dict[str, Dict[str, TextTreeList]], defn_lists)
            return {
                ety: {
                    pos: get_senses(defn_list) for pos, defn_list in defn_dict.items()
                }
                for ety, defn_dict in defn_lists.items()
            }
    empty_dict: Dict[str, List[Defn]] = {}
    return empty_dict
