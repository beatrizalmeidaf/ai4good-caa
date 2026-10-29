"""SLM de símbolos v3: fala do adulto como contexto, pré-treino, destilação, e métrica de toques da prancha de verdade.

Entrada: out/dataset.json (preparar.py), out/professor.jsonl (qwen_dados.py professor, opcional)
Tokens: [p:periodo] [l:local] [a:tipo] <a> adulto1..adulto10 <s> s1 ... sn </s>
  adulto* = pictogramas do que o adulto disse (texto_pictos.py; no site: core.js textoParaPictos)
Saídas: out/metricas3.json, e com --exportar docs/data/{slm.json, slm.bin, slm_1.bin, slm_2.bin}

Experimentos (cada um soma ao anterior; comitê de 3 sementes):
  E0 v2 (o que está no site)            E1 + fala do adulto        E2 + CHILDES revisado
  E3 + pré-treino (legendas, CHILDES PT) E4 + destilação do Qwen    E5 + destilação de um modelo grande
"""
import json, math, random, sys, time, pathlib
from collections import Counter, defaultdict
import numpy as np, torch, torch.nn as nn, torch.nn.functional as F

R = pathlib.Path(__file__).resolve().parent
OUT = R / "out"; SITE = R.parent.parent / "docs" / "data"
dev = "cuda"
D = json.load(open(OUT / "dataset.json", encoding="utf-8"))
VOCAB = D["vocab"]; ROWS = D["rows"]
IDS = [v["id"] for v in VOCAB]; IX = {i: k for k, i in enumerate(IDS)}
LABEL = {v["id"]: v["label"] for v in VOCAB}
PERIODOS = ["manha", "tarde", "noite"]; LOCAIS = ["casa", "escola", "rua", "saude", "terapia"]
TIPOS = sorted({r["tipo"] for r in ROWS} | {"desconhecido"})  # desconhecido: o adulto falou pelo microfone, sem escolher o tipo
SPECIAL = ["<s>", "</s>", "<unk>"] + [f"p:{p}" for p in PERIODOS] + [f"l:{l}" for l in LOCAIS] + [f"a:{t}" for t in TIPOS] + ["<a>"]
TOK = [str(i) for i in IDS] + SPECIAL
T2I = {t: i for i, t in enumerate(TOK)}
NS = len(IDS); EOS = T2I["</s>"]; UNK = T2I["<unk>"]
MAXA, MAXS = 10, 20
MAXLEN = 4 + MAXA + 1 + MAXS + 1

def ctx(r, adulto):
    a = [T2I[str(i)] for i in r.get("adp", [])[:MAXA] if str(i) in T2I] if adulto else []
    return [T2I[f"p:{r['periodo']}"], T2I[f"l:{r['local']}"], T2I[f"a:{r['tipo']}"], T2I["<a>"]] + a + [T2I["<s>"]]
def enc(r, adulto):
    c = ctx(r, adulto)
    return c, c + [T2I[str(i)] if i else UNK for i in r["seq"]][:MAXS] + [EOS]

# ---------------- modelo (igual ao v2; docs/js/slm.js roda a mesma conta) ----------------
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
    def __init__(s, d, layers, heads, maxlen=MAXLEN):
        super().__init__()
        s.cfg = dict(D=d, layers=layers, heads=heads, maxlen=maxlen)
        s.emb = nn.Embedding(len(TOK), d); s.pos = nn.Embedding(maxlen, d)
        nn.init.normal_(s.emb.weight, std=0.02); nn.init.normal_(s.pos.weight, std=0.02)
        s.blocks = nn.ModuleList([Block(d, heads) for _ in range(layers)]); s.lnf = nn.LayerNorm(d)
    def forward(s, x):
        h = s.emb(x) + s.pos(torch.arange(x.shape[1], device=x.device))
        for b in s.blocks: h = b(h)
        return s.lnf(h) @ s.emb.weight.T

# ---------------- professor (Qwen): rótulos suaves ----------------
PROF = {}
if (OUT / "professor.jsonl").exists():
    for l in open(OUT / "professor.jsonl", encoding="utf-8"):
        x = json.loads(l)
        dist = np.zeros(len(TOK), np.float32)
        for k, p in enumerate(x["proximos"][:8]):
            j = EOS if p == "FIM" else T2I.get(str(p))
            if j is not None: dist[j] += 1 / (k + 1)
        if dist.sum(): PROF[(x["adulto"], tuple(x["prefixo"]))] = dist / dist.sum()

def batchify(rows, adulto, prof=False):
    encs = [enc(r, adulto) for r in rows]; L = max(len(s) for _, s in encs)
    X = torch.full((len(rows), L - 1), T2I["<s>"]); Y = torch.full((len(rows), L - 1), -100)
    SI = torch.full((len(rows), L - 1), -1); Q = []
    for b, ((c, s), r) in enumerate(zip(encs, rows)):
        X[b, :len(s) - 1] = torch.tensor(s[:-1])
        y = torch.tensor(s[1:]); y[:len(c) - 1] = -100; y[y == UNK] = -100
        Y[b, :len(s) - 1] = y
        if prof:
            for i in range(min(len(r["seq"]), MAXS) + 1):
                d = PROF.get((r.get("adulto") or "", tuple(r["seq"][:i])))
                if d is not None and Y[b, len(c) - 1 + i] != -100: SI[b, len(c) - 1 + i] = len(Q); Q.append(d)
    Qt = torch.tensor(np.array(Q)) if Q else torch.zeros((1, len(TOK)))
    return X.to(dev), Y.to(dev), SI.to(dev), Qt.to(dev)

def train(rows, d=64, layers=2, heads=4, epochs=30, lr=2e-3, seed=0, adulto=True, prof=0.0, mestre=None, kd=0.0, init=None):
    """prof: peso dos rótulos do Qwen; mestre/kd: modelo grande e peso da destilação; init: começa de um modelo pré-treinado"""
    torch.manual_seed(seed); random.seed(seed)
    m = SLM(d, layers, heads).to(dev)
    if init is not None: m.load_state_dict(init.state_dict())
    if adulto:  # 30% das frases sem o tipo da fala: o modelo aprende a usar só as palavras do adulto (modo microfone)
        rr = random.Random(seed + 100)
        rows = [dict(r, tipo="desconhecido") if r.get("adp") and rr.random() < 0.3 else r for r in rows]
    X, Y, SI, Q = batchify(rows, adulto, prof > 0)
    opt = torch.optim.AdamW(m.parameters(), lr=lr, weight_decay=0.05)
    bs = 256; steps = epochs * math.ceil(len(X) / bs)
    sch = torch.optim.lr_scheduler.OneCycleLR(opt, lr, total_steps=steps, pct_start=0.1)
    if mestre is not None: mestre.eval()
    for ep in range(epochs):
        m.train(); perm = torch.randperm(len(X), device=dev)
        for i in range(0, len(X), bs):
            b = perm[i:i + bs]; y = Y[b].reshape(-1); ok = y != -100
            lp = m(X[b]).reshape(-1, len(TOK)).log_softmax(-1)[ok]; y = y[ok]
            nll = -lp.gather(1, y[:, None])[:, 0]
            loss = nll
            if prof > 0:
                si = SI[b].reshape(-1)[ok]; tem = si >= 0
                if tem.any():
                    soft = -(Q[si[tem]] * lp[tem]).sum(-1)
                    loss = loss.clone(); loss[tem] = (1 - prof) * nll[tem] + prof * soft
            if mestre is not None and kd > 0:
                with torch.no_grad(): pt = mestre(X[b]).reshape(-1, len(TOK))[ok].softmax(-1)
                loss = (1 - kd) * loss + kd * -(pt * lp).sum(-1)
            loss = loss.mean()
            opt.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(m.parameters(), 1.0); opt.step(); sch.step()
    return m.eval()

# ---------------- avaliação ----------------
def positions(rows):
    """(row, i): prever seq[i] a partir de seq[:i]; i == len(seq) é o fim da frase."""
    return [(r, i) for r in rows for i in range(len(r["seq"]) + 1) if i == len(r["seq"]) or r["seq"][i]]

def slm_probs(m, rows, adulto):
    out = []
    with torch.no_grad():
        for k in range(0, len(rows), 512):
            lote = rows[k:k + 512]
            X, _, _, _ = batchify(lote, adulto)
            P = m(X).softmax(-1).cpu().numpy()
            for b, r in enumerate(lote):
                c, _ = enc(r, adulto)
                for i in range(len(r["seq"]) + 1):
                    if i < len(r["seq"]) and not r["seq"][i]: continue
                    v = P[b, len(c) - 1 + min(i, MAXS)]
                    out.append(np.concatenate([v[:NS], v[EOS:EOS + 1]]))
    return np.array(out)

# páginas da prancha do site (igual a core.js montarPaginas; grade 5x3 = 15 por tela)
GRUPO = dict(pessoas="pessoas", acoes="acoes", sentir="sentir", descrever="sentir", comida="comida", brincar="brincar", animais="brincar",
             corpo="corpo", roupa="corpo", lugares="lugares", escola="lugares", coisas="lugares", conversa="conversa", perguntas="conversa")
def paginas():
    ordem = ["pessoa", "acao", "descricao", "social", "negacao", "tempo", "coisa", "lugar"]
    pg = {"nucleo": [w["id"] for w in sorted(VOCAB[:30], key=lambda w: (ordem.index(w["cor"]) if w["cor"] in ordem else 99, -w["freq"]))]}
    for w in VOCAB: pg.setdefault(GRUPO.get(w["pagina"], "lugares"), []).append(w["id"])
    return pg
PG = paginas(); N_TELA = 15
LOC = defaultdict(list)
for p, ids in PG.items():
    for k, i in enumerate(ids): LOC[i].append((p, k // N_TELA))
def tela(estado): p, s = estado; return set(PG[p][s * N_TELA:(s + 1) * N_TELA])
def navegar(estado, w):
    """toques para chegar em w andando pela prancha (aba + setas + toque) e onde a criança fica"""
    p0, s0 = estado; melhor = None
    for p, s in LOC[w]:
        c = 1 + (abs(s - s0) if p == p0 else 1 + s)
        if p == p0: c = min(c, 1 + 1 + s)
        if melhor is None or c < melhor[0]: melhor = (c, (p, s))
    return melhor

PALAVRA_FUNCAO = {"com", "no", "na", "para", "pra", "de", "do", "da", "e", "mas", "ou", "se", "em", "ao", "que", "o", "a", "meu", "seu"}
def conteudo(label): return {w for w in label.split() if len(w) >= 3 and w not in PALAVRA_FUNCAO}
def parecido(a, b):
    """'água' e 'beber água' ajudam do mesmo jeito; 'querer' e 'não querer' não"""
    if a == b: return True
    la, lb = LABEL.get(a, ""), LABEL.get(b, "")
    if ("não" in la.split()) != ("não" in lb.split()): return False
    return bool(conteudo(la) & conteudo(lb))

def metrics(P, rows, politica="atual"):
    """P: probabilidades [posições, NS+1] (último = fim da frase).
    top1/top6/mrr: acerto exato; top6_flex: conta sugestão de mesmo sentido ('água' para 'beber água');
    toques: simulação da prancha do site (grade 5x3, abas, setas, Zuli sempre visível), sem e com a faixa de 6 sugestões.
    politica: 'atual' (como o site), 'tela' (tira da faixa o que já está na tela), 'tela_sem_fim' (e não ocupa espaço com o fim)."""
    pos = positions(rows)
    gold = np.array([IX[r["seq"][i]] if i < len(r["seq"]) else NS for r, i in pos])
    pg = P[np.arange(len(gold)), gold]
    rank = (P > pg[:, None]).sum(1)
    sym = gold < NS; end = ~sym
    ordem = np.argsort(-P, 1)[:, :40]
    flex = []
    for k in np.where(sym)[0]:
        g = IDS[gold[k]]; top = [IDS[j] for j in ordem[k] if j < NS][:6]
        flex.append(any(parecido(g, t) for t in top))
    # simulação de toques
    sem = com = 0; k = 0; uteis = 0; n_pal = 0
    for r in rows:
        e_sem = e_com = ("nucleo", 0); prefix = []
        for i in range(len(r["seq"]) + 1):
            if i < len(r["seq"]) and not r["seq"][i]: continue
            alvo = r["seq"][i] if i < len(r["seq"]) else None
            if alvo is None: sem += 1; com += 1; k += 1; continue   # Zuli (falar) sempre visível
            n_pal += 1
            c, e_sem = (1, e_sem) if alvo in tela(e_sem) else navegar(e_sem, alvo); sem += c
            vis = tela(e_com); barra = []
            for j in ordem[k]:
                if j == NS:
                    if not prefix or politica == "tela_sem_fim": continue
                    barra.append("FIM")
                else:
                    w = IDS[j]
                    if prefix and w == prefix[-1]: continue
                    if politica != "atual" and w in vis: continue
                    barra.append(w)
                if len(barra) == 6: break
            if alvo in barra:
                com += 1
                if alvo not in vis: uteis += 1
            else:
                c, e_com = (1, e_com) if alvo in vis else navegar(e_com, alvo); com += c
            prefix.append(alvo); k += 1
    return dict(top1=round(float((rank[sym] < 1).mean()) * 100, 1), top6=round(float((rank[sym] < 6).mean()) * 100, 1),
                top6_flex=round(float(np.mean(flex)) * 100, 1), mrr=round(float((1 / (rank[sym] + 1)).mean()), 3),
                fim_top6=round(float((rank[end] < 6).mean()) * 100, 1),
                toques_sem=round(sem / len(rows), 2), toques_com=round(com / len(rows), 2),
                economia_toques=round((1 - com / sem) * 100, 1), sugestao_util=round(uteis / max(1, n_pal) * 100, 1), n=int(sym.sum()))

def comite(modelos, rows, adulto): return np.mean([slm_probs(m, rows, adulto) for m in modelos], 0)

# ---------------- exportação ----------------
def exportar(modelos):
    SITE.mkdir(parents=True, exist_ok=True)
    m = modelos[0].cpu()
    sd = {k: v.numpy().astype(np.float16) for k, v in m.state_dict().items()}
    manifest, off = {}, 0
    for k, v in sd.items(): manifest[k] = dict(shape=list(v.shape), offset=off); off += v.size
    np.concatenate([v.ravel() for v in sd.values()]).astype("<f2").tofile(SITE / "slm.bin")
    cfg = dict(m.cfg, tokens=TOK, n_symbols=NS, dtype="float16", params=sum(p.numel() for p in m.parameters()), max_adulto=MAXA)
    r0 = dict(periodo="manha", local="casa", tipo="o_que_quer", seq=[], adp=[IDS[0], IDS[1]])
    c, _ = enc(r0, True); x = torch.tensor([c])
    with torch.no_grad():
        mh = SLM(m.cfg["D"], m.cfg["layers"], m.cfg["heads"], m.cfg["maxlen"])
        mh.load_state_dict({k: torch.tensor(v.astype(np.float32)) for k, v in sd.items()}); mh.eval()
        ref = mh(x)[0, -1].log_softmax(-1).numpy()
    cfg["teste"] = dict(input=x[0].tolist(), logprobs=[float(v) for v in ref])
    json.dump(dict(config=cfg, tensors=manifest), open(SITE / "slm.json", "w"))
    for k, mm in enumerate(modelos[1:], 1):
        sdk = {kk: v.cpu().numpy().astype(np.float16) for kk, v in mm.cpu().state_dict().items()}
        np.concatenate([v.ravel() for v in sdk.values()]).astype("<f2").tofile(SITE / f"slm_{k}.bin")
    print("exportado:", cfg["params"], "parâmetros,", (SITE / "slm.bin").stat().st_size // 1024, "KB cada", flush=True)

if __name__ == "__main__":
    EXPORTAR = "--exportar" in sys.argv
    split = defaultdict(list)
    for r in ROWS: split[r["split"]].append(r)
    rnd = random.Random(0); ad = split["adaptado"][:]; rnd.shuffle(ad)
    ad_tr, ad_te = ad[: len(ad) // 2], ad[len(ad) // 2:]
    real_tr = split["treino3r"] or split["treino3"]; teste_real = split["crianca_real"] or split["crianca_real_v1"]
    # validação de conversa real: 10% das conversas de treino do CHILDES (para escolher, sem olhar os testes)
    cv = sorted({r["conversa"] for r in real_tr}); random.Random(5).shuffle(cv); cv = set(cv[: len(cv) // 10])
    val_real = [r for r in real_tr if r["conversa"] in cv]
    sem_val = lambda rows: [r for r in rows if r["conversa"] not in cv]
    tests = {"conversa_nova": split["conversa_nova"], "cenario_novo": split["cenario_novo"], "mensagem_real": ad_te,
             "conversa_nova2": split["conversa_nova2"], "cenario_novo2": split["cenario_novo2"],
             "crianca_real": teste_real, "crianca_real_v1": split["crianca_real_v1"] if split["crianca_real"] else []}
    tests = {k: v for k, v in tests.items() if v}
    vals = {"val": split["val"], "val_real": val_real}
    print({k: len(v) for k, v in split.items()}, "val_real", len(val_real), "vocab", NS, "professor", len(PROF), flush=True)
    base = split["treino"] + split["treino2"] + ad_tr
    tr_v1 = base + sem_val(split["treino3"])
    tr_rev = base + sem_val(real_tr)
    pre = split["pre"]
    res = defaultdict(dict); nota = {}; t0 = time.time()

    def avaliar(nome, modelos, adulto, politicas=("atual",), microfone=False):
        for t, rows in tests.items():
            P = comite(modelos, rows, adulto)
            for pol in politicas:
                res[t][nome + {"atual": "", "tela": " · faixa sem o que já está na tela", "tela_sem_fim": " · faixa sem o que está na tela e sem 'falar'"}[pol]] = metrics(P, rows, pol)
            if microfone:  # só as palavras do adulto, sem o tipo da fala
                rm = [dict(r, tipo="desconhecido") if r.get("adp") else r for r in rows]
                res[t][nome + " · modo microfone (sem tipo da fala)"] = metrics(comite(modelos, rm, adulto), rm)
        # nota de escolha: só validação (sintética + conversa real)
        nota[nome] = float(np.mean([metrics(comite(modelos, v, adulto), v)["top6"] for v in vals.values()]))
        r = res["crianca_real"][nome]; c = res["conversa_nova"][nome]
        print(f"{nome:45s} val={nota[nome]:.1f} | real: top6={r['top6']} flex={r['top6_flex']} toques-={r['economia_toques']}% | conversa_nova: top6={c['top6']} toques-={c['economia_toques']}%  ({time.time() - t0:.0f}s)", flush=True)

    S = (0, 1, 2)
    E0 = [train(tr_v1, seed=s, adulto=False) for s in S]; avaliar("E0 v2 (site atual)", E0, False)
    E1 = [train(tr_v1, seed=s) for s in S]; avaliar("E1 + fala do adulto", E1, True)
    cam = dict(tr=tr_v1, init=lambda s: None, prof=0.0, mestre_pre=None, modelos=E1, nome="E1 + fala do adulto")
    if split["treino3r"]:
        E2 = [train(tr_rev, seed=s) for s in S]; avaliar("E2 + CHILDES revisado", E2, True)
        if nota["E2 + CHILDES revisado"] >= nota[cam["nome"]]: cam.update(tr=tr_rev, modelos=E2, nome="E2 + CHILDES revisado")
    if pre:
        pre_ms = {s: train(pre, seed=s, epochs=8) for s in S}
        E3 = [train(cam["tr"], seed=s, init=pre_ms[s]) for s in S]; avaliar("E3 + pré-treino (legendas, CHILDES PT)", E3, True)
        if nota["E3 + pré-treino (legendas, CHILDES PT)"] > nota[cam["nome"]]:
            cam.update(init=lambda s: pre_ms[s], modelos=E3, nome="E3 + pré-treino (legendas, CHILDES PT)", mestre_pre=True)
    if PROF:
        E4 = [train(cam["tr"], seed=s, init=cam["init"](s), prof=0.5) for s in S]; avaliar("E4 + destilação do Qwen", E4, True)
        if nota["E4 + destilação do Qwen"] > nota[cam["nome"]]: cam.update(prof=0.5, modelos=E4, nome="E4 + destilação do Qwen")
    # modelo grande (d256, 4 camadas) como professor do pequeno
    mp = train(pre, d=256, layers=4, heads=8, epochs=8, seed=7) if cam["mestre_pre"] else None
    mestre = train(cam["tr"], d=256, layers=4, heads=8, seed=7, init=mp, prof=cam["prof"])
    avaliar("modelo grande (d256, 4 camadas)", [mestre], True)
    E5 = [train(cam["tr"], seed=s, init=cam["init"](s), prof=cam["prof"], mestre=mestre, kd=0.5) for s in S]
    avaliar("E5 + destilação de um modelo grande", E5, True)
    kd = 0.0
    if nota["E5 + destilação de um modelo grande"] > nota[cam["nome"]]: cam.update(modelos=E5, nome="E5 + destilação de um modelo grande"); kd = 0.5
    res["_final"] = cam["nome"]; res["_nota_validacao"] = nota
    avaliar("FINAL " + cam["nome"], cam["modelos"], True, ("atual", "tela", "tela_sem_fim"), microfone=True)
    json.dump(res, open(OUT / "metricas3.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for t in tests:
        print(f"\n== {t} ==")
        for k, v in res[t].items():
            print(f"{k:90s} top6={v['top6']:5.1f} flex={v['top6_flex']:5.1f} top1={v['top1']:5.1f} fim6={v['fim_top6']:5.1f} toques {v['toques_sem']:.2f}→{v['toques_com']:.2f} (-{v['economia_toques']:4.1f}%) útil={v['sugestao_util']:4.1f}", flush=True)
    if EXPORTAR:
        # modelo do site: o melhor caminho, treinado com todas as frases (testes incluídos, como no v2)
        real = "treino3r" if cam["tr"] is tr_rev else "treino3"; teste = "crianca_real" if real == "treino3r" else "crianca_real_v1"
        todos = [r for r in ROWS if r["split"] in ("treino", "treino2", "adaptado", "val", "conversa_nova", "cenario_novo",
                                                   "conversa_nova2", "cenario_novo2", real, teste)]
        mf = train(todos, d=256, layers=4, heads=8, seed=7, init=mp, prof=cam["prof"]) if kd else None
        finais = [train(todos, seed=s, init=cam["init"](s), prof=cam["prof"], mestre=mf, kd=kd) for s in S]
        exportar(finais)
    print("FIM", flush=True)
