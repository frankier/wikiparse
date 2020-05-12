import json
import sys


def is_non_gram(info):
    return (
        "plain_categories" in info
        or "topical_categories" in info
        or "regional_categories" in info
    )


def iter_labels(labels):
    for label, info in labels["labels"].items():
        yield label, info
    for alias, label in labels["aliases"].items():
        if label not in labels["labels"]:
            print("Broken alias:", alias, label)
            continue
        info = labels["labels"][label]
        yield label, info


def main(labels_json, non_gram_json, pos_categories_json):
    labels = json.load(open(labels_json))
    non_gram_labels = []
    pos_categories = {}
    for label, info in iter_labels(labels):
        if is_non_gram(info):
            non_gram_labels.append(label)
        elif "pos_categories" in info:
            pos_categories[label] = info["pos_categories"]

    json.dump(non_gram_labels, open(non_gram_json, "w"))
    json.dump(pos_categories, open(pos_categories_json, "w"))


if __name__ == "__main__":
    main(*sys.argv[1:])
