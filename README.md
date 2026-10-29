# Zuli

Prancha de comunicação alternativa (CAA) para crianças não verbais, com pictogramas do ARASAAC
e sugestão do próximo pictograma por um modelo de linguagem pequeno que roda no próprio aparelho.
Prova de conceito para o AI4Good.

**Site:** https://beatrizalmeidaf.github.io/ai4good-caa/

## O que tem

- **Prancha da criança** (`docs/index.html`): pictogramas em posição fixa, faixa de 6 sugestões,
  o Zuli fala a frase quando a criança toca nele, voz feminina ou masculina conforme o perfil.
- **Treino de fala** (botão Treinar): o Zuli fala a palavra, a criança repete e o reconhecimento de fala
  (Whisper, no navegador) dá o retorno. Nada é gravado nem enviado.
- **Área dos pais** (`docs/pais.html`, protegida por PIN): perfil da criança, painel de desenvolvimento
  (frases por dia, vocabulário, palavras mais usadas), progresso do treino e ajustes.
- **Resultados** (`docs/resultados.html`): como o modelo foi treinado e avaliado.

Tudo fica no aparelho (localStorage). Depois do primeiro acesso, funciona offline.

## Organização

```
docs/                 site publicado no GitHub Pages
  index.html          prancha da criança
  pais.html           área dos pais
  resultados.html     resultados dos experimentos
  js/                 core.js (perfis, áudio, previsão), slm.js (modelo em JS puro), crianca.js, treino.js, pais.js
  data/               vocabulário, modelo (slm.json + slm.bin, float16), n-grama de reserva
  p/                  pictogramas (WebP 160 px)
  audio/f, audio/m    áudio de cada pictograma, voz feminina e masculina
experiments/
  v1/                 primeira rodada: cobertura do ARASAAC, 124 pictogramas, LLMs sem treino vs. n-grama vs. SLM
  v2/                 rodada atual
    cenarios.py       situações do dia a dia e falas do adulto
    gerar_frases.py   gera conversas adulto-criança em pictogramas (LLM no servidor) e adapta mensagens reais de CAA
    mapear_arasaac.py liga cada palavra a um pictograma do ARASAAC
    preparar.py       vocabulário, páginas da prancha e divisão treino/teste
    treinar.py        treina e avalia o SLM de símbolos, exporta para o site
    gerar_audio.py    áudio das palavras (Kokoro, pt-BR)
    baixar_pictos.py  baixa os pictogramas
    exportar_resultados.py
    out/frases_raw.jsonl   conjunto de frases gerado
```

## Rodar localmente

```
cd docs && python3 -m http.server 8000
```
e abrir http://localhost:8000.

## Créditos e licenças

- Pictogramas: Sergio Palao. Origem: ARASAAC (https://arasaac.org). Licença CC BY-NC-SA 4.0.
  Propriedade: Governo de Aragão (Espanha). Uso não comercial.
- Mensagens de CAA usadas como base para adaptação: turk9k (crowdsourcing de mensagens de CAA)
  e UNL-AAC-Phrases (MIT). Verificar a licença do turk9k antes de redistribuir o conjunto.
- Voz feminina: XTTS-v2 (Coqui Public Model License, uso não comercial) clonando uma leitura do LibriVox
  do Multilingual LibriSpeech (CC BY 4.0, falante 12114), com o tom 3 semitons mais alto.
- As cores dos pictogramas seguem a chave Fitzgerald (amarelo pessoas, verde ações, azul sentir e descrever,
  laranja coisas, roxo lugares, rosa conversa, vermelho não, cinza perguntas e tempo). Explicação na aba "Guia e cores" da área dos pais.
- As frases de treino ainda não foram revisadas por fonoaudiólogo(a).
