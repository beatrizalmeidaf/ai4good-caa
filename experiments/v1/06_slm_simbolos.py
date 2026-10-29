"""Experimento 4: SLM de símbolos (transformer minúsculo sobre pictogramas).

Tokens: [periodo] [local] <s> s1 s2 ... </s>. Prevê o próximo símbolo, inclusive </s>
(o fim da frase vira sugestão de "terminei").
Embeddings dos símbolos iniciados com multilingual-e5 (rótulo pt-BR) reduzido por PCA,
para que símbolos de sentido parecido compartilhem conhecimento.
Exporta pesos em JSON para rodar em JS puro na página.
"""
import json, sys, pathlib, time, math, importlib
import numpy as np, torch, torch.nn as nn, torch.nn.functional as F
R = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "experiments"))
from vocab import VOCAB
ev = importlib.import_module("03_avaliacao")

IDS = [v[0] for v in VOCAB]
SPECIAL = ["<s>", "</s>", "p:manha", "p:tarde", "p:noite", "l:casa", "l:escola"]
TOK = IDS + SPECIAL
T2I = {t: i for i, t in enumerate(TOK)}
EOS = T2I["</s>"]
D, LAYERS, HEADS, MAXLEN = 96, 2, 4, 16
dev = "cuda"

def encode(r):
    return [T2I["p:" + r["periodo"]], T2I["l:" + r["local"]], T2I["<s>"]] + [T2I[s] for s in r["seq"]] + [EOS]

def e5_init():
    cache = R / "experiments" / "cache"; cache.mkdir(exist_ok=True)
    f = cache / "e5_labels.npy"
    if not f.exists():
        from transformers import AutoTokenizer, AutoModel
        tok = AutoTokenizer.from_pretrained("intfloat/multilingual-e5-large")
        m = AutoModel.from_pretrained("intfloat/multilingual-e5-large").to(dev).eval()
        texts = [f"query: {v[1]}" for v in VOCAB]
        b = tok(texts, padding=True, return_tensors="pt").to(dev)
        with torch.no_grad():
            h = m(**b).last_hidden_state
        e = (h * b.attention_mask[..., None]).sum(1) / b.attention_mask.sum(1, keepdim=True)
        np.save(f, F.normalize(e, dim=-1).cpu().numpy())
    e = np.load(f); e = e - e.mean(0)
    u, s, vt = np.linalg.svd(e, full_matrices=False)
    p = e @ vt[:D].T
    return p / p.std() * 0.02 * 3

class Block(nn.Module):
    def __init__(s):
        super().__init__()
        s.ln1, s.ln2 = nn.LayerNorm(D), nn.LayerNorm(D)
        s.qkv, s.proj = nn.Linear(D, 3 * D), nn.Linear(D, D)
        s.fc1, s.fc2 = nn.Linear(D, 4 * D), nn.Linear(4 * D, D)
        s.drop = nn.Dropout(0.1)
    def forward(s, x):
        B, T, _ = x.shape
        q, k, v = s.qkv(s.ln1(x)).split(D, -1)
        sh = lambda t: t.view(B, T, HEADS, D // HEADS).transpose(1, 2)
        a = F.scaled_dot_product_attention(sh(q), sh(k), sh(v), is_causal=True)
        x = x + s.drop(s.proj(a.transpose(1, 2).reshape(B, T, D)))
        return x + s.drop(s.fc2(F.gelu(s.fc1(s.ln2(x)))))

class SLM(nn.Module):
    def __init__(s, init=None):
        super().__init__()
        s.emb = nn.Embedding(len(TOK), D); s.pos = nn.Embedding(MAXLEN, D)
        nn.init.normal_(s.emb.weight, std=0.02); nn.init.normal_(s.pos.weight, std=0.02)
        if init is not None:
            with torch.no_grad(): s.emb.weight[:len(IDS)] = torch.tensor(init, dtype=torch.float)
        s.blocks = nn.ModuleList([Block() for _ in range(LAYERS)]); s.lnf = nn.LayerNorm(D)
    def forward(s, x):
        h = s.emb(x) + s.pos(torch.arange(x.shape[1], device=x.device))
        for b in s.blocks: h = b(h)
        return s.lnf(h) @ s.emb.weight.T  # pesos amarrados

def train(rows, init, epochs=40, seed=0):
    torch.manual_seed(seed)
    m = SLM(init).to(dev)
    seqs = [encode(r) for r in rows]
    L = max(map(len, seqs))
    X = torch.full((len(seqs), L), T2I["<s>"]); Y = torch.full((len(seqs), L), -100)
    for i, s in enumerate(seqs):
        X[i, :len(s) - 1] = torch.tensor(s[:-1]); Y[i, 2:len(s) - 1] = torch.tensor(s[3:])
    X, Y = X.to(dev), Y.to(dev)
    opt = torch.optim.AdamW(m.parameters(), lr=3e-3, weight_decay=0.05)
    steps = epochs * math.ceil(len(seqs) / 128); sched = torch.optim.lr_scheduler.OneCycleLR(opt, 3e-3, total_steps=steps)
    m.train()
    for ep in range(epochs):
        perm = torch.randperm(len(seqs), device=dev)
        for i in range(0, len(seqs), 128):
            b = perm[i:i + 128]
            loss = F.cross_entropy(m(X[b]).reshape(-1, len(TOK)), Y[b].reshape(-1), ignore_index=-100)
            opt.zero_grad(); loss.backward(); opt.step(); sched.step()
    return m.eval()

def scores(m, test):
    out = []
    with torch.no_grad():
        for r, i in ev.positions(test):
            x = torch.tensor([encode(r)[:3 + i]], device=dev)
            out.append(m(x)[0, -1, :len(IDS)].log_softmax(-1).cpu().numpy())
    return np.array(out)

if __name__ == "__main__":
    res = R / "experiments" / "results"
    init = e5_init()
    for name, (tr, te) in dict(A=(ev.A_train, ev.A_test), B=(ev.B_train, ev.B_test)).items():
        f = res / f"03_scores_{name}.npz"; data = dict(np.load(f))
        for tag, ini in [("slm_simbolos", init), ("slm_simbolos_sem_e5", None)]:
            t0 = time.time(); m = train(tr, ini)
            data[tag] = scores(m, te)
            print(name, tag, f"{time.time() - t0:.1f}s", flush=True)
        np.savez(f, **data)
    # modelo final: todo o conjunto, exportado para a página
    rows, _, _ = ev.ds.build()
    m = train(rows, init).cpu()
    sd = {k: v.numpy().astype(np.float32) for k, v in m.state_dict().items()}
    manifest, off = {}, 0
    for k, v in sd.items():
        manifest[k] = dict(shape=list(v.shape), offset=off); off += v.size
    np.concatenate([v.ravel() for v in sd.values()]).astype("<f4").tofile(R / "docs" / "data" / "slm.bin")
    cfg = dict(D=D, layers=LAYERS, heads=HEADS, maxlen=MAXLEN, tokens=TOK, n_symbols=len(IDS),
               params=sum(p.numel() for p in m.parameters()))
    x = torch.tensor([[T2I["p:manha"], T2I["l:casa"], T2I["<s>"], T2I["eu"], T2I["quero"]]])
    with torch.no_grad(): ref = m(x)[0, -1].log_softmax(-1).numpy()
    cfg["teste"] = dict(input=x[0].tolist(), logprobs_top=[[int(i), float(ref[i])] for i in ref.argsort()[::-1][:5]], logprobs=[float(v) for v in ref])
    json.dump(dict(config=cfg, tensors=manifest), open(R / "docs" / "data" / "slm.json", "w"))
    print("params", cfg["params"], "kb", (R / "docs/data/slm.bin").stat().st_size // 1024)
    print("top eu quero (manhã, casa):", [(TOK[i], round(p, 2)) for i, p in cfg["teste"]["logprobs_top"]])
