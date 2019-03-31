def merge_dl(into, frm):
    for k in into:
        if k in frm:
            into[k].extend(frm[k])
