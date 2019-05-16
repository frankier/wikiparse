def orelse(*iters):
    found = False
    for iter in iters:
        for elem in iter:
            found = True
            yield elem
        if found:
            break


def extract(it, pred):
    extracted = []

    def filtered_it():
        nonlocal extracted
        for elem in it:
            if pred(elem):
                extracted.append(elem)
            else:
                yield elem

    return filtered_it(), extracted
