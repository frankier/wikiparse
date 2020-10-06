import click
import click_log
import logging
from wikiparse.utils.db import get_session

logger = logging.getLogger(__name__)


def mk_cmds(get_metadata):
    def drop_trunc(which, extra=""):
        metadata = get_metadata()
        session = get_session()

        for t in reversed(metadata.sorted_tables):
            logger.info("%s %s", which, t.name)
            session.execute(f"{which} {t.name} {extra} CASCADE;")
        session.commit()

    @click.group()
    @click_log.simple_verbosity_option()
    def db():
        pass

    @db.command()
    def create():
        metadata = get_metadata()
        session = get_session()
        metadata.create_all(session().get_bind().engine)

    @db.command()
    def recreate():
        drop_trunc("DROP TABLE IF EXISTS")
        create.callback()

    @db.command()
    def trunc():
        drop_trunc("TRUNCATE", "RESTART IDENTITY")

    return db
