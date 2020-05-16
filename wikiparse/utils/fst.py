import hfst

import os
from typing import List, Tuple
from itertools import zip_longest


def seq(*exprs: str) -> str:
    "Sequence `exprs`"
    return " ".join(exprs)


def braces(expr: str) -> str:
    "Add brace to `expr`"
    return "[" + expr + "]"


def union(exprs: List[str]) -> str:
    "Put `exprs` in a union so any can be followed"
    return braces(" | ".join(exprs))


def untok(lit):
    "Take the individual tokens in `lit` and merge them into a multiword token"
    return braces(
        braces(" ".join((esc(bit) for bit in lit.split(" ")))) + " : " + esc(lit)
    )


def untokuni(lits):
    "For every lit in `lits`, merge into a multiword"
    return union(untok(lit) for lit in lits)


def esc(lit):
    "Escape `lit` so that no characters inside it are treated as special"
    return '"' + lit.replace('"', '%"') + '"'


def escuni(lits):
    "For every lit in `lits`, escape"
    return union(esc(lit) for lit in lits)


def from_dict(d):
    return union(
        braces(braces(" ".join(esc(bit) for bit in k.split(" "))) + " : " + esc(v))
        for k, vs in d.items()
        for v in vs
    )


def maptoks(ins, outs):
    pairs = []
    for inp, out in zip_longest(ins, outs, fillvalue="0"):
        pairs.append(inp + " : " + out)
    return braces(" ".join(pairs))


def inp(*ins):
    return maptoks(ins, ())


def out(*outs):
    return maptoks((), outs)


def optinp(*ins):
    return " ".join((f"({inp}:0)" for inp in ins))


def opt(expr: str) -> str:
    return "(" + expr + ")"


def rep(expr: str) -> str:
    return braces(expr) + "*"


class XreError(Exception):
    pass


def req_regex(expr: str):
    retval = hfst.regex(expr)
    if retval is None:
        raise XreError(f"Did not get FST back from XFST RE: {expr}")
    return retval


def fst_frombits(*bits):
    """
    Make a transducer from `bits`
    """
    return req_regex("".join(bits))


def fst_fromseq(*exprs):
    """
    Make a transducer from `exprs`
    """
    regex = seq(*exprs)
    return req_regex(regex)


def finalise_transducer(transducer):
    transducer.minimize()
    # transducer.lookup_optimize()
    return transducer


def lookup_tokens(fst, tokens_tup):
    for _, output in fst.lookup(tokens_tup, output="raw"):
        yield tuple((tok for tok in output if tok and tok != hfst.EPSILON))


def save(fst, outf):
    ostr = hfst.HfstOutputStream(filename=outf, type=fst.get_type())
    ostr.write(fst)
    ostr.flush()
    ostr.close()


def load(inf):
    istr = hfst.HfstInputStream(inf)
    fst = istr.read()
    istr.close()
    return fst


registry = {}


def fst2tokfst(fst):
    from hfst import EPSILON, UNKNOWN, IDENTITY

    for sym in fst.get_alphabet():
        if sym in (EPSILON, UNKNOWN, IDENTITY, ""):
            continue
        fst.substitute(sym, sym + " ", input=True, output=False)


class LazyFst:
    fst_dir = None

    @classmethod
    def set_fst_dir(cls, new_fst_dir):
        cls.fst_dir = new_fst_dir

    def __init__(self, name, build_fst, assert_non_empty=False):
        self.name = name
        self.build_fst = build_fst
        self._bare_fst = None
        self._match_at_start_fst = None
        self._fst = None
        self.assert_non_empty = assert_non_empty
        registry[name] = self

    def _path(self, var, fst_dir=None):
        return os.path.join(fst_dir or self.fst_dir, f"{self.name}.{var}.fst")

    def _save_fst(self, fst, var, fst_dir):
        save(fst, self._path(var, fst_dir))

    def save_fsts(self, fst_dir):
        self._save_fst(self.get_bare_fst(), "bare", fst_dir)
        self._save_fst(self.get_fst(), "opt", fst_dir)
        self._save_fst(self.get_match_at_start_fst(), "start", fst_dir)

    def _load_fst(self, var):
        return load(self._path(var))

    def load_fsts(self, include_bare=False):
        if self.fst_dir is None:
            raise ValueError("load_fsts(...) called before fst_dir set")
        if include_bare:
            self._bare_fst = self._load_fst("bare")
        self._fst = self._load_fst("opt")
        self._match_at_start_fst = self._load_fst("start")

    def get_bare_fst(self):
        if self._bare_fst is None:
            if self.fst_dir is not None:
                self.load_fsts(True)
            else:
                self._bare_fst = self.build_fst()
                fst2tokfst(self._bare_fst)
        return self._bare_fst.copy()

    def build_match_at_start_fst(self):
        transducer = self.get_bare_fst()
        end_then_id = req_regex("[?*]:0")
        transducer.input_project()
        transducer.concatenate(end_then_id)
        return transducer

    def get_match_at_start_fst(self):
        if self._match_at_start_fst is None:
            if self.fst_dir is not None:
                self.load_fsts()
            else:
                self._match_at_start_fst = finalise_transducer(
                    self.build_match_at_start_fst()
                )
        return self._match_at_start_fst

    def get_fst(self):
        if self._fst is None:
            if self.fst_dir is not None:
                self.load_fsts()
            else:
                self._fst = finalise_transducer(self.get_bare_fst())
        if self.assert_non_empty:
            results = list(lookup_tokens(self._fst, ()))
            assert (
                len(results) == 0
            ), f"Got results for empty lookup from FST: {results!r}"
        return self._fst

    def lookup_partial(
        self, tokens: List[str], longest_only=False
    ) -> List[Tuple[List[str], List[str]]]:
        results = []
        tokens_tup = tuple((tok + " " for tok in tokens))
        match_start_res = lookup_tokens(self.get_match_at_start_fst(), tokens_tup)
        if longest_only:
            new_match_start_res: List[List[str]] = []
            new_match_start_res_len = 0
            for match_input in match_start_res:
                match_input_len = len(match_input)
                if match_input_len > new_match_start_res_len:
                    new_match_start_res = []
                    new_match_start_res_len = match_input_len
                new_match_start_res.append(match_input)
            match_start_res = new_match_start_res
        for matched_input in match_start_res:
            outputs_res = lookup_tokens(self.get_fst(), matched_input)
            for output in outputs_res:
                results.append((output, tokens[len(matched_input) :]))
        return results
