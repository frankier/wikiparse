import click
from wikiparse.cmd.db import db as db_group
from wikiparse.cmd.parse import parse as parse_group
from wikiparse.cmd.stats import stats as stats_group
import click_log

click_log.basic_config()


parse = click.CommandCollection(sources=[db_group, parse_group, stats_group])


if __name__ == "__main__":
    parse()
