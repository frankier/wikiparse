#!/usr/bin/env bash

DB="sqlite:///$2"
python parse.py create $DB
python parse.py insert-dir $1 $DB
