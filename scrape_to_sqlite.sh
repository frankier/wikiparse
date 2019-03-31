#!/usr/bin/env bash

DEFS_DIR="$(basename $1).defns"
DB="sqlite:///$2"
mkdir $DEFS_DIR
python parse.py create $DB
python parse.py parse-dump $1 --outdir $DEFS_DIR
python parse.py insert-dir $DEFS_DIR $DB
