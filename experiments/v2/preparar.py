"""Prepara o dataset v2: frases -> sequências de IDs ARASAAC, vocabulário, páginas da prancha e divisões.

Saídas em experiments/v2/out/:
  dataset.json   {vocab, rows, splits}
"""
import json, random, re, pathlib, sys, urllib.parse, time
from collections import Counter, defaultdict
import requests
R = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(R))
from mapear_arasaac import Mapper, norm, strip_acc
from cenarios import CENARIOS

MIN_FREQ = 4
OUT = R / "out"

# Páginas da prancha. Ordem fixa. Cores Fitzgerald por classe gramatical.
PAGINAS = [  # (id, nome, cor)
    ("pessoas", "Pessoas", "pessoa"), ("acoes", "Ações", "acao"), ("sentir", "Sentir", "descricao"),
    ("descrever", "Descrever", "descricao"), ("comida", "Comer e beber", "coisa"), ("brincar", "Brincar", "coisa"),
    ("animais", "Animais", "coisa"), ("corpo", "Corpo e saúde", "coisa"), ("roupa", "Roupa e higiene", "coisa"),
    ("lugares", "Lugares", "lugar"), ("escola", "Escola", "coisa"), ("coisas", "Coisas", "coisa"),
    ("conversa", "Conversa", "social"), ("perguntas", "Perguntas e tempo", "tempo"),
]
NEG = {"não", "nao", "nunca", "nada", "parar", "acabar", "chega", "ninguém"}
PRONOME = {"eu", "você", "ele", "ela", "nós", "eles", "elas", "meu", "minha", "seu", "sua", "nosso", "a gente", "vocês"}
RESPOSTA = {"sim", "ok", "tudo bem", "talvez", "obrigado", "por favor", "oi", "tchau", "desculpa", "bom dia", "boa noite", "boa tarde"}
PERGUNTA = {"o que", "que", "onde", "quando", "quem", "por que", "porque", "como", "qual", "quanto"}
TEMPO_CAT = ("day hours", "time", "calendar", "week", "season", "month")

def _has(text, words):
    return any(re.search(r"\b" + re.escape(w), text) for w in words)

TEMAS = [  # (página, cor, palavras de categoria ARASAAC) na ordem de prioridade
    ("sentir", "descricao", ("feeling", "emotion", "symptom", "sensation", "human response")),
    ("pessoas", "pessoa", ("family", "professional", "person", "people", "pronoun", "relative", "baby")),
    ("comida", "coisa", ("food", "beverage", "gastronomy", "fruit", "vegetable", "feeding", "dessert", "cookery", "baking", "meal", "sweet")),
    ("animais", "coisa", ("animal", "mammal", "bird", "insect", "oviparous", "viviparous", "pet", "fish", "reptile")),
    ("lugares", "lugar", ("transport", "vehicle", "building", "room", "place", "facility", "city", "nature", "landscape",
                          "astronomy", "atmospheric", "meteorolog", "beach", "street")),
    ("corpo", "coisa", ("anatomy", "body", "health", "medical", "medicine", "hospital", "sanitary", "disease", "nursing")),
    ("roupa", "coisa", ("clothes", "footwear", "accessor", "hygiene", "garment")),
    ("escola", "coisa", ("educational", "school", "stationery", "classroom", "letter", "number")),
    ("brincar", "coisa", ("toy", "game", "leisure", "sport", "music", "party", "mass media", "recreation", "art")),
]

def pagina(m, label):
    cats, tags = " ".join(m["cats"]).lower(), " ".join(m["tags"]).lower(); t = m["type"]
    if label in PERGUNTA or _has(cats, TEMPO_CAT): return "perguntas", "tempo"
    if label in NEG: return "conversa", "negacao"
    if label in PRONOME: return "pessoas", "pessoa"
    if label in RESPOSTA: return "conversa", "social"
    if t == 5 or _has(cats, ("expression", "courtesy", "greeting")): return "conversa", "social"
    if t == 6: return "perguntas", "tempo"
    if t == 3: return "acoes", "acao"
    if t == 4:
        return ("sentir", "descricao") if _has(cats + " " + tags, TEMAS[0][2]) else ("descrever", "descricao")
    for text in (cats, tags):
        for pg, cor, words in TEMAS:
            if _has(text, words): return pg, cor
    return "coisas", "coisa"

def api_fallback(misses):
    """Busca na API ARASAAC os pares que o catálogo local não achou (cache em disco)."""
    f = OUT / "api_cache.json"
    cache = json.load(open(f)) if f.exists() else {}
    s = requests.Session()
    for pt, en in misses:
        k = f"{pt}|{en}"
        if k in cache: continue
        pid = None
        for lang, term in (("en", en), ("pt", pt)):
            try:
                r = s.get(f"https://api.arasaac.org/v1/pictograms/{lang}/bestsearch/{urllib.parse.quote(term)}", timeout=15)
                if r.status_code == 200 and r.json(): pid = r.json()[0]["_id"]; break
            except Exception: pass
        cache[k] = pid
    json.dump(cache, open(f, "w"))
    return cache

# formas conjugadas frequentes -> lema
LEMA = {"está": "estar", "estou": "estar", "tá": "estar", "é": "ser", "sou": "ser", "quero": "querer", "quer": "querer",
        "tenho": "ter", "tem": "ter", "gosto": "gostar", "gosta": "gostar", "vou": "ir", "vai": "ir", "posso": "poder",
        "pode": "poder", "dói": "doer", "doeu": "doer", "fiz": "fazer", "fui": "ir", "vi": "ver", "comi": "comer",
        "brinquei": "brincar", "minha": "meu", "sua": "seu", "obrigada": "obrigado"}

def main(src):
    m = Mapper()
    import gzip
    src = pathlib.Path(src)
    if not src.exists(): src = R / "frases.jsonl.gz"  # dataset versionado no repositório
    abrir = gzip.open if str(src).endswith(".gz") else open
    raw = [json.loads(l) for l in abrir(src, "rt")]
    pairs = Counter((pt.strip(), en.strip()) for r in raw for pt, en in r["pictos"])
    misses = [p for p in pairs if m.map(*p)[0] is None and pairs[p] >= 2 and not p[0][:1].isupper()]
    cache = api_fallback(misses)
    def mp(pt, en):
        pid, _ = m.map(pt, en)
        if pid is None: pid = cache.get(f"{pt}|{en}")
        return pid if pid in m.meta else None

    rows, lab = [], defaultdict(Counter)
    for r in raw:
        ids, lost = [], 0
        for pt, en in r["pictos"]:
            pt = pt.strip()
            if pt[:1].isupper() and pt.lower() not in ("eu",): lost += 0; continue  # nome próprio: fora da prancha genérica
            pt = LEMA.get(pt.lower(), pt)
            pid = mp(pt, en.strip())
            if pid is None: lost += 1; continue
            if ids and ids[-1] == pid: continue
            ids.append(pid); lab[pid][strip_acc(norm(pt)) if False else norm(pt)] += 1
        if not ids or lost > len(r["pictos"]) / 3: continue
        rows.append(dict(seq=ids, periodo=r["periodo"], local=r["local"], tipo=r["tipo_adulto"],
                         fonte=r["fonte"], cenario=r.get("cenario"), conversa=r.get("conversa"),
                         adulto=r.get("adulto"), frase=r.get("frase")))
    # um rótulo = um pictograma: junta IDs diferentes com o mesmo rótulo no mais usado
    def clean(l): return l.replace("_", " ").strip()
    freq0 = Counter(i for r in rows for i in r["seq"])
    canon = {}
    for pid in sorted(freq0, key=lambda i: -freq0[i]):
        l = clean(lab[pid].most_common(1)[0][0])
        canon.setdefault(l, pid)
    remap = {pid: canon[clean(lab[pid].most_common(1)[0][0])] for pid in freq0}
    for pid, c in remap.items():
        if pid != c: lab[c].update(lab[pid])
    for r in rows:
        seq = []
        for i in r["seq"]:
            j = remap[i]
            if not seq or seq[-1] != j: seq.append(j)
        r["seq"] = seq
    freq = Counter(i for r in rows for i in r["seq"])
    keep = {i for i, c in freq.items() if c >= MIN_FREQ}
    vocab = []
    for pid in sorted(keep, key=lambda i: -freq[i]):
        label = clean(lab[pid].most_common(1)[0][0])
        pg, cor = pagina(m.meta[pid], label)
        vocab.append(dict(id=pid, label=label, pagina=pg, cor=cor, freq=freq[pid], en=m.meta[pid]["en"][:3]))
    for r in rows: r["seq"] = [i if i in keep else 0 for i in r["seq"]]  # 0 = fora do vocabulário
    rows = [r for r in rows if any(r["seq"])]

    # divisões
    rnd = random.Random(0)
    scen = sorted({c for c, _, _ in CENARIOS}); rnd.shuffle(scen)
    held_scen = set(scen[:6])
    convs = sorted({r["conversa"] for r in rows if r["fonte"] == "cenario" and r["cenario"] not in held_scen}); rnd.shuffle(convs)
    held_conv = set(convs[: len(convs) // 10]); val_conv = set(convs[len(convs) // 10: len(convs) // 10 + len(convs) // 20])
    for r in rows:
        if r["fonte"] == "adaptado": r["split"] = "adaptado"
        elif r["cenario"] in held_scen: r["split"] = "cenario_novo"
        elif r["conversa"] in held_conv: r["split"] = "conversa_nova"
        elif r["conversa"] in val_conv: r["split"] = "val"
        else: r["split"] = "treino"
    tok_total = sum(len(r["pictos"]) for r in raw)
    resumo = dict(frases_brutas=len(raw), frases=len(rows), vocab=len(vocab), held_scen=sorted(held_scen),
                  splits=Counter(r["split"] for r in rows),
                  cobertura_tokens=round(sum(1 for r in rows for i in r["seq"] if i) / tok_total, 3),
                  paginas=Counter(v["pagina"] for v in vocab), api_fallback=sum(1 for v in cache.values() if v))
    json.dump(dict(vocab=vocab, rows=rows, resumo=resumo, paginas=PAGINAS), open(OUT / "dataset.json", "w"), ensure_ascii=False)
    print(json.dumps(resumo, ensure_ascii=False, indent=1, default=str))

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else OUT / "frases_raw.jsonl")
