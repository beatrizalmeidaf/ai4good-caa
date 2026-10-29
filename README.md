# Zuli

Prancha de comunicação alternativa (CAA) para crianças que ainda não falam, com pictogramas do ARASAAC
e sugestão do próximo pictograma por um modelo de linguagem pequeno que roda no próprio aparelho.
Prova de conceito para o AI4Good.

**Site:** https://beatrizalmeidaf.github.io/ai4good-caa/ · **Prancha (para salvar no tablet):** https://beatrizalmeidaf.github.io/ai4good-caa/prancha.html

## O que tem

- **Página inicial** (`docs/index.html`): abre a prancha de cada criança ou a área dos adultos. Sem cadastro nem login.
- **Prancha da criança** (`docs/prancha.html`)
  - grade fixa: as palavras nunca mudam de lugar (planejamento motor);
  - faixa de 6 sugestões que muda a cada toque, e o que continua sugerido fica no mesmo espaço;
  - o Zuli fala a frase quando a criança toca nele;
  - quadro **Agora** com a atividade da rotina;
  - **atalhos de calma** (pausa, parar, silêncio, abraço, música, ajuda) quando os toques ficam muito rápidos ou repetidos;
  - abas de **pranchas por foto**.
- **Treino de fala**: o Zuli fala a palavra, a criança repete e o Whisper (no navegador) verifica se combina com a palavra pedida.
- **Área dos adultos** (`docs/pais.html`, protegida por PIN)
  - **resumo da semana** em texto para pais e terapeuta;
  - painel de desenvolvimento e progresso do treino;
  - rotina visual, com sugestões aprendidas do uso;
  - **prancha por foto**: o CLIP olha a foto no aparelho e sugere os pictogramas da cena;
  - escolha da voz, ajustes, guia das cores;
  - levar os dados para outro aparelho (arquivo `.zuli.json`) e trocar de família.
- **Resultados** (`docs/resultados.html`) e **comparação de vozes** (`docs/vozes.html`).

Tudo fica no aparelho (localStorage). Depois do primeiro acesso, funciona sem internet.

## Modelo

Comitê de 3 transformers de 2 camadas sobre pictogramas (190 mil parâmetros cada, ~1,1 MB no total), treinados com
sementes diferentes; a prancha usa a média das previsões. Contexto: período do dia, lugar e fala do adulto. Prevê o próximo
pictograma e o fim da frase. Roda em JavaScript puro.

Dados de treino: conversas sintéticas (2 levas, 122 situações), mensagens reais de CAA adaptadas e **7.497 falas reais de
crianças brasileiras** do CHILDES (via IPA-CHILDES) convertidas em pictogramas.

| Acerto nas 6 sugestões (nunca vistas no treino) | Mais usados | N-grama | Zuli |
|---|---|---|---|
| Conversas novas | 33% | 60% | **67%** |
| Situações novas | 34% | 65% | **70%** |
| Conversas variadas (2ª leva) | 25% | 44% | **49%** |
| Conversas reais de crianças (CHILDES) | – | 21% | **25%** |

## Vozes

| Voz | Como foi feita | Palavras reconhecidas pelo Whisper |
|---|---|---|
| Feminina | XTTS-v2 clonando uma leitura do LibriVox (falante 12114), tom 3 semitons mais alto | ~90% |
| Masculina (criança) | F5-TTS pt-BR clonando uma voz de menino gerada por IA | ~83% |
| Voz do aparelho | speechSynthesis do navegador | depende do aparelho |

## Organização

```
docs/                    site publicado no GitHub Pages
  index.html             página inicial
  prancha.html           prancha da criança
  pais.html              área dos adultos
  resultados.html        resultados · vozes.html: comparação de vozes
  js/                    core (perfis, áudio, previsão), slm (modelo em JS), crianca, treino, pais, foto
  data/                  vocabulário, modelo (slm.json + slm.bin), n-grama de reserva, vetores do CLIP
  p/                     pictogramas (WebP 160 px)
  audio/f, mc            áudio de cada pictograma (voz feminina e masculina de criança)
  vozes/                 amostras das vozes testadas
experiments/
  v1/                    primeira rodada (cobertura do ARASAAC, LLMs sem treino vs. n-grama vs. SLM)
  v2/                    rodada atual
    frases.jsonl.gz, frases2.jsonl.gz   conversas geradas (1ª e 2ª leva)
    cenarios.py · gerar_frases.py · mapear_arasaac.py · preparar.py · treinar.py
    gerar_audio*.py · comparar_vozes*.py · testar_reconhecimento.py · clip_textos.py
    resultados/          métricas finais
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
- Vozes: XTTS-v2 (Coqui Public Model License, não comercial), F5-TTS pt-BR (firstpixel, CC BY-NC 4.0),
  Referência feminina: Multilingual LibriSpeech (CC BY 4.0).
- Fala real de criança: CHILDES/TalkBank (corpora pt-BR, via IPA-CHILDES), usada só para treino; os dados não vão para o repositório.
- Foto → prancha: CLIP ViT-B/32 (OpenAI, MIT), versão ONNX do Xenova.
- As cores seguem a chave Fitzgerald (explicação na aba "Guia e cores" da área dos adultos).
- As frases de treino são sintéticas e ainda não foram revisadas por fonoaudiólogo(a).
