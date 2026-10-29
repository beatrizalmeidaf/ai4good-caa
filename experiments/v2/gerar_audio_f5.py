"""Gera o áudio de cada pictograma com F5-TTS pt-BR clonando uma voz de referência (ex.: masculino_v2).

Mesmo cuidado do gerar_audio_xtts.py: até 3 tentativas por palavra, fica com a primeira que o Whisper
reconhece como exatamente a palavra (sem "ponto", número ou palavra a mais).
Uso: python gerar_audio_f5.py <pasta_saida (ex.: mc)> <referencia.wav> [--tudo]
Saída: docs/audio/<pasta>/<id>.mp3 e zuli_<n>.mp3, out/audio_f5_<pasta>.json
"""
import json, sys, time, pathlib, subprocess, unicodedata
import numpy as np, lameenc
from huggingface_hub import hf_hub_download

R = pathlib.Path(__file__).resolve().parent; DOCS = R.parent.parent / "docs"
FFMPEG = str(pathlib.Path.home() / "bin" / "ffmpeg")
PASTA, REF = sys.argv[1], sys.argv[2]; TUDO = "--tudo" in sys.argv; REFAZER = "--refazer-ruins" in sys.argv
OUT = DOCS / "audio" / PASTA; OUT.mkdir(parents=True, exist_ok=True)
vocab = json.load(open(DOCS / "data" / "vocab.json", encoding="utf-8"))
ZULI = json.load(open(DOCS / "data" / "zuli_falas.json", encoding="utf-8"))

from f5_tts.api import F5TTS
tts = F5TTS(model="F5TTS_Base", ckpt_file=hf_hub_download("firstpixel/F5-TTS-pt-br", "pt-br/model_last.safetensors"), device="cuda")
from transformers import pipeline
asr = pipeline("automatic-speech-recognition", "openai/whisper-medium", device=0)

def norm(s): return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn" and (c.isalnum() or c == " ")).strip()
def ff(a, sr_in, sr_out):
    return np.frombuffer(subprocess.run([FFMPEG, "-loglevel", "quiet", "-f", "f32le", "-ar", str(sr_in), "-ac", "1", "-i", "-", "-f", "f32le", "-ar", str(sr_out), "-"],
                                        input=a.astype(np.float32).tobytes(), capture_output=True).stdout, dtype=np.float32)
def limpo(t, alvo):
    tt, aa = norm(t).replace("-", " ").split(), norm(alvo).replace("-", " ").split()
    if any(ch.isdigit() for ch in t) or ("ponto" in tt and "ponto" not in aa): return False
    return aa == tt or (len(tt) == len(aa) and all(a2[:3] == t2[:3] for a2, t2 in zip(aa, tt)))
def reconhece(a, sr, alvo):
    x = ff(a, sr, 16000)
    t = asr(np.concatenate([np.zeros(8000, np.float32), x, np.zeros(8000, np.float32)]), generate_kwargs=dict(language="portuguese", task="transcribe"))["text"]
    return limpo(t, alvo)
def aparar(a, sr):
    thr = 0.02 * np.abs(a).max(); idx = np.where(np.abs(a) > thr)[0]
    return a[max(0, idx[0] - int(.05 * sr)): idx[-1] + int(.12 * sr)] if len(idx) else a
def mp3(a, sr):
    a = a / (np.abs(a).max() + 1e-6) * 0.9
    e = lameenc.Encoder(); e.set_bit_rate(40); e.set_in_sample_rate(sr); e.set_channels(1); e.set_quality(2)
    return e.encode((a * 32767).astype(np.int16).tobytes()) + e.flush()

curto = R / "out" / f"ref10_{PASTA}.wav"
subprocess.run([FFMPEG, "-loglevel", "quiet", "-y", "-i", REF, "-t", "10", "-ac", "1", "-ar", "24000", str(curto)])
x16 = np.frombuffer(subprocess.run([FFMPEG, "-loglevel", "quiet", "-i", str(curto), "-f", "f32le", "-ac", "1", "-ar", "16000", "-"], capture_output=True).stdout, dtype=np.float32)
ref_text = asr(x16.copy(), generate_kwargs=dict(language="portuguese", task="transcribe"))["text"].strip().lower()

def gerar(texto, seed):
    wav, sr, _ = tts.infer(ref_file=str(curto), ref_text=ref_text, gen_text=texto.lower(), remove_silence=True, speed=0.95, nfe_step=32, seed=seed)
    return aparar(np.asarray(wav, dtype=np.float32), sr), sr

stats = dict(ok=0, total=0, falhas=[]); t0 = time.time()
itens = [(str(v["id"]), v["label"], True) for v in vocab] + [(f"zuli_{i}", t, False) for i, t in enumerate(ZULI)]
def existente(chave):
    raw = subprocess.run([FFMPEG, "-loglevel", "quiet", "-i", str(OUT / f"{chave}.mp3"), "-f", "f32le", "-ac", "1", "-ar", "24000", "-"], capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32)
def TENTAR(falado, k):  # sementes novas; F5 devolve 24 kHz
    a, sr = gerar(falado, 20 + k)
    return a if sr == 24000 else checar_fim.para16k(a, sr)
# --lista: refaz só os áudios com "ponto" lido ou som sobrando no fim (lista de checar_fim.py);
# cada tentativa passa pela mesma checagem e o arquivo só é trocado se uma versão passar
if "--lista" in sys.argv:
    sys.path.insert(0, str(R)); import checar_fim
    juiz = checar_fim.Juiz()
    alvo_ids = set(json.load(open(R / "out" / f"fim_{PASTA}.json", encoding="utf-8"))["refazer"])
    lab = {str(v["id"]): v["label"] for v in vocab}
    feitos, falhas = 0, []
    for chave in sorted(map(str, alvo_ids)):
        texto = lab.get(chave)
        if not texto: continue
        aceito = None
        for k in range(10):
            a = TENTAR(texto.replace("_", " "), k)
            ok, mot, cons = juiz.avaliar(a, 24000, texto)
            if ok: aceito = a; break
            if cons is not None: aceito = cons; break
        if aceito is not None: (OUT / f"{chave}.mp3").write_bytes(checar_fim.mp3(aceito)); feitos += 1
        else: falhas.append(texto)
    print("refeitos:", feitos, "de", len(alvo_ids), "falhas:", falhas, flush=True)
    sys.exit(0)
ruins = []
for chave, texto, palavra in itens:
    if REFAZER and palavra and (OUT / f"{chave}.mp3").exists():
        if reconhece(existente(chave), 24000, texto): continue
        ruins.append(texto)
    elif not TUDO and (OUT / f"{chave}.mp3").exists(): continue
    falado = texto.replace("_", " ")
    melhor, ok = None, False
    for seed in (([4, 5, 6, 7, 8, 9] if REFAZER else [1, 2, 3]) if palavra else [1]):
        a, sr = gerar(falado, seed)
        if melhor is None: melhor = (a, sr)
        if not palavra or reconhece(a, sr, texto): melhor, ok = (a, sr), True; break
    stats["total"] += 1; stats["ok"] += ok
    if not ok: stats["falhas"].append(texto)
    (OUT / f"{chave}.mp3").write_bytes(mp3(*melhor))
    if stats["total"] % 100 == 0: print(stats["total"], "itens", f"{time.time() - t0:.0f}s", flush=True)
stats["acerto"] = round(100 * stats["ok"] / max(1, stats["total"]), 1); stats["ruins_encontrados"] = ruins
json.dump(stats, open(R / "out" / f"audio_f5_{PASTA}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("pronto:", stats["acerto"], "% reconhecido,", f"{time.time() - t0:.0f}s")
