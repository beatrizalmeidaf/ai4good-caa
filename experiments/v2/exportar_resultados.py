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
# rodada 3: fala do adulto, mais dados, destilação e métrica de toques (treinar3.py)
if (OUT / "metricas3.json").exists():
    M3 = json.load(open(OUT / "metricas3.json", encoding="utf-8"))
    out["v3"] = {k: v for k, v in M3.items() if k in ("crianca_real", "conversa_nova", "cenario_novo", "conversa_nova2", "mensagem_real")}
    out["leitura_v3"] = [
        "Saber o que o adulto disse foi o maior ganho: nas conversas reais de crianças o acerto foi de 24,9% para 30,3%, e nas mensagens reais de CAA de 28,3% para 47,1%. No site, o adulto segura o botão \"Segure e fale\" (ou escreve), e as palavras viram pictogramas.",
        "Pré-treino com 27 mil falas de crianças de Portugal (CHILDES) e 43 mil falas curtas de legendas somou mais 1,4 ponto nas conversas reais (31,7%).",
        "Destilação de um modelo grande entrou no modelo final (melhor na validação); a destilação com as respostas do Qwen e a revisão do CHILDES pelo Qwen ficaram dentro da variação e não entraram.",
        "Toques: sem sugestões, uma frase real custa cerca de 11 toques, a maior parte para trocar de aba e passar páginas. A faixa economiza 13% nas conversas reais e 28% nas sintéticas; tirar da faixa o que já está na tela soma mais 1 a 2 pontos (já no site).",
        "Sem o tipo da pergunta (só a fala pelo microfone) o resultado quase não muda (0,5 ponto). As medidas supõem que a fala do adulto foi entendida; erros do reconhecimento de fala vão tirar parte do ganho.",
    ]
json.dump(out, open(SITE / "resultados.json", "w"), ensure_ascii=False, indent=1)
print("ok")
