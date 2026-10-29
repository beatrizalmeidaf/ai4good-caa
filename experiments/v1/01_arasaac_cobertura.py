"""Experimento 1: cobertura do ARASAAC para o vocabulário pt-BR.

Para cada termo: tenta /bestsearch (correspondência exata), cai para /search.
Salva resultados, baixa os PNGs (300px) para docs/pictos e gera resumo.
"""
import json, sys, time, pathlib, urllib.parse
import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "experiments"))
from vocab import VOCAB, OVERRIDES

API = "https://api.arasaac.org/v1/pictograms/pt"
IMG = "https://static.arasaac.org/pictograms/{id}/{id}_300.png"
OUT = ROOT / "experiments" / "results"
PICTOS = ROOT / "docs" / "pictos"
s = requests.Session()

def query(kind, term):
    t0 = time.time()
    r = s.get(f"{API}/{kind}/{urllib.parse.quote(term)}", timeout=20)
    dt = (time.time() - t0) * 1000
    return (r.json() if r.status_code == 200 else []), dt

rows, latencies = [], []
for sid, label, cat, term in VOCAB:
    auto, dt = query("bestsearch", term); latencies.append(dt)
    if not auto:
        auto, _ = query("search", term)
    res, mode = auto, ("bestsearch" if auto else "nenhum")
    if sid in OVERRIDES:
        pid, motivo = OVERRIDES[sid]
        info = s.get(f"{API}/{pid}", timeout=20).json()
        res, mode = [info] + [x for x in auto if x["_id"] != pid], "curado"
    elif not res:
        res, dt = query("search", term); latencies.append(dt); mode = "search" if res else "nenhum"
    top = res[0] if res else None
    row = dict(id=sid, label=label, cat=cat, term=term, mode=mode, n=len(res),
               arasaac_id=top["_id"] if top else None,
               keywords=[k["keyword"] for k in top["keywords"]][:4] if top else [],
               alternativas=[x["_id"] for x in res[1:6]],
               motivo=OVERRIDES.get(sid, (None, None))[1])
    if top:
        f = PICTOS / f"{top['_id']}.png"
        if not f.exists():
            img = s.get(IMG.format(id=top["_id"]), timeout=30)
            if img.headers.get("content-type") != "image/png":  # estático falha p/ alguns ids
                img = s.get(f"https://api.arasaac.org/v1/pictograms/{top['_id']}?resolution=500&download=false", timeout=30)
            assert img.headers.get("content-type") == "image/png", top["_id"]
            f.write_bytes(img.content)
    rows.append(row)
    print(f"{mode:10s} n={len(res):3d} {label:22s} -> {row['arasaac_id']} {row['keywords']}")

found = [r for r in rows if r["arasaac_id"]]
summary = dict(
    total=len(rows), encontrados=len(found),
    exatos=sum(r["mode"] == "bestsearch" for r in rows),
    aproximados=sum(r["mode"] == "search" for r in rows),
    curados=sum(r["mode"] == "curado" for r in rows),
    curados_ptpt=sum(1 for r in rows if r["mode"] == "curado" and (r["motivo"] or "").startswith("pt")),
    sem_resultado=[r["label"] for r in rows if not r["arasaac_id"]],
    latencia_ms_mediana=sorted(latencies)[len(latencies)//2],
    tamanho_pictos_kb=round(sum(p.stat().st_size for p in PICTOS.glob("*.png"))/1024),
)
json.dump(rows, open(OUT / "01_cobertura.json", "w"), ensure_ascii=False, indent=1)
json.dump(summary, open(OUT / "01_resumo.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(summary, ensure_ascii=False, indent=1))
