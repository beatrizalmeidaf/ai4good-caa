"""Gera o áudio de cada pictograma (voz feminina e masculina, Kokoro pt-BR) em MP3 leve.

Saída: docs/audio/{f,m}/<id>.mp3 e docs/audio/{f,m}/zuli_<n>.mp3 (falas do Zuli)
Também transcreve tudo com Whisper para medir inteligibilidade (out/audio_check.json).
Uso: python gerar_audio.py   (precisa de kokoro, soundfile, scipy, lameenc, transformers)
"""
import json, pathlib, re
import numpy as np, soundfile as sf, lameenc
from kokoro import KPipeline
R = pathlib.Path(__file__).resolve().parent
DOCS = R.parent.parent / "docs"
vocab = json.load(open(DOCS / "data" / "vocab.json"))
import os
VOZES = {"f": "pf_dora", "m": "pm_alex"}
if os.environ.get("SO_VOZ"): VOZES = {os.environ["SO_VOZ"]: VOZES[os.environ["SO_VOZ"]]}  # gera só uma voz
ZULI = ["Oi! Eu sou o Zuli!", "Escute.", "Agora é a sua vez!", "Muito bem!", "Isso! Você conseguiu!",
        "Quase! Vamos tentar de novo?", "Vamos tentar de novo.", "Não ouvi. Fala mais perto?", "Vamos treinar?", "Acabou! Parabéns!"]
json.dump(ZULI, open(DOCS / "data" / "zuli_falas.json", "w", encoding="utf-8"), ensure_ascii=False)

def mp3(audio, sr=24000):
    # corta silêncio nas pontas e normaliza
    a = audio.astype(np.float32); thr = 0.002 * np.abs(a).max()
    idx = np.where(np.abs(a) > thr)[0]
    if len(idx): a = a[max(0, idx[0] - 2400): idx[-1] + 2400]  # margem de 100 ms: não corta consoante fraca no início
    a = a / (np.abs(a).max() + 1e-6) * 0.9
    enc = lameenc.Encoder(); enc.set_bit_rate(40); enc.set_in_sample_rate(sr); enc.set_channels(1); enc.set_quality(2)
    return enc.encode((a * 32767).astype(np.int16).tobytes()) + enc.flush()

def falar(texto):  # texto que soa natural para o rótulo
    return re.sub(r"[_]", " ", texto)

pipe = KPipeline(lang_code="p", device="cuda")
def synth(texto, voz):
    for t in (texto, texto + ".", texto.replace("-", " ") + "."):
        chunks = [x.audio.numpy() for x in pipe(t, voice=voz, speed=1.0) if x.audio is not None]
        if chunks: return np.concatenate(chunks)
    return None
falhas = []
for g, voz in VOZES.items():
    out = DOCS / "audio" / g; out.mkdir(parents=True, exist_ok=True)
    for v in vocab:
        f = out / f"{v['id']}.mp3"
        if f.exists(): continue
        a = synth(falar(v["label"]), voz)
        if a is None: falhas.append(v["label"]); continue
        f.write_bytes(mp3(a))
    for i, t in enumerate(ZULI):
        if (out / f"zuli_{i}.mp3").exists(): continue
        (out / f"zuli_{i}.mp3").write_bytes(mp3(synth(t, voz)))
    print(g, "falhas:", falhas); falhas.clear()
    print(g, "ok", sum(p.stat().st_size for p in out.glob("*.mp3")) // 1024, "KB", flush=True)

# inteligibilidade: Whisper transcreve cada palavra
import warnings; warnings.filterwarnings("ignore")
from transformers import pipeline
import subprocess, unicodedata
asr = pipeline("automatic-speech-recognition", "openai/whisper-medium", device=0)
def norm(s): return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn" and (c.isalnum() or c == " ")).strip()
res = {}
for g in VOZES:
    ok = 0; bad = []
    for v in vocab:
        if not (DOCS / "audio" / g / f"{v['id']}.mp3").exists(): continue
        raw = subprocess.run(["ffmpeg", "-loglevel", "quiet", "-i", str(DOCS / "audio" / g / f"{v['id']}.mp3"), "-f", "f32le", "-ac", "1", "-ar", "16000", "-"], capture_output=True).stdout
        pad = np.zeros(8000, dtype=np.float32)  # 0,5 s de silêncio em volta: o Whisper erra menos em palavra solta
        t = asr(np.concatenate([pad, np.frombuffer(raw, dtype=np.float32), pad]), generate_kwargs=dict(language="portuguese", task="transcribe"))["text"]
        hit = norm(v["label"]) in norm(t) or norm(t) in norm(v["label"]) and norm(t)
        ok += bool(hit)
        if not hit: bad.append([v["label"], t.strip()])
    res[g] = dict(acerto=round(ok / len(vocab) * 100, 1), erros=bad)
    print(g, "inteligibilidade", res[g]["acerto"], "%", flush=True)
json.dump(res, open(R / "out" / "audio_check.json", "w"), ensure_ascii=False, indent=1)
