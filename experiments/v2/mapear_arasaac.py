"""Mapeia pares [lema_pt, lema_en] para IDs de pictogramas ARASAAC (catálogo completo).

Prioridade de candidatos:
  +4 o lema pt aparece nas palavras-chave pt (pt-PT) do mesmo pictograma (confirmação cruzada)
  +3 o lema en é a palavra-chave principal (1ª) do pictograma
  +1 pictograma marcado como próprio para CAA / vocabulário núcleo
  descarta sexo/violência; desempate pelo menor ID (pictogramas clássicos)
"""
import json, re, pathlib, unicodedata
from collections import defaultdict
RAW = pathlib.Path(__file__).resolve().parent.parent.parent / "data_raw"

def norm(s):
    s = s.lower().strip()
    s = re.sub(r"^(to|a|an|the)\s+", "", s)
    s = re.sub(r"[!?.¡¿,]", "", s)
    return re.sub(r"\s+", " ", s).strip()

def strip_acc(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

# termos que o modelo gerador usa e o ARASAAC chama de outro jeito
SINON_EN = {"play dough": "plasticine", "playdough": "plasticine", "modeling clay": "plasticine",
            "cell phone": "mobile phone", "cellphone": "mobile phone", "tv": "television",
            "poop": "poo", "potty": "potty", "mom": "mother", "mommy": "mother", "dad": "father", "daddy": "father",
            "grandma": "grandmother", "grandpa": "grandfather", "teacher": "teacher", "fries": "chips"}

class Mapper:
    def __init__(self):
        en = json.load(open(RAW / "arasaac_all_en.json"))
        pt = json.load(open(RAW / "arasaac_all_pt.json"))
        self.meta = {}
        self.en_idx, self.en_primary = defaultdict(set), defaultdict(set)
        for p in en:
            if p.get("sex") or p.get("violence"): continue
            pid = p["_id"]
            self.meta[pid] = dict(cats=p.get("categories", []), tags=p.get("tags", []), aac=p.get("aac", False),
                                  type=(p["keywords"][0].get("type") if p["keywords"] else None),
                                  en=[k["keyword"] for k in p["keywords"]])
            for i, k in enumerate(p["keywords"]):
                kw = k.get("keyword") or ""
                forms = {kw, k.get("plural")}
                if kw.endswith("s") and len(kw) > 3: forms.add(kw[:-1])  # 'grapes' -> 'grape'
                for form in forms:
                    if form:
                        self.en_idx[norm(form)].add(pid)
                        if i == 0: self.en_primary[norm(form)].add(pid)
        self.pt_kw = defaultdict(set); self.pt_idx = defaultdict(set); self.pt_first = defaultdict(set)
        for p in pt:
            for k in p["keywords"]:
                for form in (k.get("keyword"), k.get("plural")):
                    if form:
                        f = strip_acc(norm(form))
                        self.pt_kw[p["_id"]].add(f); self.pt_idx[f].add(p["_id"])
                        if " " in f: self.pt_first[f.split(" ")[0]].add(p["_id"])
        self.cache = {}

    def score(self, pid, pt, en):
        m = self.meta[pid]
        s = 0
        if pt in self.pt_kw.get(pid, ()): s += 2
        if pid in self.en_primary.get(en, ()): s += 3
        if m["aac"] or any("core vocabulary" in c for c in m["cats"]): s += 1
        # classe gramatical pela forma do lema pt: infinitivo (-ar/-er/-ir) sugere verbo
        first = pt.split(" ")[0]
        verb_like = first.endswith(("ar", "er", "ir", "or", "ôr")) and len(first) >= 2
        if m["type"] == 3: s += 1 if verb_like else -3
        elif verb_like and " " not in pt: s -= 1
        return (s, -pid)

    def map(self, pt, en):
        key = (pt, en)
        if key in self.cache: return self.cache[key]
        ptn, enn = strip_acc(norm(pt)), norm(en)
        enn = SINON_EN.get(enn, enn)
        cands = {p for p in self.en_idx.get(enn, set()) | self.pt_idx.get(ptn, set()) if p in self.meta}
        how = "en" if self.en_idx.get(enn) else "pt"
        if not cands and enn.endswith("s"):
            cands = {p for p in self.en_idx.get(enn[:-1], ()) if p in self.meta}; how = "en-sing"
        best = max(cands, key=lambda p: self.score(p, ptn, enn)) if cands else None
        f0 = ptn.split(" ")[0]
        wrong_pos = best is not None and self.meta[best]["type"] == 3 and not f0.endswith(("ar", "er", "ir", "or", "ôr"))
        if (best is None or wrong_pos) and " " not in ptn:
            extra = {p for p in self.pt_first.get(ptn, ()) if p in self.meta and self.meta[p]["type"] != 3
                     and any(enn in k.lower() for k in self.meta[p]["en"])}
            if extra:
                best = max(extra, key=lambda p: (self.meta[p]["aac"], -p)); how = "pt-composto"
        res = (best, how) if best else (None, "nenhum")
        self.cache[key] = res
        return res

if __name__ == "__main__":
    import sys
    from collections import Counter
    m = Mapper()
    rows = [json.loads(l) for l in open(sys.argv[1])]
    tot, hits, how, miss = 0, 0, Counter(), Counter()
    for r in rows:
        for pt, en in r["pictos"]:
            pid, h = m.map(pt, en); tot += 1; how[h] += 1
            if pid: hits += 1
            else: miss[f"{pt}/{en}"] += 1
    print(f"tokens {tot}  mapeados {hits/tot:.1%}  {dict(how)}")
    print("sem pictograma:", miss.most_common(25))
