"""Fala real de criança (CHILDES pt-BR, via IPA-CHILDES) → sequências de pictogramas.

Para cada fala de criança, pega a fala do adulto logo antes (mesma conversa) e pede ao LLM:
  - os pictogramas que a criança tocaria para dizer aquilo (estilo CAA, lema pt + termo en)
  - o tipo de fala do adulto (mesma lista de cenarios.PARCEIRO) e o lugar provável
Entrada: data_raw/childes/ptbr.csv  (CHILDES/TalkBank, uso em pesquisa; não vai para o repositório)
Saída: out/childes_pictos.jsonl
"""
import csv, json, re, sys, pathlib
R = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(R))
from cenarios import PARCEIRO
from gerar_frases import REGRAS, MODELO, parse, valid

RAW = R.parent.parent / "data_raw" / "childes" / "ptbr.csv"
linhas = sorted(csv.DictReader(open(RAW, encoding="utf-8")), key=lambda r: (int(r["transcript_id"]), int(r["id"])))
ruido = re.compile(r"\b(xxx|yyy|www)\b")
itens, ultimo_adulto, tr_ant = [], "", None
for r in linhas:
    if r["transcript_id"] != tr_ant: ultimo_adulto, tr_ant = "", r["transcript_id"]
    g = (r["gloss"] or "").strip()
    if r["is_child"] != "True":
        if g and not ruido.search(g): ultimo_adulto = g
        continue
    if not g or ruido.search(g) or len(g.split()) > 14 or len(re.sub(r"\W", "", g)) < 2: continue
    itens.append(dict(transcript=r["transcript_id"], idade_meses=round(float(r["target_child_age"] or 0)), adulto=ultimo_adulto, crianca=g))
print("falas de criança úteis:", len(itens), "conversas:", len({i["transcript"] for i in itens}), flush=True)

def prompt(lote):
    tipos = ", ".join(PARCEIRO)
    lista = "\n".join(f'{k + 1}. ADULTO: "{x["adulto"] or "(silêncio)"}" → CRIANÇA: "{x["crianca"]}"' for k, x in enumerate(lote))
    return f"""Abaixo estão trechos reais de conversas entre adultos e crianças brasileiras (transcrições do CHILDES).
Para cada trecho, imagine que a criança NÃO fala e precisa dizer a mesma coisa tocando pictogramas numa prancha de comunicação.

{lista}

{REGRAS}
- Mantenha o sentido do que a criança disse, em estilo telegráfico (só as palavras essenciais, de 1 a 6 pictogramas).
- Se a fala da criança não tem sentido sozinha (som, "hum", palavra cortada), devolva ok=false.

Também classifique:
- "tipo_adulto": que tipo de fala do adulto veio antes, um de {tipos}
- "local": um de casa, escola, rua, saude, terapia (o mais provável pela conversa)

Responda só com um array JSON com exatamente {len(lote)} itens, na mesma ordem:
{{"n": 1, "ok": true, "tipo_adulto": "...", "local": "...", "pictos": [["lema_pt","lema_en"], ...]}} ou {{"n": 1, "ok": false}}"""

if __name__ == "__main__":
    from vllm import LLM, SamplingParams
    lotes = [itens[i:i + 20] for i in range(0, len(itens), 20)]
    llm = LLM(MODELO, dtype="bfloat16", max_model_len=8192, gpu_memory_utilization=0.78, tensor_parallel_size=1)
    tok = llm.get_tokenizer()
    textos = [tok.apply_chat_template([{"role": "user", "content": prompt(l)}], tokenize=False, add_generation_prompt=True) for l in lotes]
    outs = llm.generate(textos, SamplingParams(temperature=0.3, top_p=0.9, max_tokens=4096, seed=0))
    n_ok = 0
    with open(R / "out" / "childes_pictos.jsonl", "w", encoding="utf-8") as f:
        for lote, o in zip(lotes, outs):
            for it in parse(o.outputs[0].text) or []:
                if not isinstance(it, dict) or not it.get("ok") or not isinstance(it.get("n"), int) or not 1 <= it["n"] <= len(lote): continue
                if not valid(it) or it.get("tipo_adulto") not in PARCEIRO or it.get("local") not in ("casa", "escola", "rua", "saude", "terapia"): continue
                x = lote[it["n"] - 1]
                f.write(json.dumps(dict(fonte="childes", cenario=None, conversa="CH:" + x["transcript"], periodo="tarde", local=it["local"],
                                        tipo_adulto=it["tipo_adulto"] if x["adulto"] else "nenhuma", adulto=x["adulto"], frase=x["crianca"],
                                        idade_meses=x["idade_meses"], pictos=it["pictos"]), ensure_ascii=False) + "\n"); n_ok += 1
    print("convertidas:", n_ok)
