from tarfile import TarFile
from os.path import join as pjoin, isdir, basename
import os


def merge_dl(into, frm):
    for k in into:
        if k in frm:
            into[k].extend(frm[k])


class IterDirOrTar(object):
    def __init__(self, indir, members=None):
        self.indir = indir
        self.members = members

    def __len__(self):
        if self.members is not None:
            return len(self.members)
        if isdir(self.indir):
            return len(os.listdir(self.indir))
        else:
            tf = TarFile(self.indir)
            return sum((1 for m in tf.getmembers() if m.isfile()))

    def word_included(self, word):
        return (
            self.members is None
            or word in self.members
            or word.strip("-") in self.members
        )

    def __iter__(self):
        if isdir(self.indir):
            for word in os.listdir(self.indir):
                if not self.word_included(word):
                    continue
                with open(pjoin(self.indir, word), "rb") as defn_fp:
                    yield word, defn_fp
        else:
            tf = TarFile(self.indir)
            for member in tf.getmembers():
                word = basename(member.name)
                if not self.word_included(word):
                    continue
                if member.isfile():
                    yield word, tf.extractfile(member)
