"""Mais dados e dados melhores com o Qwen (uma carga do modelo, 3 tarefas):

  revisar     confere a conversão do CHILDES pt-BR (out/childes_pictos.jsonl) e corrige → out/childes_revisado.jsonl
  converter   legendas pt-BR (OpenSubtitles) + fala de criança do CHILDES de Portugal → pictogramas → out/extra_pictos.jsonl
  professor   para cada momento de frases de treino, os 8 próximos pictogramas mais prováveis segundo o Qwen
              (sem ver a resposta) → out/professor.jsonl  (rótulos suaves para a destilação)

Uso: python qwen_dados.py [revisar] [converter] [professor]   (sem argumentos: as três)
Dados brutos em data_raw/ (CHILDES/TalkBank e OpenSubtitles: uso em pesquisa, não vão para o repositório).
"""
import csv, json, re, sys, random, pathlib
from collections import Counter
R = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(R))
from cenarios import PARCEIRO
from gerar_frases import REGRAS, MODELO, parse, valid
import texto_pictos as tp

RAW = R.parent.parent / "data_raw"; OUT = R / "out"
TAREFAS = [a for a in sys.argv[1:] if not a.startswith("-")] or ["revisar", "converter", "professor"]
LOCAIS = ("casa", "escola", "rua", "saude", "terapia")
tp.montar()
VOCAB = json.load(open(R.parent.parent / "docs" / "data" / "vocab.json", encoding="utf-8"))
LAB = {v["id"]: v["label"] for v in VOCAB}

def cobertura(texto):
    """fração das palavras de conteúdo do texto que existem na prancha"""
    w = [x for x in tp.tokens(texto) if x not in tp.LIGACAO]
    return (len(tp.para_pictos(texto, 99)) / len(w)) if w else 0

# ---------------- revisar ----------------
def itens_revisar():
    return [json.loads(l) for l in open(OUT / "childes_pictos.jsonl", encoding="utf-8")]
def prompt_revisar(lote):
    lista = "\n".join(f'{k + 1}. ADULTO: "{x["adulto"] or "(silêncio)"}" → CRIANÇA: "{x["frase"]}" → PICTOGRAMAS: {[p[0] for p in x["pictos"]]}'
                      for k, x in enumerate(lote))
    return f"""Uma criança que não fala precisa dizer, tocando pictogramas numa prancha de comunicação, o mesmo que uma criança
brasileira disse numa conversa real (CHILDES). Abaixo está uma conversão automática; confira cada uma.

{lista}

{REGRAS}
- Os pictogramas devem dizer o mesmo que a criança disse, em estilo telegráfico (1 a 6 pictogramas), com lemas.
- Corrija se: mudou o sentido, inventou palavra que a criança não disse, faltou a palavra principal, usou forma
  conjugada em vez do lema, ou separou uma expressão que é um pictograma só.
- Se a fala da criança não tem sentido sozinha (som, palavra cortada, imitação sem sentido), devolva ok=false.

Responda só com um array JSON com exatamente {len(lote)} itens, na mesma ordem:
{{"n": 1, "ok": true, "mudou": false, "pictos": [["lema_pt","lema_en"], ...]}} ou {{"n": 1, "ok": false}}"""

# ---------------- converter ----------------
def itens_converter():
    itens = []
    # fala de criança de Portugal (CHILDES PortuguesePt), com a fala do adulto logo antes
    linhas = sorted(csv.DictReader(open(RAW / "childes" / "ptpt.csv", encoding="utf-8")), key=lambda r: (int(r["transcript_id"]), int(r["id"])))
    ruido = re.compile(r"\b(xxx|yyy|www)\b"); ult, tr = "", None; vistos = set()
    for r in linhas:
        if r["transcript_id"] != tr: ult, tr = "", r["transcript_id"]
        g = (r["gloss"] or "").strip()
        if r["is_child"] != "True":
            if g and not ruido.search(g): ult = g
            continue
        if not g or ruido.search(g) or len(g.split()) > 14 or len(re.sub(r"\W", "", g)) < 2: continue
        if (ult, g) in vistos or cobertura(g) < 0.5: continue
        vistos.add((ult, g)); itens.append(dict(fonte="childes_pt", conversa="PT:" + r["transcript_id"], adulto=ult, crianca=g))
    n_pt = len(itens)
    # legendas pt-BR: fala curta e coloquial, quase toda com palavras da prancha; a fala de antes faz o papel do adulto
    L = [l.strip() for l in open(RAW / "legendas" / "pt_br.txt", encoding="utf-8", errors="ignore")]
    cand = []
    for i in range(1, len(L)):
        l = L[i]
        if not l or len(l) > 60 or re.search(r"[0-9<>\[\]#♪@/]|http|^-", l) or not 1 <= len(l.split()) <= 8: continue
        if re.search(r"\s[A-ZÁÉÍÓÚ][a-z]", l): continue  # nome próprio no meio
        if cobertura(l) < 0.75: continue
        cand.append((L[i - 1] if len(L[i - 1]) <= 90 else "", l))
    vistos = set(); uniq = []
    for a, l in cand:
        if l.lower() in vistos: continue
        vistos.add(l.lower()); uniq.append((a, l))
    random.Random(0).shuffle(uniq)
    for k, (a, l) in enumerate(uniq[:60000]):
        itens.append(dict(fonte="legenda", conversa=f"LG:{k // 50}", adulto=a, crianca=l))
    print("converter: childes_pt", n_pt, "legendas", len(itens) - n_pt, "(de", len(uniq), "candidatas)", flush=True)
    return itens
def prompt_converter(lote):
    tipos = ", ".join(PARCEIRO)
    lista = "\n".join(f'{k + 1}. ANTES: "{x["adulto"] or "(silêncio)"}" → FALA: "{x["crianca"]}"' for k, x in enumerate(lote))
    return f"""Abaixo estão falas curtas do dia a dia (conversas reais de crianças de Portugal e falas de filmes e desenhos em português),
cada uma com a fala que veio antes. Imagine que uma CRIANÇA que não fala quer dizer a mesma coisa tocando pictogramas numa prancha.

{lista}

{REGRAS}
- Mantenha o sentido da FALA em estilo telegráfico (1 a 6 pictogramas), com lemas em português do Brasil
  (ex.: "mamã" → "mãe", "autocarro" → "ônibus", "queres" → "querer").
- Se a FALA não é algo que uma criança diria no dia a dia (violência, romance, trabalho, assunto de adulto), ou não tem sentido
  sozinha, devolva ok=false.

Também classifique:
- "tipo_adulto": que tipo de fala veio ANTES, um de {tipos}
- "local": um de casa, escola, rua, saude, terapia (o mais provável)

Responda só com um array JSON com exatamente {len(lote)} itens, na mesma ordem:
{{"n": 1, "ok": true, "tipo_adulto": "...", "local": "...", "pictos": [["lema_pt","lema_en"], ...]}} ou {{"n": 1, "ok": false}}"""

# ---------------- professor ----------------
def itens_professor():
    D = json.load(open(OUT / "dataset.json", encoding="utf-8"))
    rows = [r for r in D["rows"] if r["split"] in ("treino", "treino2", "treino3", "adaptado")]
    random.Random(0).shuffle(rows)
    itens = []
    for r in rows[:14000]:
        for i in range(len(r["seq"]) + 1):
            if i < len(r["seq"]) and not r["seq"][i]: continue
            if any(not x for x in r["seq"][:i]): break
            itens.append(dict(adulto=r.get("adulto") or "", local=r["local"], prefixo=r["seq"][:i]))
    print("professor:", len(itens), "momentos", flush=True)
    return itens
def prompt_professor(lote):
    lista = "\n".join(f'{k + 1}. lugar: {x["local"]} | ADULTO: "{x["adulto"] or "(nada)"}" | já tocou: {[LAB[i] for i in x["prefixo"]] or "(nada ainda)"}'
                      for k, x in enumerate(lote))
    return f"""Uma criança de 3 a 12 anos, autista e que não fala, monta frases tocando pictogramas numa prancha de comunicação
(estilo telegráfico, lemas: "eu querer água", "não gostar barulho", "mãe ajudar"). Ela responde ao que o adulto disse.
Para cada momento abaixo, diga quais pictogramas ela tem mais chance de tocar EM SEGUIDA.

{lista}

Para cada momento, liste os 8 próximos pictogramas mais prováveis, do mais para o menos provável, como lemas
(infinitivo, singular, masculino). Use "FIM" se a frase já pode terminar ali. Prefira palavras simples de prancha.

Responda só com um array JSON com exatamente {len(lote)} itens, na mesma ordem: {{"n": 1, "proximos": ["...", ...]}}"""

def chamar(llm, prompts, max_tokens):
    tok = llm.get_tokenizer()
    from vllm import SamplingParams
    textos = [tok.apply_chat_template([{"role": "user", "content": p}], tokenize=False, add_generation_prompt=True) for p in prompts]
    return [o.outputs[0].text for o in llm.generate(textos, SamplingParams(temperature=0.2, top_p=0.9, max_tokens=max_tokens, seed=0))]

def por_n(texto, lote):
    for it in parse(texto) or []:
        if isinstance(it, dict) and isinstance(it.get("n"), int) and 1 <= it["n"] <= len(lote): yield lote[it["n"] - 1], it

if __name__ == "__main__":
    from vllm import LLM
    llm = LLM(MODELO, dtype="bfloat16", max_model_len=8192, gpu_memory_utilization=0.85, tensor_parallel_size=1)
    if "revisar" in TAREFAS:
        itens = itens_revisar(); lotes = [itens[i:i + 15] for i in range(0, len(itens), 15)]
        st = Counter()
        with open(OUT / "childes_revisado.jsonl", "w", encoding="utf-8") as f:
            for lote, txt in zip(lotes, chamar(llm, [prompt_revisar(l) for l in lotes], 4096)):
                for x, it in por_n(txt, lote):
                    if not it.get("ok"): st["removida"] += 1; continue
                    if not valid(it): st["inválida"] += 1; continue
                    mudou = [p[0] for p in it["pictos"]] != [p[0] for p in x["pictos"]]
                    st["corrigida" if mudou else "igual"] += 1
                    f.write(json.dumps(dict(x, pictos=it["pictos"], revisada=True, mudou=mudou), ensure_ascii=False) + "\n")
        print("revisar:", dict(st), flush=True)
    if "converter" in TAREFAS:
        itens = itens_converter(); lotes = [itens[i:i + 20] for i in range(0, len(itens), 20)]
        n_ok = Counter()
        with open(OUT / "extra_pictos.jsonl", "w", encoding="utf-8") as f:
            for lote, txt in zip(lotes, chamar(llm, [prompt_converter(l) for l in lotes], 4096)):
                for x, it in por_n(txt, lote):
                    if not it.get("ok") or not valid(it) or it.get("tipo_adulto") not in PARCEIRO or it.get("local") not in LOCAIS: continue
                    f.write(json.dumps(dict(fonte=x["fonte"], cenario=None, conversa=x["conversa"], periodo="tarde", local=it["local"],
                                            tipo_adulto=it["tipo_adulto"] if x["adulto"] else "nenhuma", adulto=x["adulto"],
                                            frase=x["crianca"], pictos=it["pictos"]), ensure_ascii=False) + "\n"); n_ok[x["fonte"]] += 1
        print("convertidas:", dict(n_ok), flush=True)
    if "professor" in TAREFAS:
        itens = itens_professor(); lotes = [itens[i:i + 12] for i in range(0, len(itens), 12)]
        n = 0
        with open(OUT / "professor.jsonl", "w", encoding="utf-8") as f:
            for lote, txt in zip(lotes, chamar(llm, [prompt_professor(l) for l in lotes], 2048)):
                for x, it in por_n(txt, lote):
                    p = it.get("proximos")
                    if not isinstance(p, list): continue
                    ids = []
                    for w in p[:10]:
                        if not isinstance(w, str): continue
                        if w.strip().upper() == "FIM": ids.append("FIM"); continue
                        m = tp.para_pictos(w, 1, sem_ligacao=False)
                        if m and m[0] not in ids: ids.append(m[0])
                    if ids:
                        f.write(json.dumps(dict(adulto=x["adulto"], prefixo=x["prefixo"], proximos=ids), ensure_ascii=False) + "\n"); n += 1
        print("professor:", n, "momentos com resposta", flush=True)
    print("FIM", flush=True)
