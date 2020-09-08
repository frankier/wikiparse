## Environment variables
from os.path import join as pjoin

def cnf(name, val):
    globals()[name] = config.setdefault(name, val)

# Intermediate dirs
cnf("WORK", "work")
cnf("WIKIPAGES", WORK + "/pages")
cnf("MOD_DATA", WORK + "/mod_data")
cnf("FSTS", WORK + "/fsts")
cnf("PARSED", WORK + "/parsed")
cnf("STATS", WORK + "/stats")
cnf("LOG", WORK + "/log")

# Input
WIKIDUMP = config["WIKIDUMP"]

rule all:
    input:
        defns_db = WORK + "/defns.db",
        agg_csv = STATS + "/stats.csv"

rule make_dumpsplit:
    output:
        "dumpsplit/target/release/dumpsplit"
    shell:
        "cd dumpsplit && ./build.sh"

rule run_dumpsplit:
    input:
        dumpsplit = "dumpsplit/target/release/dumpsplit",
        wikidump = WIKIDUMP
    output:
        wikipages = directory(WIKIPAGES)
    shell:
        "mkdir -p {output.wikipages}" +
        " && lbunzip2 -c {input.wikidump} | {input.dumpsplit} {output.wikipages}"

rule clone_scribunto:
    output:
        directory("dumplabels/Scribunto")
    shell:
        "cd dumplabels && git clone https://gerrit.wikimedia.org/r/mediawiki/extensions/Scribunto"

rule run_dumplabels:
    input:
        wikipages = WIKIPAGES,
        scribunto = "dumplabels/Scribunto"
    output:
        mod_data = directory(MOD_DATA)
    shell:
        "mkdir -p " + MOD_DATA +
        " && MOD_DUMP_PATH={input.wikipages}/modules luajit dumplabels/dump_labels.lua" +
        " > {output.mod_data}/labels.json" +
        " && python dumplabels/non_gram.py" +
        " {output.mod_data}/labels.json" +
        " {output.mod_data}/non_gram.json" +
        " {output.mod_data}/pos_categories.json"

rule run_makefsts:
    input:
        mod_data = MOD_DATA,
    output:
        fsts = directory(FSTS)
    shell:
        "mkdir -p " + FSTS +
        " && python parse.py make-fsts" +
        " --mod-data {input.mod_data}"
        " {output.fsts}"

rule run_wikiparse:
    input:
        mod_data = MOD_DATA,
        wikipages = WIKIPAGES,
        fsts = FSTS
    output:
        parsed = directory(PARSED),
        stats_db = STATS + "/stats.db"
    log:
        LOG + "/wikiparse.log"
    shell:
        "mkdir -p {output.parsed}" +
        " && python parse.py parse-pages {input.wikipages}/fin"
        " --outdir {output.parsed} --stats-db {output.stats_db}"
        " --fsts-dir {input.fsts}"
        " > {log} 2>&1"

rule insert_wikiparse:
    input:
        parsed = PARSED,
    output:
        defns_db = WORK + "/defns.db"
    shell:
        "export DATABASE_URL=sqlite:///{output.defns_db};" + 
        " python parse.py create" +
        " && python parse.py insert-dir {input.parsed}"

rule proc_stats:
    input:
        stats_db = STATS + "/stats.db"
    output:
        agg_csv = STATS + "/stats.csv",
        cov = STATS + "/cov.txt",
        probs = STATS + "/probs.txt"
    shell:
        "python parse.py parse-stats-agg {input.stats_db} {output.agg_csv}" + 
        " && python parse.py parse-stats-cov {output.agg_csv} > {output.cov}" + 
        " && python parse.py parse-stats-probs {output.agg_csv} > {output.probs}"

onsuccess:
    shell("cp {log} " + LOG + "/snakemake.log")
