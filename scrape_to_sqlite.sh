#!/usr/bin/env bash

DEFS_DIR="$(basename $1).defns"
mkdir $DEFS_DIR
python parse.py parse-dump $1 --outdir $DEFS_DIR
./create_insert_sqlite.sh $DEFS_DIR $2
