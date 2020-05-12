from boltons.setutils import IndexedSet


def lang_template_idx_adjust(template, idx):
    """
    Many templates take lang as the first parameter, except if the deprecated
    lang parameter is passed, in which case all the parameters are moved back a
    position. This normalises these cases.
    """
    assert idx >= 1
    if template.has("lang"):
        return idx - 1
    else:
        return idx


def lang_template_has(template, idx):
    return template.has(lang_template_idx_adjust(template, idx))


def lang_template_get(template, idx):
    return template.get(lang_template_idx_adjust(template, idx))


def template_matcher(template):
    from wikiparse.data.template import LANG_TEMPLATES

    name = str(template.name)
    if name in LANG_TEMPLATES:
        if template.has("lang"):
            return (name, str(template.get("lang").value))
        else:
            return (name, str(template.get(1).value))
    else:
        return (name,)


def template_matchers(templates):
    return IndexedSet((template_matcher(template) for template in templates))


def expand_templates(defn, keep_lb=True, rm_gram=False):
    from mwparserfromhell import parse
    from wikiparse.assoc.identispan import identispan_text_rm

    wikicode = parse(defn)

    for t in wikicode.filter_templates(recursive=False):
        if t.name in ("l", "link"):
            wikicode.replace(t, "[[{}]]".format(expand_templates(t.get(2))))
        elif t.name in ("lb",) and keep_lb:
            wikicode.replace(t, "({})".format(expand_templates(t.get(2))))
        elif t.name in ("gloss", "qualifier"):
            wikicode.replace(t, "({})".format(expand_templates(t.get(1))))
        else:
            wikicode.remove(t)

    defn = str(wikicode)
    if rm_gram:
        defn = identispan_text_rm(defn)

    return defn
