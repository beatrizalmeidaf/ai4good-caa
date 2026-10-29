"""Junta os resultados das comparações de voz em docs/vozes/resultados.json (lido por docs/vozes.html).

Por padrão deixa de fora as vozes clonadas de crianças (clonar_vozes/), que não são publicadas.
Uso: python juntar_vozes.py [--com-criancas]
"""
import json, sys, pathlib
R = pathlib.Path(__file__).resolve().parent
DOCS = R.parent.parent / "docs"
com = "--com-criancas" in sys.argv
res = {}
for f in ["vozes.json", "vozes_f5.json", "vozes_criancas_xtts.json", "vozes_criancas_f5.json"]:
    p = R / "out" / f
    if p.exists(): res.update(json.load(open(p, encoding="utf-8")))
if not com: res = {k: v for k, v in res.items() if "crianca" not in k}
# só vozes que têm amostras para ouvir
res = {k: {kk: vv for kk, vv in v.items() if kk != "erros"} for k, v in res.items() if (DOCS / "vozes" / k / "0.mp3").exists() or k.startswith("kokoro")}
json.dump(res, open(DOCS / "vozes" / "resultados.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for k, v in sorted(res.items(), key=lambda kv: -kv[1]["acerto"]): print(f"{k:22s} {v['acerto']:5.1f}%  {v['ms_por_palavra']:6.0f} ms")
