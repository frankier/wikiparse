from tarfile import TarFile
from os.path import join as pjoin, isdir, basename
import os


def merge_dl(into, frm):
    for k in into:
        if k in frm:
            into[k].extend(frm[k])


class IterDirOrTar(object):
    def __init__(self, indir):
        self.indir = indir

    def __len__(self):
        if isdir(self.indir):
            return len(os.listdir(self.indir))
        else:
            tf = TarFile(self.indir)
            return sum((1 for m in tf.getmembers() if m.isfile()))

    def __iter__(self):
        if isdir(self.indir):
            for word in os.listdir(self.indir):
                with open(pjoin(self.indir, word), "rb") as defn_fp:
                    yield word, defn_fp
        else:
            tf = TarFile(self.indir)
            for member in tf.getmembers():
                if member.isfile():
                    yield basename(member.name), tf.extractfile(member)
