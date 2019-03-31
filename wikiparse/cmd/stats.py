import json
from sqlitedict import SqliteDict
import wordfreq
from wordfreq.preprocess import preprocess_text, MULTI_DIGIT_RE
from collections import Counter
import pandas as pd
import csv
import click
import click_log


def freq(word):
    if (
        word != preprocess_text(word, "fi")
        or MULTI_DIGIT_RE.fullmatch(word)
        or word.startswith("-")
        or word.endswith("-")
    ):
        return 0
    return wordfreq.word_frequency(word, "fi")


def dicts2csv(dictlist, csvfile):
    # 1st pass: Get field names
    fieldnames = []
    for row in dictlist:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)

    # 2nd pass: Write out
    writer = csv.DictWriter(open(csvfile, "w"), delimiter=",", fieldnames=fieldnames)
    writer.writeheader()
    for row in dictlist:
        writer.writerow(row)


def print100(df):
    with pd.option_context("display.max_rows", None, "display.max_columns", None):
        print(df[:100])


def top_events(df, word_wise=False, freq=False):
    df_raw = df.drop(["word", "wf"], axis=1).fillna(0)
    if word_wise:
        df_raw = df_raw.astype(bool).astype(float)
    if freq:
        df_raw = df_raw.mul(df["wf"], axis=0)
    df_raw = df_raw.sum().transpose().sort_values(ascending=False)
    if not freq:
        return df_raw.astype(int)
    else:
        return df_raw * 100


@click.group()
@click_log.simple_verbosity_option()
def stats():
    pass


@stats.command()
@click.argument("inf")
@click.argument("outf")
def parse_stats_agg(inf, outf):
    word_rows = {}
    total_count = 0
    unknown_pos_titles = set()
    print("Loading into counters")
    with SqliteDict(
        inf, encode=json.dumps, decode=json.loads, journal_mode="WAL"
    ) as db:
        for doc in db.values():
            if doc["type"] == "word_event":
                word = doc["word"]
                if word not in word_rows:
                    word_rows[word] = Counter()
                row = word_rows[word]

                def inc(*bits):
                    row[" ".join(bits)] += 1

                inc(doc["event"])
                if doc["event"] == "unknown_structure":
                    inc(doc["event"], doc["nick"])
                    if doc["nick"] == "expect-only":
                        inc(doc["event"], doc["nick"], *doc["extra"][0])
                    elif doc["nick"] == "not-ux-lb":
                        inc(doc["event"], doc["nick"], doc["extra"][0])
                    elif doc["nick"] == "lb-fin-unknown":
                        inc(doc["event"], doc["nick"], *doc["extra"][1])
            elif doc["type"] == "total_count":
                total_count += doc["count"]
            elif doc["type"] == "unknown_pos_title":
                unknown_pos_titles.add(doc["title"])
            else:
                assert False
    print("Loaded into counters")

    print("Rejiggling")
    sorted_word_rows = []
    for word, word_row in word_rows.items():
        new_word_row = {"word": word, "wf": freq(word)}
        new_word_row.update(word_row)
        sorted_word_rows.append(new_word_row)
    print("Done regjiggling")

    print("Sorting")
    sorted_word_rows.sort(key=lambda row: row["wf"], reverse=True)
    print("Sorted")

    print("Total count", total_count)
    print("Unknown POS titles", unknown_pos_titles)
    print("Rows", len(sorted_word_rows))
    print("First", sorted_word_rows[0])

    dicts2csv(sorted_word_rows, outf)


@stats.command()
@click.argument("inf")
def parse_stats_probs(inf):
    df = pd.read_csv(inf)
    print("Total occurences")
    print100(top_events(df))
    print("Word-wise occurences")
    print100(top_events(df, word_wise=True))
    with pd.option_context("display.float_format", lambda x: "%.5f" % x):
        print("Frequency scaled word-wise occurences")
        print100(top_events(df, word_wise=True, freq=True))


@stats.command()
@click.argument("inf")
@click.argument("col")
def parse_stats_top10(inf, col):
    df = pd.read_csv(inf)
    df_col = df[["word", "wf", col]]
    print100(df_col.dropna())


@stats.command()
@click.argument("inf")
def parse_stats_cov(inf):
    df = pd.read_csv(inf)
    top = dict(top_events(df))
    success = top.get("success", 0)
    empty = top.get("empty", 0)
    total = success + empty
    error_df = df.drop(["success", "wf", "empty"], axis=1).set_index("word")
    partial_success = error_df.sum(axis=1).astype(bool).sum() - empty
    complete_success = success - partial_success
    print("Success:", success)
    print("Partial success:", partial_success)
    print("Complete success:", complete_success)
    print("Empty:", empty)
    print("Total:", total)
    print("Partial coverage: {:.1f}".format((success / total) * 100))
    print("Full coverage: {:.1f}".format((complete_success / total) * 100))
