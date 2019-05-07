import ujson


def json_load(file_like):
    try:
        file_like.fileno()
    except Exception:
        return ujson.loads(file_like.read())
    else:
        return ujson.load(file_like)
