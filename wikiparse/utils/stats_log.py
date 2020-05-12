from uuid import uuid4
from sqlitedict import SqliteDict
import orjson


class DbStatsLogger:
    def __init__(self, dbfn):
        self.dbfn = dbfn
        self.reopen()

    def reopen(self):
        self.db = SqliteDict(
            self.dbfn,
            encode=orjson.dumps,
            decode=orjson.loads,
            autocommit=True,
            journal_mode="WAL",
        )

    def append(self, record):
        self.db[uuid4().bytes] = record


class NullStatsLogger:
    def reopen(self):
        pass

    def append(self, record):
        pass


_stats_logger = NullStatsLogger()


def get_stats_logger():
    return _stats_logger


def install_db_stats_logger(dbfn):
    global _stats_logger
    _stats_logger = DbStatsLogger(dbfn)
