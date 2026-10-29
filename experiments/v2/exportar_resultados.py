"""Monta docs/data/resultados.json para a página de resultados."""
import json, pathlib, random
R = pathlib.Path(__file__).resolve().parent
OUT = R / "out"; SITE = R.parent.parent / "docs" / "data"
M = json.load(open(OUT / ("metricas_site.json" if (OUT / "metricas_site.json").exists() else "metricas.json"), encoding="utf-8"))
D = json.load(open(OUT / "dataset.json"))
res = D["resumo"]; vocab = {v["id"]: v["label"] for v in D["vocab"]}
raw_n = sum(1 for _ in open(OUT / "frases_raw.jsonl"))
fmt = lambda v: str(v).replace(".", ",")
best = M["_melhor"]
cn, sn, mr = M["conversa_nova"], M["cenario_novo"], M["mensagem_real"]

# exemplos: conversas do teste (falas do adulto + pictogramas da criança)
rnd = random.Random(4)
convs = sorted({r["conversa"] for r in D["rows"] if r["split"] == "conversa_nova"})
ex = []
for c in rnd.sample(convs, 3):
    for r in [r for r in D["rows"] if r["conversa"] == c]:
        ex.append(dict(adulto=r["adulto"], frase=r["frase"], seq=[[i, vocab[i]] for i in r["seq"] if i]))

params = json.load(open(SITE / "slm.json"))["config"]["params"]
kb = (SITE / "slm.bin").stat().st_size // 1024
extra = json.load(open(OUT / "extra.json")) if (OUT / "extra.json").exists() else {}
out = dict(
    metricas=M, dataset=res, exemplos=ex,
    lead=extra.get("lead", ""), conclusoes=extra.get("conclusoes", []), metodo=extra.get("metodo", []),
    numeros=[
        [f"{len(vocab)}", "pictogramas na prancha"],
        [f"{res['frases']:,}".replace(",", "."), "frases de treino e teste, em conversas"],
        [f"{fmt(sn[best]['top6'])}%", "acerto das 6 sugestões em situações que o modelo nunca viu"],
        [f"{3 * kb / 1024:.1f} MB".replace(".", ","), f"3 modelos de {params / 1e6:.2f} mi parâmetros (comitê), rodam no tablet".replace(".", ",")],
    ],
)
json.dump(out, open(SITE / "resultados.json", "w"), ensure_ascii=False, indent=1)
print("ok")
