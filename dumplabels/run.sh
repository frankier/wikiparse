git clone https://gerrit.wikimedia.org/r/mediawiki/extensions/Scribunto
MOD_DUMP_PATH=$1/modules luajit dump_labels.lua > labels.json
