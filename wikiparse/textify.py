from mwparserfromhell import parse


def expand_templates(defn, keep_lb=True, rm_text=None):
    wikicode = parse(defn)
    for t in wikicode.filter_templates():
        if t.name in ("l", "link"):
            wikicode.replace(t, "[[{}]]".format(t.get(2)))
        elif t.name in ("lb",) and keep_lb:
            wikicode.replace(t, "({})".format(t.get(2)))
        elif t.name in ("gloss", "qualifier"):
            wikicode.replace(t, "({})".format(t.get(1)))
        else:
            wikicode.remove(t)
    if rm_text is not None:
        wikicode.replace(rm_text, "")

    return wikicode
