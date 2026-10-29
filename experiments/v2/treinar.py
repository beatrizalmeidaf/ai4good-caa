"""SLM de símbolos v2: treino, avaliação e exportação para a página.

Entrada: out/dataset.json (preparar.py)
Tokens: [p:periodo] [l:local] [t:tipo_adulto] <s> s1 ... sn </s>
Saídas: out/metricas.json, docs/data/{slm.json,slm.bin,vocab.json,ngram.json}
"""
import json, math, random, sys, time, pathlib
from collections import Counter, defaultdict
import numpy as np, torch, torch.nn as nn, torch.nn.functional as F

R = pathlib.Path(__file__).resolve().parent
OUT = R / "out"; SITE = R.parent.parent / "docs" / "data"
dev = "cuda"
D = json.load(open(OUT / "dataset.json"))
VOCAB = D["vocab"]; ROWS = D["rows"]
IDS = [v["id"] for v in VOCAB]
PAG = {v["id"]: v["pagina"] for v in VOCAB}
PERIODOS = ["manha", "tarde", "noite"]; LOCAIS = ["casa", "escola", "rua", "saude", "terapia"]
TIPOS = sorted({r["tipo"] for r in ROWS})
SPECIAL = ["<s>", "</s>", "<unk>"] + [f"p:{p}" for p in PERIODOS] + [f"l:{l}" for l in LOCAIS] + [f"a:{t}" for t in TIPOS]
TOK = [str(i) for i in IDS] + SPECIAL
T2I = {t: i for i, t in enumerate(TOK)}
NS = len(IDS); EOS = T2I["</s>"]; UNK = T2I["<unk>"]
CORE = set(IDS[:30])  # página Núcleo: os 30 mais frequentes

def ctx(r): return [T2I[f"p:{r['periodo']}"], T2I[f"l:{r['local']}"], T2I[f"a:{r['tipo']}"], T2I["<s>"]]
def enc(r): return ctx(r) + [T2I[str(i)] if i else UNK for i in r["seq"]][:20] + [EOS]

# ---------------- modelo ----------------
class Block(nn.Module):
    def __init__(s, d, h):
        super().__init__(); s.d, s.h = d, h
        s.ln1, s.ln2 = nn.LayerNorm(d), nn.LayerNorm(d)
        s.qkv, s.proj = nn.Linear(d, 3 * d), nn.Linear(d, d)
        s.fc1, s.fc2 = nn.Linear(d, 4 * d), nn.Linear(4 * d, d)
        s.drop = nn.Dropout(0.1)
    def forward(s, x):
        B, T, _ = x.shape
        q, k, v = s.qkv(s.ln1(x)).split(s.d, -1)
        sh = lambda t: t.view(B, T, s.h, s.d // s.h).transpose(1, 2)
        a = F.scaled_dot_product_attention(sh(q), sh(k), sh(v), is_causal=True)
        x = x + s.drop(s.proj(a.transpose(1, 2).reshape(B, T, s.d)))
        return x + s.drop(s.fc2(F.gelu(s.fc1(s.ln2(x)))))

class SLM(nn.Module):
    def __init__(s, d, layers, heads, maxlen=26):
        super().__init__()
        s.cfg = dict(D=d, layers=layers, heads=heads, maxlen=maxlen)
        s.emb = nn.Embedding(len(TOK), d); s.pos = nn.Embedding(maxlen, d)
        nn.init.normal_(s.emb.weight, std=0.02); nn.init.normal_(s.pos.weight, std=0.02)
        s.blocks = nn.ModuleList([Block(d, heads) for _ in range(layers)]); s.lnf = nn.LayerNorm(d)
    def forward(s, x):
        h = s.emb(x) + s.pos(torch.arange(x.shape[1], device=x.device))
        for b in s.blocks: h = b(h)
        return s.lnf(h) @ s.emb.weight.T

def batchify(rows):
    seqs = [enc(r) for r in rows]; L = max(map(len, seqs))
    X = torch.full((len(seqs), L - 1), T2I["<s>"]); Y = torch.full((len(seqs), L - 1), -100)
    for i, s in enumerate(seqs):
        X[i, :len(s) - 1] = torch.tensor(s[:-1])
        y = torch.tensor(s[1:]); y[:3] = -100; y[y == UNK] = -100  # não prevê contexto nem <unk>
        Y[i, :len(s) - 1] = y
    return X.to(dev), Y.to(dev)

def train(rows, d=128, layers=3, heads=4, epochs=30, lr=2e-3, seed=0, val=None, log=True):
    torch.manual_seed(seed); random.seed(seed)
    m = SLM(d, layers, heads).to(dev)
    X, Y = batchify(rows)
    opt = torch.optim.AdamW(m.parameters(), lr=lr, weight_decay=0.05)
    bs = 256; steps = epochs * math.ceil(len(X) / bs)
    sch = torch.optim.lr_scheduler.OneCycleLR(opt, lr, total_steps=steps, pct_start=0.1)
    for ep in range(epochs):
        m.train(); perm = torch.randperm(len(X), device=dev)
        for i in range(0, len(X), bs):
            b = perm[i:i + bs]
            loss = F.cross_entropy(m(X[b]).reshape(-1, len(TOK)), Y[b].reshape(-1), ignore_index=-100)
            opt.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(m.parameters(), 1.0); opt.step(); sch.step()
        if log and val is not None and (ep + 1) % 10 == 0:
            print(f"   época {ep+1}: val top6={evaluate_slm(m, val)["top6"]}", flush=True)
    return m.eval()

# ---------------- avaliação ----------------
def positions(rows):
    """(row, i): prever seq[i] a partir de seq[:i]; i == len(seq) é o fim da frase."""
    return [(r, i) for r in rows for i in range(len(r["seq"]) + 1) if i == len(r["seq"]) or r["seq"][i]]

def slm_logprobs(m, rows):
    """log-probs sobre [símbolos..., </s>] para cada posição."""
    out = []
    with torch.no_grad():
        for r in rows:
            s = enc(r)
            lp = m(torch.tensor([s[:-1]], device=dev))[0].log_softmax(-1)
            for i in range(len(r["seq"]) + 1):
                if i < len(r["seq"]) and not r["seq"][i]: continue
                v = lp[3 + i]  # posição do token anterior ao alvo
                out.append(torch.cat([v[:NS], v[EOS:EOS + 1]]).cpu().numpy())
    return np.array(out)

class NGram:
    L = dict(ctxb=0.3, tri=0.3, bi=0.2, ctx=0.1, uni=0.1)
    def __init__(s, rows):
        s.c = {k: defaultdict(Counter) for k in s.L}
        for r in rows:
            cx = f"{r['periodo']}|{r['local']}|{r['tipo']}"
            seq = ["<s>", "<s>"] + [str(i) for i in r["seq"]] + ["</s>"]
            for i in range(2, len(seq)):
                a, b, w = seq[i - 2], seq[i - 1], seq[i]
                if w == "0": continue
                for k, key in (("ctxb", f"{cx}|{b}"), ("tri", f"{a}|{b}"), ("bi", b), ("ctx", cx), ("uni", "")):
                    s.c[k][key][w] += 1
    def logprobs(s, rows):
        keys = [str(i) for i in IDS] + ["</s>"]; out = []
        for r, i in positions(rows):
            cx = f"{r['periodo']}|{r['local']}|{r['tipo']}"
            seq = ["<s>", "<s>"] + [str(x) for x in r["seq"][:i]]
            a, b = seq[-2], seq[-1]
            p = np.full(len(keys), 1e-7)
            for k, key in (("ctxb", f"{cx}|{b}"), ("tri", f"{a}|{b}"), ("bi", b), ("ctx", cx), ("uni", "")):
                d = s.c[k].get(key)
                if d:
                    tot = sum(d.values())
                    p += s.L[k] * np.array([d.get(w, 0) for w in keys]) / tot
            out.append(np.log(p))
        return np.array(out)

def metrics(lp, rows):
    pos = positions(rows)
    gold = np.array([IDS.index(r["seq"][i]) if i < len(r["seq"]) else NS for r, i in pos])
    rank = (lp > lp[np.arange(len(gold)), gold][:, None]).sum(1)
    sym = gold < NS; end = ~sym
    # conceito: página da prancha mais provável (soma das probabilidades por página)
    pages = sorted(set(PAG.values())); pidx = np.array([pages.index(PAG[i]) for i in IDS])
    pr = np.exp(lp[:, :NS]); pm = np.zeros((len(lp), len(pages)))
    for j in range(len(pages)): pm[:, j] = pr[:, pidx == j].sum(1)
    gold_pg = pidx[gold[sym]]
    pg_rank = (pm[sym] > pm[sym][np.arange(sym.sum()), gold_pg][:, None]).sum(1)
    # toques: sem barra, Núcleo = 1 toque, outras páginas = 2; com barra = 1 se está nas 5 sugestões
    core = np.array([IDS[g] in CORE for g in gold[sym]])
    sem = np.where(core, 1, 2); com = np.where(rank[sym] < 6, 1, sem)
    return dict(top1=round(float((rank[sym] < 1).mean()) * 100, 1), top6=round(float((rank[sym] < 6).mean()) * 100, 1),
                mrr=round(float((1 / (rank[sym] + 1)).mean()), 3),
                fim_top6=round(float((rank[end] < 6).mean()) * 100, 1),
                conceito_top1=round(float((pg_rank < 1).mean()) * 100, 1), conceito_top3=round(float((pg_rank < 3).mean()) * 100, 1),
                economia_toques=round(float(1 - com.sum() / sem.sum()) * 100, 1), n=int(sym.sum()))

def evaluate_slm(m, rows): return metrics(slm_logprobs(m, rows), rows)

def unigram_lp(train_rows, rows):
    c = Counter(str(i) for r in train_rows for i in r["seq"] if i); c["</s>"] = len(train_rows)
    v = np.log(np.array([c[str(i)] + 0.1 for i in IDS] + [c["</s>"]]) / (sum(c.values()) + 1))
    return np.tile(v, (len(positions(rows)), 1))

# ---------------- exportação ----------------
def export(m, ngram_rows):
    SITE.mkdir(parents=True, exist_ok=True)
    m = m.cpu()
    sd = {k: v.numpy().astype(np.float16) for k, v in m.state_dict().items()}
    manifest, off = {}, 0
    for k, v in sd.items():
        manifest[k] = dict(shape=list(v.shape), offset=off); off += v.size
    np.concatenate([v.ravel() for v in sd.values()]).astype("<f2").tofile(SITE / "slm.bin")
    cfg = dict(m.cfg, tokens=TOK, n_symbols=NS, dtype="float16", params=sum(p.numel() for p in m.parameters()))
    r0 = dict(periodo="manha", local="casa", tipo="o_que_quer", seq=[5441])  # "querer"
    x = torch.tensor([ctx(r0) + [T2I["5441"]]])
    with torch.no_grad():
        mh = SLM(m.cfg["D"], m.cfg["layers"], m.cfg["heads"], m.cfg["maxlen"])
        mh.load_state_dict({k: torch.tensor(v.astype(np.float32)) for k, v in sd.items()}); mh.eval()
        ref = mh(x)[0, -1].log_softmax(-1).numpy()
    cfg["teste"] = dict(input=x[0].tolist(), logprobs=[float(v) for v in ref])
    json.dump(dict(config=cfg, tensors=manifest), open(SITE / "slm.json", "w"))
    json.dump([dict(id=v["id"], label=v["label"], pagina=v["pagina"], cor=v["cor"], freq=v["freq"]) for v in VOCAB],
              open(SITE / "vocab.json", "w"), ensure_ascii=False)
    print("exportado:", cfg["params"], "parâmetros,", (SITE / "slm.bin").stat().st_size // 1024, "KB")

if __name__ == "__main__":
    split = defaultdict(list)
    for r in ROWS: split[r["split"]].append(r)
    rnd = random.Random(0); ad = split["adaptado"][:]; rnd.shuffle(ad)
    ad_tr, ad_te = ad[: len(ad) // 2], ad[len(ad) // 2:]
    tests = {"conversa_nova": split["conversa_nova"], "cenario_novo": split["cenario_novo"], "mensagem_real": ad_te,
             "conversa_nova2": split["conversa_nova2"], "cenario_novo2": split["cenario_novo2"], "crianca_real": split["crianca_real"]}
    tests = {k: v for k, v in tests.items() if v}
    print({k: len(v) for k, v in split.items()}, "vocab", NS, flush=True)
    res = defaultdict(dict)
    tr = split["treino"]
    tr_leva1 = tr + ad_tr                      # só a primeira leva (como o modelo anterior)
    tr_mix = tr + split["treino2"] + split["treino3"] + ad_tr     # sintético (2 levas) + fala real de criança (CHILDES)
    tr_sem_childes = tr + split["treino2"] + ad_tr
    ng = NGram(tr_mix)
    for t, rows in tests.items():
        res[t]["Mais usados (frequência)"] = metrics(unigram_lp(tr_mix, rows), rows)
        res[t]["N-grama + contexto"] = metrics(ng.logprobs(rows), rows)
    configs = {"SLM P (d64, 2 camadas)": (64, 2, 4), "SLM M (d128, 3 camadas)": (128, 3, 4), "SLM G (d192, 4 camadas)": (192, 4, 6)}
    best, best_name, best_score = None, None, -1
    for name, (d, l, h) in configs.items():
        t0 = time.time(); print(name, flush=True)
        m = train(tr_mix, d, l, h, val=split["val"])
        v = evaluate_slm(m, split["val"])
        for t, rows in tests.items(): res[t][name] = evaluate_slm(m, rows)
        res["_tempo_treino_s"][name] = round(time.time() - t0, 1)
        if v["top6"] + 10 * v["mrr"] > best_score: best, best_name, best_score = (d, l, h), name, v["top6"] + 10 * v["mrr"]
    # efeito da segunda leva: mesmo tamanho, treinado só com a primeira leva, nos mesmos testes
    m1 = train(tr_leva1, *best, log=False)
    for t, rows in tests.items(): res[t][best_name + " só 1ª leva"] = evaluate_slm(m1, rows)
    # efeito da fala real de criança no treino
    if split["treino3"]:
        m_sc = train(tr_sem_childes, *best, log=False)
        for t, rows in tests.items(): res[t][best_name + " sem fala real de criança"] = evaluate_slm(m_sc, rows)
    # comitê: média de 3 treinos com sementes diferentes
    comite = [m] if False else []
    lps = {t: [] for t in tests}; lps_val = []
    for sd in (0, 1, 2):
        mm = train(tr_mix, *best, seed=sd, log=False); comite.append(mm)
        for t, rows in tests.items(): lps[t].append(np.exp(slm_logprobs(mm, rows)))
        lps_val.append(np.exp(slm_logprobs(mm, split["val"])))
    for t, rows in tests.items(): res[t][best_name + " comitê de 3"] = metrics(np.log(np.mean(lps[t], 0)), rows)
    # mistura com n-grama (peso escolhido na validação)
    ng_all = NGram(tr_mix); pv = np.mean(lps_val, 0); ngv = np.exp(ng_all.logprobs(split["val"]))
    alfa = max([0.0, 0.1, 0.2, 0.3], key=lambda a: (lambda r: r["top6"] + 10 * r["mrr"])(metrics(np.log((1 - a) * pv + a * ngv), split["val"])))
    res["_alfa_ngrama"] = alfa
    for t, rows in tests.items(): res[t][best_name + f" comitê + n-grama ({alfa})"] = metrics(np.log((1 - alfa) * np.mean(lps[t], 0) + alfa * np.exp(ng_all.logprobs(rows))), rows)
    # rebaixar palavras de ligação (com, no, de...) nas sugestões
    LIG = {"com", "no", "na", "nos", "nas", "para", "pra", "de", "do", "da", "e", "mas", "ou", "se", "até", "sem", "em", "ao", "que", "tão", "embora"}
    peso = np.array([0.5 if v["label"] in LIG else 1.0 for v in VOCAB] + [1.0])
    for t, rows in tests.items(): res[t][best_name + " comitê, ligação rebaixada"] = metrics(np.log(np.mean(lps[t], 0) * peso), rows)
    # efeito das mensagens reais no treino (mesmo tamanho do melhor)
    m_sem = train(tr + split["treino2"], *best, log=False)
    if ad_te: res["mensagem_real"][best_name + " sem mensagens reais no treino"] = evaluate_slm(m_sem, ad_te)
    res["_melhor"] = best_name
    json.dump(res, open(OUT / "metricas.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for t in tests:
        print(f"\n== {t} ==")
        for k, v in sorted(res[t].items(), key=lambda kv: -kv[1]["top6"]):
            print(f"{k:55s} top1={v['top1']:5.1f} top6={v["top6"]:5.1f} mrr={v["mrr"]:.3f} fim6={v["fim_top6"]:5.1f} conc1={v['conceito_top1']:5.1f} toques-={v['economia_toques']:5.1f}%")
    # modelo final: todas as frases (menos o teste de mensagens reais fica de fora? não: o modelo da página usa tudo)
    finais = [train([r for r in ROWS if r["split"] != "fora"], *best, seed=sd, log=False) for sd in (0, 1, 2)]
    export(finais[0], ROWS)
    for k, mm in enumerate(finais[1:], 1):   # membros extras do comitê: slm_1.bin, slm_2.bin (mesmo slm.json)
        sd = {kk: v.cpu().numpy().astype(np.float16) for kk, v in mm.cpu().state_dict().items()}
        np.concatenate([v.ravel() for v in sd.values()]).astype("<f2").tofile(SITE / f"slm_{k}.bin")
    # n-grama de reserva para a página
    ngf = NGram(ROWS)
    json.dump(dict(lambdas=NGram.L, counts={k: {kk: dict(v) for kk, v in d.items()} for k, d in ngf.c.items()}),
              open(SITE / "ngram.json", "w"))
