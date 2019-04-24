import click
import click_log
from wikiparse.tables import metadata
from wikiparse.utils.db import get_session


@click.group()
@click_log.simple_verbosity_option()
def db():
    pass


@db.command()
def create():
    session = get_session()
    metadata.create_all(session().get_bind().engine)


@db.command()
def trunc():
    session = get_session()

    for t in reversed(metadata.sorted_tables):
        print("Dropping", t.name)
        session.execute(f"TRUNCATE {t.name} RESTART IDENTITY CASCADE;")
    session.commit()
