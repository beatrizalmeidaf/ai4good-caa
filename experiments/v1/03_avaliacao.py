"""Experimento 2b/3: avalia preditores do próximo símbolo.

Uso: python3 03_avaliacao.py [modelo_hf ...]
Salva, por posição avaliada, os scores de cada preditor em results/03_scores_*.npz
"""
import json, math, random, sys, time, pathlib
import numpy as np
R = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "experiments"))
from vocab import VOCAB
from ngram import NGram
import importlib
ds = importlib.import_module("02_dataset_sintetico")

IDS = [v[0] for v in VOCAB]
LABEL = {v[0]: v[1] for v in VOCAB}
PER = dict(manha="manhã", tarde="tarde", noite="noite")
LOC = dict(casa="em casa", escola="na escola")

rows, test_phr, _ = ds.build()
rnd = random.Random(1)
# Cenário A: rotina pessoal (split aleatório das amostras)
idx = list(range(len(rows))); rnd.shuffle(idx)
A_train = [rows[i] for i in idx[:4800]]
A_test = [rows[i] for i in idx[4800:]][:500]
# Cenário B: frases inéditas (frases inteiras fora do treino)
B_train = [r for r in rows if tuple(r["seq"]) not in test_phr]
B_test_all = [r for r in rows if tuple(r["seq"]) in test_phr]
rnd.shuffle(B_test_all); B_test = B_test_all[:500]

def positions(test):
    return [(r, i) for r in test for i in range(len(r["seq"]))]

def prompt(r, i):
    feito = " ".join(LABEL[s] for s in r["seq"][:i]) or "(nada ainda)"
    return (f"Uma criança autista não verbal usa uma prancha de comunicação com pictogramas "
            f"para formar frases curtas. Período: {PER[r['periodo']]}, {LOC[r['local']]}.\n"
            f"Pictogramas já escolhidos: {feito}\nPróximo pictograma:")

def ngram_scores(train, test, use_ctx=True):
    m = NGram(use_ctx).fit(train)
    out = []
    for r, i in positions(test):
        p = m.predict(r["periodo"], r["local"], r["seq"][:i], IDS)
        out.append(np.log([p[w] for w in IDS]))
    return np.array(out)

def unigram_scores(train, test):
    from collections import Counter
    c = Counter(s for r in train for s in r["seq"]); tot = sum(c.values())
    v = np.log([(c[w] + 1e-3) / tot for w in IDS])
    return np.array([v for _ in positions(test)])

def llm_scores(model_name, test, device="cuda"):
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    tok = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=torch.bfloat16).to(device).eval()
    cand = [tok(" " + LABEL[w], add_special_tokens=False).input_ids for w in IDS]
    first = torch.tensor([c[0] for c in cand], device=device)
    full, ft, t_full, t_first = [], [], [], []
    cache = {}
    for r, i in positions(test):
        key = (r["periodo"], r["local"], tuple(r["seq"][:i]))
        if key in cache:
            a, b = cache[key]; full.append(a); ft.append(b); continue
        p_ids = tok(prompt(r, i), add_special_tokens=False).input_ids
        with torch.no_grad():
            # 1) aproximação barata: só o 1º token de cada candidato, 1 forward
            torch.cuda.synchronize(); t0 = time.time()
            lo = model(torch.tensor([p_ids], device=device)).logits[0, -1].float().log_softmax(-1)
            b = lo[first].cpu().numpy()
            torch.cuda.synchronize(); t_first.append(time.time() - t0)
            # 2) score completo: soma do log-prob de todos os tokens do rótulo
            t0 = time.time()
            seqs = [p_ids + c for c in cand]; L = max(map(len, seqs))
            pad = tok.pad_token_id if tok.pad_token_id is not None else 0
            x = torch.tensor([s + [pad] * (L - len(s)) for s in seqs], device=device)
            att = torch.tensor([[1] * len(s) + [0] * (L - len(s)) for s in seqs], device=device)
            lp = model(x, attention_mask=att).logits.float().log_softmax(-1)
            a = np.zeros(len(IDS))
            for k, c in enumerate(cand):
                for j, t in enumerate(c):
                    a[k] += lp[k, len(p_ids) + j - 1, t].item()
            torch.cuda.synchronize(); t_full.append(time.time() - t0)
        cache[key] = (a, b); full.append(a); ft.append(b)
    del model; torch.cuda.empty_cache()
    return np.array(full), np.array(ft), float(np.median(t_full)), float(np.median(t_first))

def gold(test):
    return np.array([IDS.index(r["seq"][i]) for r, i in positions(test)])

if __name__ == "__main__":
    out = R / "experiments" / "results"; out.mkdir(exist_ok=True)
    models = sys.argv[1:]
    for name, (tr, te) in dict(A=(A_train, A_test), B=(B_train, B_test)).items():
        f = out / f"03_scores_{name}.npz"
        data = dict(np.load(f)) if f.exists() else {}
        data["gold"] = gold(te)
        data["unigrama"] = unigram_scores(tr, te)
        data["ngrama_sem_ctx"] = ngram_scores(tr, te, use_ctx=False)
        data["ngrama_ctx"] = ngram_scores(tr, te, use_ctx=True)
        lat = json.load(open(out / "03_latencia_gpu.json")) if (out / "03_latencia_gpu.json").exists() else {}
        for m in models:
            short = m.split("/")[-1]
            t0 = time.time()
            full, ft, tf, t1 = llm_scores(m, te)
            data[f"llm_full:{short}"], data[f"llm_first:{short}"] = full, ft
            lat[short] = dict(full_ms=tf * 1000, first_ms=t1 * 1000)
            print(f"[{name}] {short}: {time.time()-t0:.0f}s", flush=True)
        json.dump(lat, open(out / "03_latencia_gpu.json", "w"), indent=1)
        np.savez(f, **data)
        print(name, "posições:", len(data["gold"]), "treino:", len(tr), "teste:", len(te))
