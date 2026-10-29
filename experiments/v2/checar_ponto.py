"""2ª varredura: 'ponto' grudado no fim da palavra (sem pausa, então checar_fim.py não separa).

Para cada áudio, transcreve só a última parte (depois do que a palavra deveria durar) e procura "ponto"/"po".
Se achar, tenta cortar no começo desse trecho e confere de novo; senão entra na lista para refazer.
Uso: python checar_ponto.py <f|mc> [--cortar]   → acrescenta em out/fim_<pasta>.json ("refazer")
"""
import json, sys, re, pathlib
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import checar_fim as c

pasta = sys.argv[1]; CORTAR = "--cortar" in sys.argv
OUT = c.DOCS / "audio" / pasta
vocab = json.load(open(c.DOCS / "data" / "vocab.json", encoding="utf-8"))
j = c.Juiz()
PONTO = re.compile(r"\bpo(nto|nte|n)?\b|\b1\.1\b|\bum ponto\b", re.I)
achados, cortados, refazer = [], [], []
for v in vocab:
    p = OUT / f"{v['id']}.mp3"
    if not p.exists(): continue
    a = c.ler_mp3(p); sr = 24000
    segs = c.segmentos(a, sr)
    if not segs: continue
    fim = segs[-1][1]
    # janela final: último 0,55 s de fala
    ini = max(segs[0][0], fim - int(0.55 * sr))
    if fim - segs[0][0] < int(0.7 * sr): continue      # áudio curto: não cabe palavra + "ponto"
    t = j.transcrever(c.para16k(a[ini:fim + int(0.05 * sr)], sr))
    tl = c.norm(t)
    alvo_fim = c.norm(v["label"]).split()[-1]
    if "pont" in c.norm(v["label"]) or not PONTO.search(tl): continue
    achados.append([v["label"], t])
    # corta onde começa o "ponto": procura o ponto de menor energia antes da janela final
    f = int(0.01 * sr); e = np.array([np.sqrt((a[k:k + f] ** 2).mean()) for k in range(segs[0][0], fim - f, f)])
    cand = [segs[0][0] + k * f for k in np.argsort(e[: max(1, (ini - segs[0][0]) // f + 20)])[:8] if segs[0][0] + k * f > segs[0][0] + int(0.25 * sr)]
    ok = None
    for cut in sorted(cand, reverse=True):
        b = a[: cut + int(0.04 * sr)]; b16 = c.para16k(b, sr)
        tt = j.transcrever(b16)
        if c.limpo(tt, v["label"]):
            ok = b; break
    if ok is not None:
        cortados.append(v["label"])
        if CORTAR: p.write_bytes(c.mp3(ok))
    else: refazer.append(v["id"])
arq = c.R / "out" / f"fim_{pasta}.json"
d = json.load(open(arq, encoding="utf-8")) if arq.exists() else {"refazer": []}
d["ponto_achados"] = achados; d["ponto_cortados"] = cortados
d["refazer"] = sorted(set(d["refazer"]) | set(refazer))
json.dump(d, open(arq, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("pronto:", pasta, "com 'ponto':", len(achados), "cortados", len(cortados), "para refazer", len(refazer), flush=True)
print(achados[:40], flush=True)
