"""Formas de cada palavra da prancha (conjugações, plural, feminino, diminutivo, variantes de Portugal e sinônimos diretos).

Serve para transformar texto (fala do adulto, legendas, respostas do Qwen) em pictogramas sem LLM, com a mesma regra
no treino e no navegador.
Saída: out/formas_raw.json  {rótulo: [formas...]}
"""
import json, pathlib, sys
R = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(R))
from gerar_frases import MODELO

vocab = json.load(open(R.parent.parent / "docs" / "data" / "vocab.json", encoding="utf-8"))
CLASSE = dict(acao="verbo/ação", pessoa="pessoa/pronome", descricao="adjetivo/sentimento", coisa="substantivo", lugar="lugar",
              social="expressão social", negacao="negação", tempo="tempo/pergunta/ligação")

def prompt(lote):
    lista = "\n".join(f'- "{v["label"]}" ({CLASSE.get(v["cor"], "")})' for v in lote)
    return f"""Estas são palavras de uma prancha de comunicação alternativa para crianças brasileiras:
{lista}

Para cada uma, liste as formas como ela aparece na fala real (português do Brasil e também de Portugal), para
reconhecer a palavra num texto:
- verbos: infinitivo, presente (eu, você/ele, nós, eles), passado (eu, ele), futuro com "vai", imperativo, gerúndio, particípio;
- substantivos e adjetivos: plural, feminino, diminutivo e aumentativo comuns (ex.: "aguinha", "carrinho");
- variantes de Portugal e infantis com o MESMO sentido (ex.: mãe → mamã, mamãe, mainha; ônibus → autocarro);
- sinônimos só se forem exatamente o mesmo conceito para uma criança (ex.: "cachorro" → "cão", "cachorrinho").
Não inclua palavras de outro sentido, nem formas que sejam outra palavra comum (ex.: não ponha "casa" em "casar").
Até 15 formas por palavra, todas em minúsculas.

Responda só com um objeto JSON: {{"palavra": ["forma1", "forma2", ...], ...}} com as {len(lote)} palavras."""

if __name__ == "__main__":
    import re
    from vllm import LLM, SamplingParams
    lotes = [vocab[i:i + 25] for i in range(0, len(vocab), 25)]
    llm = LLM(MODELO, dtype="bfloat16", max_model_len=8192, gpu_memory_utilization=0.85, tensor_parallel_size=1)
    tok = llm.get_tokenizer()
    textos = [tok.apply_chat_template([{"role": "user", "content": prompt(l)}], tokenize=False, add_generation_prompt=True) for l in lotes]
    outs = llm.generate(textos, SamplingParams(temperature=0.2, top_p=0.9, max_tokens=4096, seed=0))
    res = {}
    for lote, o in zip(lotes, outs):
        m = re.search(r"\{.*\}", o.outputs[0].text, flags=re.S)
        try: d = json.loads(m.group(0)) if m else {}
        except Exception: d = {}
        for v in lote:
            f = d.get(v["label"])
            if isinstance(f, list): res[v["label"]] = [x.strip().lower() for x in f if isinstance(x, str) and x.strip()]
    json.dump(res, open(R / "out" / "formas_raw.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print("formas:", len(res), "de", len(vocab), "palavras")
