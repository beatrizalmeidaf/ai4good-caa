"""Preditor n-grama contextual (plano B, roda em qualquer aparelho).

score(w) = interpolação de P(w|contexto,anterior), P(w|a,b), P(w|b),
P(w|contexto), P(w). Mesma lógica é reimplementada em JS na página.
"""
from collections import Counter, defaultdict
L = dict(ctxb=0.35, tri=0.25, bi=0.2, ctx=0.1, uni=0.1)

class NGram:
    def __init__(self, use_ctx=True):
        self.use_ctx = use_ctx
        self.c = {k: defaultdict(Counter) for k in L}

    def fit(self, rows):
        for r in rows:
            ctx = f"{r['periodo']}|{r['local']}"
            seq = ["<s>", "<s>"] + r["seq"]
            for i in range(2, len(seq)):
                a, b, w = seq[i-2], seq[i-1], seq[i]
                self.c["ctxb"][f"{ctx}|{b}"][w] += 1
                self.c["tri"][f"{a}|{b}"][w] += 1
                self.c["bi"][b][w] += 1
                self.c["ctx"][ctx][w] += 1
                self.c["uni"][""][w] += 1
        return self

    def predict(self, periodo, local, prefix, vocab):
        ctx = f"{periodo}|{local}"
        seq = ["<s>", "<s>"] + list(prefix)
        a, b = seq[-2], seq[-1]
        keys = dict(ctxb=f"{ctx}|{b}", tri=f"{a}|{b}", bi=b, ctx=ctx, uni="")
        lam = dict(L)
        if not self.use_ctx:
            lam["ctxb"] = lam["ctx"] = 0
        out = {}
        dists = {k: (self.c[k].get(keys[k]), sum(self.c[k][keys[k]].values()) if keys[k] in self.c[k] else 0) for k in L}
        for w in vocab:
            s = 1e-6
            for k, (cnt, tot) in dists.items():
                if tot and lam[k]:
                    s += lam[k] * cnt[w] / tot
            out[w] = s
        return out

    def export(self):
        return {k: {kk: dict(v) for kk, v in d.items()} for k, d in self.c.items()}
