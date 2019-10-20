from pprint import pprint
import click
from wikiparse.utils.db import get_session
from wikiparse.queries import lemma_info_query, headword_rels_counts_query, RELATED


@click.group()
def lookup_group():
    pass


@lookup_group.command()
@click.argument("word")
def lookup(word):
    session = get_session()
    query = lemma_info_query([word])
    print("Counts")
    for row in session.execute(headword_rels_counts_query([word])):
        if not row[0]:
            print("Not found")
            continue
        print("# " + row[0])
        for (name, _, _), cnt in zip(RELATED, row[1:]):
            print(name, cnt)
    print("Senses")
    for row in session.execute(query):
        pprint(row)
