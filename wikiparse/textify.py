from mwparserfromhell import parse


def expand_templates(defn, keep_lb=True, rm_gram=False):
    from wikiparse.parse_assoc import rm_gram_assoc

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
        defn = rm_gram_assoc(defn)

    return defn
