from boltons.setutils import IndexedSet
from .template_data import LANG_TEMPLATES


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
