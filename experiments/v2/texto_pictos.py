"""Texto → pictogramas da prancha, sem LLM (mesma regra em docs/js/core.js: textoParaPictos).

Usa docs/data/formas.json {forma: id}, montado de out/formas_raw.json (gerar_formas.py) + rótulos da prancha.
Junta até 3 palavras seguidas ("tomar banho", "por favor") antes de olhar palavra por palavra.
Uso: python texto_pictos.py   (monta formas.json e mostra exemplos)
"""
import json, re, pathlib, unicodedata
R = pathlib.Path(__file__).resolve().parent
SITE = R.parent.parent / "docs" / "data"
# palavras de ligação: não entram no contexto do adulto (só ocupam espaço)
LIGACAO = {"com", "no", "na", "nos", "nas", "para", "pra", "de", "do", "da", "dos", "das", "e", "mas", "ou", "se", "até", "sem",
           "em", "ao", "que", "tão", "embora", "o", "a", "os", "as", "um", "uma", "uns", "umas", "é", "lá", "aí", "aqui", "né", "então"}

def sem_acento(s): return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
def tokens(texto):
    t = texto.lower().replace("’", "'")
    t = re.sub(r"[^\w\s-]", " ", t).replace("_", " ")
    return [w for w in re.split(r"[\s-]+", t) if w]

# fala coloquial que a regra não pega
COLOQUIAL = {"tá": "estar", "tô": "estar", "tava": "estar", "tamo": "estar", "cadê": "onde", "quedê": "onde", "bora": "vamos",
             "mamã": "mãe", "papá": "pai", "vó": "avó", "vô": "avô", "tchauzinho": "tchau", "brigado": "obrigado", "brigada": "obrigado",
             "dói": "dor", "doi": "dor", "doeu": "dor", "doendo": "dor", "dodói": "dor", "machucou": "machucar", "machucado": "machucar",
             "aonde": "onde", "qualé": "qual", "num": "não", "nóis": "nós", "cê": "você", "ocê": "você", "tu": "você", "teu": "seu", "tua": "seu"}
TERM = {"ar": "o a as amos am ei aste ou ava avam ando ado e em ares ará aremos".split(),
        "er": "o e es emos em i eu este ia iam endo ido a am erá eremos".split(),
        "ir": "o e es imos em i iu iste ia iam indo ido a am irá iremos".split()}
def flexoes(v):
    """formas regulares: conjugação (verbos) e plural, feminino e diminutivo (nomes e adjetivos)"""
    w = tokens(v["label"])
    if not w: return []
    p, resto = w[0], w[1:]
    out = []
    if v["cor"] == "acao" and p[-2:] in TERM and len(p) > 3:
        out = [p[:-2] + t for t in TERM[p[-2:]]]
        if p.endswith("car"): out += [p[:-3] + "quei", p[:-3] + "que"]
        if p.endswith("gar"): out += [p[:-3] + "guei", p[:-3] + "gue"]
    elif v["cor"] in ("coisa", "lugar", "descricao", "pessoa") and len(w) == 1:
        if p.endswith("ão"): out = [p[:-2] + "ões", p[:-2] + "ães", p[:-2] + "ãozinho"]
        elif p.endswith("l"): out = [p[:-1] + "is", p + "zinho"]
        elif p.endswith(("r", "z", "s")): out = [p + "es", p + "zinho"]
        elif p.endswith("m"): out = [p[:-1] + "ns"]
        elif p.endswith(("o", "a", "e")):
            out = [p + "s", p[:-1] + "inho", p[:-1] + "inha", p[:-1] + "inhos", p[:-1] + "inhas"]
            if p.endswith("o"): out += [p[:-1] + "a", p[:-1] + "as"]
        else: out = [p + "s"]
    return [" ".join([f] + resto) for f in out]

def montar():
    vocab = json.load(open(SITE / "vocab.json", encoding="utf-8"))
    raw = json.load(open(R / "out" / "formas_raw.json", encoding="utf-8"))
    pos = {v["id"]: k for k, v in enumerate(vocab)}  # mais usado primeiro
    formas = {}
    # 1) rótulo exato sempre vence; 2) formas geradas, em caso de conflito fica a palavra mais usada
    for v in vocab: formas.setdefault(" ".join(tokens(v["label"])), v["id"])
    rotulos = set(formas)
    for v in vocab:
        n = len(tokens(v["label"]))
        for f in raw.get(v["label"], []):
            f = " ".join(tokens(f))
            # só formas do mesmo tamanho do rótulo ("quero" para "querer"); o Qwen às vezes inventa locuções ("carro de luxo")
            if not f or len(f.split()) != n or f in LIGACAO or f in rotulos: continue
            if f not in formas or pos[v["id"]] < pos[formas[f]]: formas[f] = v["id"]
    # regras de conjugação e plural completam o que faltou (não passam por cima do que já existe)
    for v in sorted(vocab, key=lambda v: pos[v["id"]]):
        for f in flexoes(v):
            if f not in formas and f not in LIGACAO: formas[f] = v["id"]
    for f, lab in COLOQUIAL.items():
        i = next((v["id"] for v in vocab if v["label"] == lab), None)
        if i is not None: formas.setdefault(f, i)
    # versão sem acento (o reconhecimento de fala às vezes esquece o acento); não sobrescreve
    for f, i in list(formas.items()): formas.setdefault(sem_acento(f), i)
    json.dump(formas, open(SITE / "formas.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    return formas

_F = None
def formas():
    global _F
    if _F is None: _F = json.load(open(SITE / "formas.json", encoding="utf-8"))
    return _F

def para_pictos(texto, maximo=10, sem_ligacao=True):
    """Palavras do texto → ids da prancha, em ordem, sem repetir; ignora o que não está na prancha."""
    F, w, out, i = formas(), tokens(texto or ""), [], 0
    while i < len(w):
        for n in (3, 2, 1):
            g = " ".join(w[i:i + n])
            if len(w[i:i + n]) == n and (g in F or sem_acento(g) in F):
                if not (sem_ligacao and n == 1 and w[i] in LIGACAO):
                    pid = F.get(g, F.get(sem_acento(g)))
                    if pid not in out: out.append(pid)
                i += n; break
        else: i += 1
    return out[:maximo]

if __name__ == "__main__":
    F = montar(); print("formas:", len(F))
    vocab = {v["id"]: v["label"] for v in json.load(open(SITE / "vocab.json", encoding="utf-8"))}
    for t in ["Você quer suco ou água?", "Quer ir ao banheiro?", "O que aconteceu com o seu carrinho?", "Vamos tomar banho agora?",
              "A mamã já chegou, queres o leitinho?", "Olha! Tem um ônibus azul ali.", "Gostou de brincar com os blocos?"]:
        print(t, "→", [vocab[i] for i in para_pictos(t)])
