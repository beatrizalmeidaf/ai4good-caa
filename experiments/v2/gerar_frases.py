"""Gera frases de CAA infantil em pictogramas com Qwen3-14B (vLLM).

Duas fontes:
  1) situações x falas do adulto (cenarios.py)
  2) adaptação de mensagens reais de CAA (turk9k, UNL-AAC-Phrases) para criança em pt-BR
Saída: experiments/v2/out/frases_raw.jsonl
Uso: python gerar_frases.py [--teste]
"""
import json, random, re, sys, pathlib, csv
R = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(R))
from cenarios import CENARIOS, PARCEIRO

TESTE = "--teste" in sys.argv
# modelo já baixado no servidor (MoE, 3B ativos: rápido e bom em pt-BR)
MODELO = "/local/user_beatrizalmeida/hf_cache/models--Qwen--Qwen3-30B-A3B-Instruct-2507/snapshots/0d7cf23991f47feeb3a57ecb4c9cee8ea4a17bfe"
OUT = R / "out"; OUT.mkdir(exist_ok=True)
RAW = R.parent.parent / "data_raw"
PER = {"manha": "manhã", "tarde": "tarde", "noite": "noite"}

REGRAS = """Regras para os pictogramas:
- A criança tem entre 3 e 12 anos, é autista e não fala; ela monta frases tocando pictogramas numa prancha de comunicação.
- "pictos" é a sequência de pictogramas que ela toca, na ordem: de 1 a 6 itens, estilo telegráfico.
- Use lemas: verbo no infinitivo (querer, ir, comer), substantivo no singular, adjetivo no masculino singular.
- Sem artigos. Evite preposições; use "com" ou "para" só quando forem essenciais.
- Pronomes permitidos: eu, você, ele, ela, nós, meu.
- Português do Brasil: banheiro, suco, ônibus, sorvete, tchau, celular, geladeira.
- Cada pictograma é um par [lema_pt, lema_en]; lema_en é a palavra simples em inglês que alguém digitaria para buscar o pictograma (ex.: ["banheiro","toilet"], ["querer","want"], ["não","no"], ["sim","yes"]).
- Expressões fixas podem ser um pictograma só: ["bom dia","good morning"], ["por favor","please"], ["obrigado","thank you"], ["fazer xixi","pee"].
- Varie bastante: pedidos, recusas, escolhas, comentários, sentimentos, perguntas, reclamações, humor, respostas curtas de uma palavra."""

def prompt_cenario(cen, local, periodo, foco, n):
    tipos = "\n".join(f'- "{k}": {v}' for k, v in PARCEIRO.items())
    return f"""Escreva {n} conversas curtas e diferentes entre um adulto (mãe, pai, professora, terapeuta, avó...) e uma criança que se comunica com uma prancha de pictogramas.
Situação: {cen}. Período: {PER[periodo]}. Lugar: {local}.
Cada conversa tem de 2 a 5 trocas. Em cada troca o adulto fala (ou fica em silêncio quando a criança começa) e a criança responde com pictogramas.
Pelo menos uma troca de cada conversa deve ter fala do adulto do tipo "{foco}".

Tipos de fala do adulto:
{tipos}

{REGRAS}
- No máximo 1 em cada 3 respostas da criança pode ser um pedido com "querer". O resto: comentar, recusar, responder sim/não, contar o que aconteceu, dizer o que sente, perguntar, chamar alguém, brincar.
- Use palavras específicas da situação (objetos, lugares, pessoas, ações), não só palavras genéricas.
- A resposta da criança tem que fazer sentido como resposta à fala do adulto.

Responda só com um array JSON de conversas. Cada conversa é um array de trocas:
[[{{"adulto": "Oi! Como foi a escola?", "tipo_adulto": "o_que_aconteceu", "frase": "Eu brinquei de bola com o Pedro.", "pictos": [["eu","I"],["brincar","play"],["bola","ball"],["amigo","friend"]]}}, ...], ...]"""

def prompt_adaptar(msgs):
    lista = "\n".join(f"{i+1}. {m}" for i, m in enumerate(msgs))
    tipos = ", ".join(PARCEIRO)
    return f"""Abaixo estão mensagens reais escritas por usuários de comunicação alternativa (em inglês).
Para cada uma, decida se é algo que uma criança de 3 a 12 anos realmente diria no dia a dia (família, escola, brincar, comer, sentir, saúde, passeio). Se sim, adapte para o que uma criança brasileira diria com pictogramas. Se for assunto de adulto (trabalho, dinheiro, política, relacionamento, ironia, gírias de adulto) ou se você estiver em dúvida, devolva null. É esperado que mais da metade seja null.

{lista}

{REGRAS}

Também classifique:
- "local": um de casa, escola, rua, saude, terapia
- "periodo": um de manha, tarde, noite
- "tipo_adulto": qual fala do adulto viria antes, um de {tipos}

Responda só com um array JSON com exatamente {len(msgs)} itens, na mesma ordem. Cada item repete a mensagem original no campo "n" (o número dela) e é:
{{"n": 1, "ok": false}} quando não serve para criança, ou
{{"n": 1, "ok": true, "adulto": "fala do adulto em português (pode ser vazio)", "tipo_adulto": "...", "local": "...", "periodo": "...", "frase": "...", "pictos": [["lema_pt","lema_en"], ...]}}"""

def jobs():
    rnd = random.Random(0)
    js = []
    reps = 1 if TESTE else 3
    for cen, local, periodos in CENARIOS[: 3 if TESTE else None]:
        for foco in PARCEIRO:
            for r in range(reps):
                per = rnd.choice(periodos)
                js.append(dict(fonte="cenario", cenario=cen, local=local, periodo=per,
                               prompt=prompt_cenario(cen, local, per, foco, 5)))
    msgs = [row["text"].strip() for row in csv.DictReader(open(RAW / "turk9k.csv"))]
    msgs += [row["Sentence"].strip() for row in csv.DictReader(open(RAW / "unl_aac.csv"))]
    msgs = [m for m in dict.fromkeys(msgs) if m]
    if TESTE: msgs = msgs[:50]
    for i in range(0, len(msgs), 20):
        js.append(dict(fonte="adaptado", origem=msgs[i:i+20], prompt=prompt_adaptar(msgs[i:i+20])))
    return js

def parse(text):
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    m = re.search(r"\[.*\]", text, flags=re.S)
    if not m: return None
    try: return json.loads(m.group(0))
    except Exception: return None

def valid(it):
    if not isinstance(it, dict): return False
    p = it.get("pictos")
    return isinstance(p, list) and 1 <= len(p) <= 8 and all(isinstance(x, list) and len(x) == 2 and all(isinstance(y, str) and y.strip() for y in x) for x in p)

if __name__ == "__main__":
    from vllm import LLM, SamplingParams
    js = jobs(); print("jobs:", len(js), flush=True)
    llm = LLM(MODELO, dtype="bfloat16", max_model_len=8192, gpu_memory_utilization=0.85, tensor_parallel_size=1)
    tok = llm.get_tokenizer()
    texts = [tok.apply_chat_template([{"role": "user", "content": j["prompt"]}], tokenize=False,
                                     add_generation_prompt=True) for j in js]
    outs = llm.generate(texts, SamplingParams(temperature=0.95, top_p=0.95, max_tokens=4096, seed=0))
    n_ok = n_bad = 0
    with open(OUT / ("frases_teste.jsonl" if TESTE else "frases_raw.jsonl"), "w") as f:
        for j, o in zip(js, outs):
            items = parse(o.outputs[0].text)
            if items is None: n_bad += 1; continue
            if j["fonte"] == "cenario":
                for c, conv in enumerate(items):
                    if not isinstance(conv, list): continue
                    for t, it in enumerate(conv):
                        if not valid(it) or it.get("tipo_adulto") not in PARCEIRO: continue
                        rec = dict(fonte="cenario", cenario=j["cenario"], local=j["local"], periodo=j["periodo"],
                                   conversa=f"{js.index(j)}-{c}", turno=t, **{x: it.get(x) for x in ("tipo_adulto", "adulto", "frase", "pictos")})
                        f.write(json.dumps(rec, ensure_ascii=False) + "\n"); n_ok += 1
                continue
            for it in items:
                if not valid(it) or not it.get("ok") or not isinstance(it.get("n"), int) or not 1 <= it["n"] <= len(j["origem"]): continue
                k = it["n"] - 1
                if True:
                    if it.get("local") not in ("casa", "escola", "rua", "saude", "terapia") or it.get("periodo") not in PER or it.get("tipo_adulto") not in PARCEIRO: continue
                    rec = dict(fonte="adaptado", origem=j["origem"][k], **{x: it.get(x) for x in ("local", "periodo", "tipo_adulto", "adulto", "frase", "pictos")})
                f.write(json.dumps(rec, ensure_ascii=False) + "\n"); n_ok += 1
    print("itens:", n_ok, "respostas sem JSON:", n_bad)
