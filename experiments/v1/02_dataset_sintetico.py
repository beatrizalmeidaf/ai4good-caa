"""Experimento 2a: conjunto sintético (contexto + sequência de símbolos).

Frases telegráficas típicas de CAA, agrupadas por rotina. Cada modelo de frase
tem contextos plausíveis (período, local) e lacunas com alternativas.
ATENÇÃO: é um rascunho para a PoC. Precisa ser revisado por fonoaudiólogo(a).
"""
import itertools, json, random, pathlib, sys
R = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "experiments"))
from vocab import VOCAB
IDS = {v[0] for v in VOCAB}

COMIDA = ["arroz", "feijao", "pao", "banana", "maca", "fruta", "biscoito"]
BEBIDA = ["agua", "suco", "leite"]
LAZER = ["bola", "brinquedo", "tablet", "massinha", "livro"]
PESSOA = ["mamae", "papai", "vovo", "irmao", "amigo", "professora"]
PESSOA_CASA = ["mamae", "papai", "vovo", "irmao"]
CORPO = ["cabeca", "barriga", "dente", "ouvido", "perna", "mao"]
SENT = ["feliz", "triste", "bravo", "cansado"]

M, T, N = "manha", "tarde", "noite"
CASA, ESC = "casa", "escola"
TODOS = [(p, l) for p in (M, T, N) for l in (CASA, ESC) if not (p == N and l == ESC)]

# (rotina, peso, contextos, modelo); lista dentro do modelo = lacuna
TEMPLATES = [
    # manhã em casa
    ("manha", 3, [(M, CASA)], ["bom_dia", PESSOA_CASA]),
    ("manha", 3, [(M, CASA)], ["eu", "quero", "cafe_manha"]),
    ("manha", 3, [(M, CASA)], ["eu", "quero", ["leite", "pao", "suco", "banana"]]),
    ("manha", 2, [(M, CASA)], ["eu", "estar", "cansado"]),
    ("manha", 2, [(M, CASA)], ["eu", "quero", "dormir", "mais"]),
    ("manha", 2, [(M, CASA)], ["nao_quero", "ir", "escola"]),
    ("manha", 2, [(M, CASA)], ["vestir", "roupa"]),
    ("manha", 1, [(M, CASA)], ["vestir", "sapato"]),
    ("manha", 2, [(M, CASA), (N, CASA)], ["escovar", "dente"]),
    ("manha", 1, [(M, CASA)], ["pegar", "mochila"]),
    ("manha", 2, [(M, CASA), (T, CASA)], ["ir", ["escola", "parque", "rua"], "agora"]),
    # higiene / banheiro (qualquer hora)
    ("banheiro", 4, TODOS, ["eu", "quero", "ir", "banheiro"]),
    ("banheiro", 3, TODOS, ["eu", "quero", "xixi"]),
    ("banheiro", 2, TODOS, ["ajudar", "banheiro", "por_favor"]),
    ("banheiro", 1, TODOS, ["trocar", "roupa"]),
    ("banheiro", 2, [(T, CASA), (N, CASA)], ["eu", "quero", "tomar_banho"]),
    ("banheiro", 2, [(T, CASA), (N, CASA)], ["nao_quero", "tomar_banho"]),
    ("banheiro", 1, TODOS, ["lavar", "mao"]),
    # refeição
    ("refeicao", 4, TODOS, ["eu", "ter", ["fome", "sede"]]),
    ("refeicao", 4, TODOS, ["eu", "quero", "comer", COMIDA]),
    ("refeicao", 4, TODOS, ["eu", "quero", "beber", BEBIDA]),
    ("refeicao", 3, TODOS, ["eu", "quero", BEBIDA]),
    ("refeicao", 3, TODOS, ["mais", COMIDA + BEBIDA, "por_favor"]),
    ("refeicao", 3, TODOS, ["eu", "quero", "mais"]),
    ("refeicao", 2, TODOS, ["nao_quero", COMIDA]),
    ("refeicao", 2, TODOS, [COMIDA, "gostoso"]),
    ("refeicao", 2, TODOS, ["pronto"]),
    ("refeicao", 2, TODOS, ["chega"]),
    ("refeicao", 2, [(T, CASA), (T, ESC)], ["eu", "quero", "lanche"]),
    ("refeicao", 2, [(T, CASA)], ["eu", "quero", "almoco"]),
    ("refeicao", 2, [(N, CASA)], ["eu", "quero", "jantar"]),
    ("refeicao", 1, [(T, CASA)], ["eu", "quero", "sorvete"]),
    ("refeicao", 1, TODOS, ["agua", "quente"]),
    # escola
    ("escola", 3, [(M, ESC), (T, ESC)], ["oi", ["professora", "amigo"]]),
    ("escola", 3, [(M, ESC), (T, ESC)], ["eu", "quero", ["desenhar", "ler", "brincar"]]),
    ("escola", 2, [(M, ESC), (T, ESC)], ["eu", "quero", "lapis"]),
    ("escola", 2, [(M, ESC), (T, ESC)], ["ajudar", "por_favor"]),
    ("escola", 2, [(M, ESC), (T, ESC)], ["vez"]),
    ("escola", 2, [(M, ESC), (T, ESC)], ["barulho"]),
    ("escola", 2, [(M, ESC), (T, ESC)], ["eu", "quero", "sair"]),
    ("escola", 2, [(M, ESC), (T, ESC)], ["eu", "quero", "ir", ["casa", "la_fora"]]),
    ("escola", 1, [(M, ESC), (T, ESC)], ["brincar", "amigo"]),
    ("escola", 1, [(M, ESC), (T, ESC)], ["onde", PESSOA_CASA]),
    ("escola", 1, [(T, ESC)], ["quando", "ir", "casa"]),
    ("escola", 1, [(M, ESC), (T, ESC)], ["eu", "quero", "descansar"]),
    # brincar / lazer
    ("brincar", 4, [(T, CASA), (T, ESC), (M, CASA)], ["eu", "quero", "brincar", LAZER]),
    ("brincar", 3, [(T, CASA), (N, CASA)], ["eu", "quero", ["assistir", "ver"], "tv"]),
    ("brincar", 3, [(T, CASA), (T, ESC)], ["eu", "quero", ["musica", "tablet", "bola"]]),
    ("brincar", 2, [(T, CASA)], ["eu", "quero", "ir", "parque"]),
    ("brincar", 2, [(T, CASA), (T, ESC)], ["vez"]),
    ("brincar", 2, [(T, CASA), (T, ESC)], ["brincar", "mais"]),
    ("brincar", 1, [(T, CASA)], ["eu", "quero", "ouvir", "musica"]),
    ("brincar", 1, [(T, CASA), (T, ESC)], ["eu", "gostar", LAZER]),
    # saúde
    ("saude", 3, TODOS, ["doer", CORPO]),
    ("saude", 3, TODOS, ["eu", "sentir", "dor"]),
    ("saude", 2, TODOS, ["eu", "sentir", "dor", CORPO]),
    ("saude", 2, TODOS, ["eu", "estar", ["doente", "enjoado"]]),
    ("saude", 2, TODOS, ["eu", "quero", "medico"]),
    ("saude", 1, [(M, CASA), (N, CASA)], ["eu", "quero", "remedio"]),
    ("saude", 1, TODOS, ["eu", "ter", ["calor", "frio"]]),
    # sentimentos
    ("sentimento", 3, TODOS, ["eu", "estar", SENT]),
    ("sentimento", 2, TODOS, ["eu", "ter", "medo"]),
    ("sentimento", 2, TODOS, ["eu", "quero", PESSOA_CASA]),
    ("sentimento", 2, TODOS, ["abracar", PESSOA]),
    ("sentimento", 2, TODOS, ["eu_te_amo", PESSOA_CASA]),
    ("sentimento", 1, TODOS, ["nao", "quero"]),
    ("sentimento", 1, TODOS, ["eu", "quero", "parar"]),
    # noite
    ("noite", 4, [(N, CASA)], ["eu", "quero", "dormir"]),
    ("noite", 3, [(N, CASA)], ["boa_noite", PESSOA_CASA]),
    ("noite", 2, [(N, CASA)], ["eu", "quero", "cobertor"]),
    ("noite", 2, [(N, CASA)], ["eu", "quero", "ler", "livro"]),
    ("noite", 2, [(N, CASA)], ["nao_quero", "dormir"]),
    ("noite", 1, [(N, CASA)], ["eu", "quero", "ir", "quarto"]),
    ("noite", 1, [(N, CASA)], ["amanha", "escola"]),
    # social geral
    ("social", 2, TODOS, ["obrigado"]),
    ("social", 2, TODOS, ["sim"]),
    ("social", 2, TODOS, ["nao"]),
    ("social", 1, TODOS, ["desculpa"]),
    ("social", 1, TODOS, ["tchau", PESSOA]),
    ("social", 1, TODOS, ["o_que", "fazer", "agora"]),
    ("social", 1, TODOS, ["eu", "quero", "ajudar"]),
    ("social", 1, [(T, CASA), (T, ESC)], ["ir", "casa", "depois"]),
    ("social", 1, TODOS, ["eu", "quero", "ir", "carro"]),
    ("social", 1, TODOS, ["voce", "quer", "brincar"]),
]

def expand(tpl):
    slots = [s if isinstance(s, list) else [s] for s in tpl]
    return [list(p) for p in itertools.product(*slots)]

def build(seed=0, n=6000):
    # corrige ids e valida
    phrases = []  # (rotina, contexto, seq, peso)
    for rot, w, ctxs, tpl in TEMPLATES:
        tpl = ["quero" if t == "quer" else t for t in tpl]
        ex = expand(tpl)
        for seq in ex:
            bad = [s for s in seq if s not in IDS]
            assert not bad, (bad, seq)
            for c in ctxs:
                phrases.append((rot, c, seq, w / len(ex)))
    uniq = sorted({tuple(p[2]) for p in phrases})
    rnd = random.Random(seed)
    test_phr = set(rnd.sample(uniq, int(0.2 * len(uniq))))
    weights = [p[3] for p in phrases]
    sample = rnd.choices(phrases, weights, k=n)
    rows = [dict(rotina=r, periodo=c[0], local=c[1], seq=s) for r, c, s, _ in sample]
    return rows, test_phr, uniq

if __name__ == "__main__":
    rows, test_phr, uniq = build()
    out = R / "experiments" / "results"
    json.dump(rows, open(out / "02_dataset.json", "w"), ensure_ascii=False)
    used = {s for r in rows for s in r["seq"]}
    print(f"modelos={len(TEMPLATES)} frases_unicas={len(uniq)} amostras={len(rows)} "
          f"simbolos_usados={len(used)}/{len(IDS)} comprimento_medio="
          f"{sum(len(r['seq']) for r in rows)/len(rows):.2f}")
    print("não usados:", sorted(IDS - used))
