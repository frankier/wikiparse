import os
from wikiparse.utils.mod_data import set_jsons_path
from wikiparse.utils.fst import LazyFst


def pytest_configure(config):
    set_jsons_path(os.path.join(os.path.dirname(__file__), "data/mod_data"))
    if "FST_DIR" in os.environ:
        LazyFst.set_fst_dir(os.environ["FST_DIR"])
