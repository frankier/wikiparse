from wikiparse.db.tables import metadata
from .mk_db import mk_cmds


db = mk_cmds(lambda: metadata)
