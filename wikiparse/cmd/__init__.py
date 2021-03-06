import click
from wikiparse.cmd.db import db as db_group
from wikiparse.cmd.parse import parse as parse_group
from wikiparse.cmd.stats import stats as stats_group
from wikiparse.cmd.lookup import lookup_group
from wikiparse.cmd.fst import fst_group


merged = click.CommandCollection(
    sources=[db_group, parse_group, stats_group, lookup_group, fst_group],
    help="Commands for Wiktionary parsing and ETL",
)
