# Wikiparse

Scrapes some Finnish word definitions from English Wiktionary.

Usage:

    $ poetry install
    $ DATABASE_URL=enwiktionary-20171001.db poetry run ./scrape_to_sqlite.sh ~/corpora/enwiktionary-20171001-pages-meta-current.xml

You can also pipe straight from lbunzip2 run a multistream bzip2 file which
should be about as fast on a multiprocessor machine (pbunzip2 segfaults when
piped directly into wikiparse):

    $ sudo apt install lbunzip2 
    $ lbunzip2 -c ~/corpora/enwiktionary-latest-pages-articles-multistream.xml.bz2 | poetry run python parse.py parse-dump - --outdir enwiktionary.defns
