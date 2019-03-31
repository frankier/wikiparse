import click
import click_log
from wikiparse.tables import metadata
from wikiparse.utils.db import get_session


@click.group()
@click_log.simple_verbosity_option()
def db():
    pass


@db.command()
@click.argument("db")
def create(db: str):
    session = get_session(db)
    metadata.create_all(session().get_bind().engine)
