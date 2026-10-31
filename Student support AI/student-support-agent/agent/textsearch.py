"""Tiny dependency-free BM25 ranker (used for policy retrieval AND memory selection)."""
import math
import re
from collections import Counter

STOP = set("""a an the is are was were be been am i me my we our you your of to in on at for from by with and or
but if then so as it its this that these those do does did can could should would will may might shall next much many year what which
who whom how when where why not no yes please tell about have has had get got into out up down over under again
also just than too very s t there their them they he she his her""".split())


def _stem(t: str) -> str:
    if len(t) > 4 and t.endswith("ies"):
        t = t[:-3] + "y"
    elif len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
        t = t[:-1]
    if len(t) > 5 and t.endswith("ing"):
        t = t[:-3]
    elif len(t) > 4 and t.endswith("ed"):
        t = t[:-2]
    if len(t) > 4 and t.endswith("e"):
        t = t[:-1]
    return t


def tokenize(text: str) -> list:
    return [_stem(t) for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOP]


class BM25:
    def __init__(self, docs, k1=1.4, b=0.75):
        self.k1, self.b = k1, b
        self.tokens = [tokenize(d) for d in docs]
        self.N = len(docs)
        self.avgdl = (sum(len(t) for t in self.tokens) / self.N) if self.N else 1.0
        self.tf = [Counter(t) for t in self.tokens]
        self.df = Counter()
        for t in self.tokens:
            self.df.update(set(t))

    def scores(self, query: str):
        """Returns [(score, matched_query_terms)] for every document."""
        q = set(tokenize(query))
        out = []
        for i in range(self.N):
            dl = len(self.tokens[i]) or 1
            s, matched = 0.0, 0
            for w in q:
                f = self.tf[i].get(w, 0)
                if not f:
                    continue
                matched += 1
                idf = math.log(1 + (self.N - self.df[w] + 0.5) / (self.df[w] + 0.5))
                s += idf * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
            out.append((s, matched))
        return out
