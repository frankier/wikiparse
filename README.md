# Wikiparse

Scrapes some Finnish word definitions from English Wiktionary.

## Usage

    $ poetry install
    $ DATABASE_URL=sqlite:///enwiktionary-20171001.db poetry run ./scrape_to_sqlite.sh ~/corpora/enwiktionary-20171001-pages-meta-current.xml

You can also pipe straight from lbunzip2 run a multistream bzip2 file which
should be about as fast on a multiprocessor machine (pbunzip2 segfaults when
piped directly into wikiparse):

    $ sudo apt install lbunzip2 
    $ lbunzip2 -c ~/corpora/enwiktionary-latest-pages-articles-multistream.xml.bz2 | poetry run python parse.py parse-dump - --outdir enwiktionary.defns

## Coverage info

You can generate coverage info by passing e.g. `--stats-db stats.db` when
running parse-dump and then running:

    $ poetry run python parse.py parse-stats-agg stats.db stats.csv
    $ poetry run python parse.py parse-stats-cov stats.csv

You can get a breakdown of the top problems affecting the coverage like so:

    $ poetry run python parse.py parse-stats-probs stats.csv

For each of these problems, you can then get the most frequent words affected
by it (e.g. so it can be turned into a test later):

    $ poetry run python parse.py parse-stats-probs parse-stats-top10 "my-problem"

Please consult the source code for more information on what the different
problems mean.
