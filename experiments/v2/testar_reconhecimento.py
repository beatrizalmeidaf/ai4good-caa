"""Treino de fala: transcrição livre vs. verificação da palavra-alvo (mesmo modelo Whisper do navegador).

Verificação: o Whisper calcula a probabilidade de o áudio ser a palavra-alvo e a de ser cada uma de
N palavras de comparação; o acerto conta quando a alvo vence. Teste com áudios das palavras
(voz gravada do Zuli) em três condições: normal, tom de criança (+4 semitons) e ruído.
Também mede falso aceite: áudio de OUTRA palavra avaliado como se fosse a alvo.
Uso: python testar_reconhecimento.py [modelo]   (padrão openai/whisper-base)
"""
import json, sys, random, pathlib, subprocess, unicodedata
import numpy as np, torch
from transformers import WhisperProcessor, WhisperForConditionalGeneration

R = pathlib.Path(__file__).resolve().parent; DOCS = R.parent.parent / "docs"
FFMPEG = str(pathlib.Path.home() / "bin" / "ffmpeg")
MODELO = sys.argv[1] if len(sys.argv) > 1 else "openai/whisper-base"
dev = "cuda" if torch.cuda.is_available() else "cpu"
proc = WhisperProcessor.from_pretrained(MODELO); model = WhisperForConditionalGeneration.from_pretrained(MODELO).to(dev).eval()
tok = proc.tokenizer
vocab = json.load(open(DOCS / "data" / "vocab.json"))
rnd = random.Random(0)
palavras = [w for w in vocab[:200] if len(w["label"]) > 1]
alvos = rnd.sample(palavras, 60)

def carregar(pid, cond):
    af = {"normal": "anull", "crianca": "asetrate=24000*1.26,aresample=24000,atempo=0.794", "ruido": "anull"}[cond]
    raw = subprocess.run([FFMPEG, "-loglevel", "quiet", "-i", str(DOCS / "audio" / "f" / f"{pid}.mp3"), "-af", af,
                          "-f", "f32le", "-ac", "1", "-ar", "16000", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.float32).copy()
    if cond == "ruido": x = x + np.random.default_rng(1).normal(0, 0.03, len(x)).astype(np.float32)
    return np.concatenate([np.zeros(4000, np.float32), x, np.zeros(4000, np.float32)])

PREFIXO = tok.convert_tokens_to_ids(["<|startoftranscript|>", "<|pt|>", "<|transcribe|>", "<|notimestamps|>"])
EOT = tok.convert_tokens_to_ids("<|endoftext|>")

@torch.no_grad()
def pontuar(audio, textos):
    """log-prob média por token de cada texto, dado o áudio (encoder roda uma vez)."""
    feats = proc(audio, sampling_rate=16000, return_tensors="pt").input_features.to(dev)
    enc = model.model.encoder(feats).last_hidden_state
    seqs = [PREFIXO + tok.encode(" " + t, add_special_tokens=False) + [EOT] for t in textos]
    L = max(map(len, seqs)); ids = torch.full((len(seqs), L), EOT); mask = torch.zeros(len(seqs), L)
    for i, s in enumerate(seqs): ids[i, :len(s)] = torch.tensor(s); mask[i, :len(s)] = 1
    ids, mask = ids.to(dev), mask.to(dev)
    out = model(encoder_outputs=(enc.expand(len(seqs), -1, -1),), decoder_input_ids=ids[:, :-1]).logits.log_softmax(-1)
    lp = out.gather(-1, ids[:, 1:, None])[..., 0] * mask[:, 1:]
    n0 = len(PREFIXO) - 1
    return ((lp[:, n0:]).sum(1) / mask[:, 1 + n0:].sum(1)).cpu().numpy()

def norm(s): return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn" and (c.isalnum() or c == " ")).strip()
@torch.no_grad()
def transcrever(audio):
    feats = proc(audio, sampling_rate=16000, return_tensors="pt").input_features.to(dev)
    ids = model.generate(feats, language="portuguese", task="transcribe", max_new_tokens=20)
    return tok.decode(ids[0], skip_special_tokens=True)

res = {}
for cond in ["normal", "crianca", "ruido"]:
    livre = verif = falso = 0; exemplos = []
    for w in alvos:
        a = carregar(w["id"], cond)
        t = transcrever(a); livre += norm(w["label"]) in norm(t)
        comp = [x["label"] for x in rnd.sample([p for p in palavras if p["id"] != w["id"]], 9)]
        s = pontuar(a, [w["label"]] + comp); verif += int(np.argmax(s) == 0)
        # falso aceite: áudio de uma palavra qualquer, avaliado como se a alvo fosse outra
        outra = rnd.choice([p for p in palavras if p["id"] != w["id"]])
        s2 = pontuar(carregar(outra["id"], cond), [w["label"]] + comp); falso += int(np.argmax(s2) == 0)
        if len(exemplos) < 6: exemplos.append([w["label"], t])
    n = len(alvos)
    res[cond] = dict(transcricao_livre=round(100 * livre / n, 1), verificacao=round(100 * verif / n, 1), falso_aceite=round(100 * falso / n, 1), exemplos=exemplos)
    print(cond, res[cond], flush=True)
json.dump(res, open(R / "out" / f"reconhecimento_{MODELO.split('/')[-1]}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
