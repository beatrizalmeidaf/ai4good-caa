"""Métricas: top-1, top-5 (barra de 5 sugestões), MRR e economia de toques.

Economia de toques (suposição simples): sem a barra, cada símbolo custa 2
toques (abrir categoria + escolher). Com a barra: 1 toque se o símbolo está
nas 5 sugestões, senão 2.
Híbrido = n-grama + β·LLM (LLM renormalizado sobre os 124 símbolos);
β escolhido na 1ª metade das posições e reportado na 2ª metade (sem vazar).
"""
import json, pathlib, numpy as np
R = pathlib.Path(__file__).resolve().parent.parent / "experiments" / "results"

def norm(s):
    s = s - s.max(1, keepdims=True)
    return s - np.log(np.exp(s).sum(1, keepdims=True))

def metr(s, g):
    rank = (s > s[np.arange(len(g)), g][:, None]).sum(1)
    top5 = (rank < 5).mean()
    return dict(top1=round(float((rank < 1).mean())*100, 1), top5=round(float(top5)*100, 1),
                mrr=round(float((1/(rank+1)).mean()), 3), economia_toques=round(float(top5/2)*100, 1))

res = {}
for name in "AB":
    d = dict(np.load(R / f"03_scores_{name}.npz")); g = d.pop("gold")
    half = len(g) // 2
    out = {k: metr(v, g) for k, v in d.items()}
    ng = norm(d["ngrama_ctx"])
    for k in [k for k in d if k.startswith("llm")]:
        l = norm(d[k]); best = max([0.1, 0.25, 0.5, 1, 2], key=lambda b: metr((ng+b*l)[:half], g[:half])["top5"] + metr((ng+b*l)[:half], g[:half])["mrr"])
        out["hibrido:" + k.split(":", 1)[1] + ("" if k.startswith("llm_full") else " (1º token)")] = dict(metr((ng+best*l)[half:], g[half:]), beta=best, nota="2ª metade")
    res[name] = out
json.dump(res, open(R / "04_metricas.json", "w"), indent=1, ensure_ascii=False)
for name, out in res.items():
    print(f"\n== Cenário {name} ==")
    for k, v in sorted(out.items(), key=lambda kv: -kv[1]["top5"]):
        print(f"{k:45s} top1={v['top1']:5.1f} top5={v['top5']:5.1f} mrr={v['mrr']:.3f} economia={v['economia_toques']:4.1f}%  {v.get('beta','')}")
