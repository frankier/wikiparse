import os
import orjson

jsons_path = None


def set_jsons_path(new_jsons_path):
    global jsons_path
    if jsons_path is not None:
        raise Exception("Can't set jsons_path twice")
    jsons_path = new_jsons_path


def get(name):
    if jsons_path is None:
        raise Exception("Trying to get data before set_jsons_path(...) called")
    # Not putting into registry at the moment since they're all used only once
    # at the moment
    return orjson.loads(open(os.path.join(jsons_path, name + ".json"), "rb").read())
