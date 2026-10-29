"""Exporta dados para a página (docs/data): vocabulário, n-grama treinado
no conjunto inteiro e resultados dos experimentos."""
import json, pathlib, sys, importlib
R = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "experiments"))
from ngram import NGram, L
ds = importlib.import_module("02_dataset_sintetico")
res = R / "experiments" / "results"; out = R / "docs" / "data"

cob = json.load(open(res / "01_cobertura.json"))
vocab = [dict(id=r["id"], label=r["label"], cat=r["cat"], pic=r["arasaac_id"]) for r in cob]
json.dump(vocab, open(out / "vocab.json", "w"), ensure_ascii=False)

rows, _, uniq = ds.build()
json.dump(dict(lambdas=L, counts=NGram().fit(rows).export()), open(out / "ngram.json", "w"), ensure_ascii=False)

def conclusoes(M):
    if not M: return []
    import copy; M0 = M; M = copy.deepcopy(M)
    for sc in M.values():
        for v in sc.values():
            for k in ("top1", "top5"): v[k] = str(v[k]).replace(".", ",")
    a, b = M["A"], M["B"]
    llm_b = (max(v["top5"] for k, v in M0["B"].items() if k.startswith("llm")),)
    hib_b = (max(v["top5"] for k, v in M0["B"].items() if k.startswith("hibrido")),)
    llm_b = (str(llm_b[0]).replace(".", ","),)
    return [
        f"Prever o próximo pictograma é viável: com frases da rotina da criança, o símbolo certo aparece entre as 5 sugestões em {a['slm_simbolos']['top5']}% das vezes (SLM de símbolos), contra {a['unigrama']['top5']}% mostrando só os mais usados. Isso corta cerca de {a['slm_simbolos']['economia_toques']:.0f}% dos toques.",
        f"Modelos de linguagem genéricos (0,36 a 1,7 bilhão de parâmetros), sem treino, não servem sozinhos: o melhor acerta {llm_b[0]}% no top-5 nas frases inéditas. Eles não sabem o que é uma prancha de CAA nem o vocabulário fixo.",
        f"Combinados com n-grama, ajudam pouco nas frases inéditas (até {str(hib_b[0]).replace('.', ',')}% contra {b['ngrama_ctx']['top5']}% do n-grama), exigem baixar ~500 MB e fazer 124 passadas por toque. Não cabem na meta de latência mínima.",
        f"O SLM de símbolos (238 mil parâmetros, 0,9 MB) chega a {b['slm_simbolos']['top5']}% nas frases inéditas e é o que põe o símbolo certo mais perto do início da barra (maior MRR nos dois cenários, contando as duas versões). Roda em JavaScript puro em ~2 ms, offline, e ainda prevê o fim da frase para sugerir o botão falar.",
        "Iniciar os símbolos com embeddings multilíngues (e5) não mudou o resultado: diferenças de 1 ponto estão dentro do ruído de uma única execução.",
        "Limite principal: os dados são sintéticos e escritos por nós. O próximo passo é gerar frases mais variadas com um modelo grande (offline, como professor), revisar com fonoaudióloga e coletar uso real com consentimento.",
    ]

def load(name):
    p = res / name
    return json.load(open(p)) if p.exists() else None
json.dump(dict(
    cobertura=load("01_resumo.json"),
    curados=[dict(label=r["label"], pic=r["arasaac_id"], motivo=r["motivo"]) for r in cob if r["mode"] == "curado"],
    dataset=dict(modelos=len(ds.TEMPLATES), frases_unicas=len(uniq), amostras=len(rows)),
    metricas=load("04_metricas.json"),
    latencia_gpu=load("03_latencia_gpu.json"),
    conclusoes=conclusoes(load("04_metricas.json")),
), open(out / "resultados.json", "w"), ensure_ascii=False, indent=1)
print("ok", (out / "ngram.json").stat().st_size // 1024, "KB ngram")
