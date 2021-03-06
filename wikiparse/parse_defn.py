import re
from mwparserfromhell.wikicode import Wikicode, Template
from typing import Any, List, Optional, Dict, Iterator, Tuple
from mwparserfromhell import parse

from dataclasses import asdict
from .utils.wikicode import double_strip, TextTreeNode, TextTreeList, block_templates
from .utils.iter import extract
from .utils.nlp import detect_fi_en, BRACKET_RE
from .models import DefnTreeFrag, Defn, Example

from .exceptions import unknown_structure, UnknownStructureException, expect_only
from .data.template import (
    FORM_TEMPLATES,
    DEFN_TEMPLATES,
    UX_TEMPLATES,
    DERIV_TEMPLATES,
    NON_GLOSS_TEMPLATES,
)
from .utils.template import expand_templates, template_matchers
from .assoc.identispan import identispan_lb_tmpl, identispan_text, has_grammar_word
from .assoc.models import (
    AssocFrame,
    AssocSpanType,
    PipelineResult,
    AssocSpan,
)
from .assoc import pipeline_spans
from .context import ParseContext
from .parse_ety import proc_defn_head_template

EARLY_THRESH = 5
DEFN_TEMPLATE_START = re.compile(r"{{(lb|lbl|label)\|fi\|")
GLOSS_TEMPLATE_START = re.compile(r"{{gloss\|")


def detect_sense(contents: str) -> bool:
    if (
        "=" in contents
        or DEFN_TEMPLATE_START.search(str(contents))
        or GLOSS_TEMPLATE_START.search(str(contents))
    ):
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


def get_defn_info(ctx: ParseContext, defn: str) -> Defn:
    raw_defn = defn
    parsed_defn = parse(defn)
    defn_dirty = False
    templates = block_templates(parsed_defn)
    spans = []
    grams = []
    tmpl_span = identispan_lb_tmpl(templates)
    if tmpl_span is not None:
        spans.append(tmpl_span)
    for template in templates:
        parsed_defn.remove(template)
        defn_dirty = True
    for template in parsed_defn.filter_templates():
        if template.name != "qualifier":
            continue
        grams.append(
            PipelineResult(
                span=AssocSpan(
                    typ=AssocSpanType.qualifier_template, payload=str(template),
                ),
                tree=AssocFrame(qualifiers=[str(template.get(1))]),
            )
        )
        parsed_defn.remove(template)
        defn_dirty = True
    if defn_dirty:
        defn = str(parsed_defn)

    # defn is just thrown away at this point. it is overly stripped
    spans.extend(identispan_text(defn))
    grams.extend(pipeline_spans(ctx, spans))

    lb_in_defn = True
    for gram in grams:
        if gram.span.typ == AssocSpanType.lb_template and gram.tree_has_gram:
            lb_in_defn = False
    expanded = expand_templates(raw_defn, keep_lb=lb_in_defn, rm_gram=True)

    return Defn(
        raw_defn=raw_defn,
        cleaned_defn=expanded,
        stripped_defn=double_strip(parse(expanded)),
        grams=grams,
    )


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
    ctx: ParseContext,
    contents: Wikicode,
    children_result: DefnTreeFrag,
    non_gloss: bool = False,
    morph_dict: Optional[Dict] = None,
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
        defn_info = get_defn_info(ctx, defn_txt)
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
    sense_dict.non_gloss = non_gloss
    subsenses = children_result.senses + sense_dicts[1:]
    if len(subsenses):
        sense_dict.subsenses = subsenses
    result.senses.append(sense_dict)
    return result


def proc_example(
    ctx: ParseContext,
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
    ctx: ParseContext, defn: TextTreeNode, level: int
) -> Iterator[Tuple[str, Any]]:
    to_propagate, children_result = extract(
        get_senses_and_examples(ctx, defn.children, level + 1),
        lambda elem: elem[0] == "frag",
    )
    yield from to_propagate
    children_result = children_result[0][1]
    contents = defn.contents
    templates = block_templates(contents)
    t_match = template_matchers(templates)
    is_lb_template = False
    is_ux_template = False
    morph_dict = None
    ux_template = None
    non_gloss = False

    def get_template(matches):
        return templates[t_match.index(matches[0])]

    if not t_match or contents is None:
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
            # TODO: Not sure about this removal of the template
            # Should grammar notes within n-g be excluded?
            non_gloss = True
            template = get_template(non_gloss_template_matches)
            new_contents = str(template.get(1))
            contents.remove(template)
            if contents.strip():
                contents = new_contents + " " + str(contents)
            else:
                contents = new_contents
    elif t_match.issubset(UX_TEMPLATES):
        is_ux_template = True
        ux_template = templates[0]
    else:
        unknown_structure("not-ux-lb", list(t_match))
    is_sense = level == 0 or detect_sense(str(contents)) or is_lb_template
    if is_sense and not is_ux_template:
        yield "frag", proc_sense(ctx, contents, children_result, non_gloss, morph_dict)
    else:
        if is_ux_template:
            yield "frag", proc_example(ctx, contents, children_result, ux_template)
        else:
            yield "frag", proc_example(ctx, contents, children_result)


def get_senses_and_examples(
    ctx: ParseContext, nested_list: TextTreeList, level: int
) -> Iterator[Tuple[str, Any]]:
    result = DefnTreeFrag()
    for defn in nested_list:
        try:
            for act, payload in get_senses_and_examples_defn(ctx, defn, level):
                if act == "frag":
                    result.merge(payload)
                    for sense in payload.senses:
                        for gram in sense.grams:
                            if isinstance(gram.tree, UnknownStructureException):
                                exc = gram.tree
                                exc.add_info(defn)
                                yield "exception", exc
                else:
                    yield act, payload
        except UnknownStructureException as exc:
            exc.add_info(defn)
            yield "exception", exc
        except Exception as e:
            print("Exception caused by ", defn)
            raise e
    yield "frag", result


def get_senses(
    ctx: ParseContext, nested_list: TextTreeList
) -> Iterator[Tuple[str, Any]]:
    for act, payload in get_senses_and_examples(ctx, nested_list, 0):
        if act == "frag":
            yield "defn", payload.senses
        else:
            yield act, payload
