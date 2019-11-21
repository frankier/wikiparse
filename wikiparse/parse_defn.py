import re
from mwparserfromhell.wikicode import Wikicode, Template
from typing import Any, List, Optional, Dict, Iterator, Tuple
from mwparserfromhell import parse

from dataclasses import asdict
from .utils.wikicode import double_strip, TextTreeNode, TextTreeList, block_templates
from .utils.iter import extract
from .utils.nlp import detect_fi_en, has_grammar_word, BRACKET_RE
from .models import DefnTreeFrag, Defn, Example

from .exceptions import unknown_structure, UnknownStructureException, expect_only
from .template_data import FORM_TEMPLATES, DEFN_TEMPLATES, DERIV_TEMPLATES, NON_GLOSS_TEMPLATES
from .template_utils import template_matchers
from .parse_assoc import proc_lb_template_assoc, proc_text_assoc, mk_assoc_bits
from .parse_ety import proc_defn_head_template

EARLY_THRESH = 5
DEFN_TEMPLATE_START = re.compile(r"{{(lb|lbl|label)\|fi\|")


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


def get_defn_info(defn: str) -> Defn:
    raw_defn = defn
    parsed_defn = parse(defn)
    defn_dirty = False
    templates = block_templates(parsed_defn)
    assoc_cmds: List[Tuple[str, Any]] = []
    assoc_cmds.extend(proc_lb_template_assoc(templates))
    for template in templates:
        parsed_defn.remove(template)
        defn_dirty = True
    for template in parsed_defn.filter_templates():
        if template.name != "qualifier":
            continue
        assoc_cmds.append(("qualifiers", str(template.get(1))))
        parsed_defn.remove(template)
        defn_dirty = True
    if defn_dirty:
        defn = str(parsed_defn)
    # XXX: If there's already some info this might be in brackets because it's
    # optional -- should detect this case

    new_assoc_cmds, new_defn = extract(
        proc_text_assoc(defn), lambda elem: elem[0] == "defn"
    )
    assoc_cmds.extend(new_assoc_cmds)
    assoc = mk_assoc_bits(assoc_cmds)
    assert len(new_defn) == 1
    defn = new_defn[0][1]

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


def proc_defn_form_template(tmpl: Template):
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
    contents: Wikicode, children_result: DefnTreeFrag, non_gloss: bool=False, morph_dict: Optional[Dict] = None
) -> DefnTreeFrag:
    result = DefnTreeFrag()
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
    result.non_gloss = non_gloss
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


def get_senses_and_examples_defn(
    defn: TextTreeNode, level: int
) -> Iterator[Tuple[str, Any]]:
    to_propagate, children_result = extract(
        get_senses_and_examples(defn.children, level + 1),
        lambda elem: elem[0] == "frag",
    )
    yield from to_propagate
    children_result = children_result[0][1]
    contents = defn.contents
    flatten_templates(contents)
    templates = block_templates(contents)
    t_match = template_matchers(templates)
    is_lb_template = False
    is_ux_template = False
    morph_dict = None
    ux_template = None
    non_gloss = False

    def get_template(matches):
        return templates[t_match.index(matches[0])]

    if not t_match:
        # No template
        pass
    elif t_match.issubset(DEFN_TEMPLATES):
        is_lb_template = True
        form_templates_matches = t_match.intersection(FORM_TEMPLATES | DERIV_TEMPLATES)
        if form_templates_matches:
            if len(form_templates_matches) > 1:
                unknown_structure(
                    "multiple-form-tmpls", repr(list(form_templates_matches))
                )
            form_template = get_template(form_templates_matches)
            # Get etys for adding to headword
            yield from proc_defn_head_template(form_template)
            # Put form stuff on defns
            if form_templates_matches.intersection(FORM_TEMPLATES):
                morph_dict = proc_defn_form_template(form_template)
        non_gloss_template_matches = t_match.intersection(NON_GLOSS_TEMPLATES)
        if non_gloss_template_matches:
            non_gloss = True
            template = get_template(non_gloss_template_matches)
            new_contents = str(template.get(1))
            contents.remove(template)
            if contents.strip():
                contents = new_contents + " " + str(contents)
            else:
                contents = new_contents
    elif t_match.issubset({("ux", "fi")}):
        is_ux_template = True
        ux_template = templates[0]
    else:
        unknown_structure("not-ux-lb", t_match)
    is_sense = level == 0 or detect_sense(str(contents)) or is_lb_template
    if is_sense and not is_ux_template:
        yield "frag", proc_sense(contents, children_result, non_gloss, morph_dict)
    else:
        if is_ux_template:
            yield "frag", proc_example(contents, children_result, ux_template)
        else:
            yield "frag", proc_example(contents, children_result)


def get_senses_and_examples(
    nested_list: TextTreeList, level: int
) -> Iterator[Tuple[str, Any]]:
    result = DefnTreeFrag()
    for defn in nested_list:
        try:
            for act, payload in get_senses_and_examples_defn(defn, level):
                if act == "frag":
                    result.merge(payload)
                else:
                    yield act, payload
        except UnknownStructureException as exc:
            exc.add_info(defn)
            yield "exception", exc
        except Exception as e:
            print("Exception caused by ", defn)
            raise e
    yield "frag", result


def get_senses(nested_list: TextTreeList) -> Iterator[Tuple[str, Any]]:
    for act, payload in get_senses_and_examples(nested_list, 0):
        if act == "frag":
            yield "defn", payload.senses
        else:
            yield act, payload
