"""Compara vozes de TTS abertas para o Zuli.

Para cada voz: gera as palavras de teste e as frases de amostra, mede a
inteligibilidade (o Whisper reconhece a palavra?) e o tempo de geração.
Saída: docs/vozes/<voz>/<n>.mp3 (amostras para ouvir) e out/vozes.json.

Vozes:
  kokoro-f / kokoro-m : atual (Kokoro-82M), só palavras já geradas
  piper-*             : Piper pt_BR (VITS, leve)
  xtts-*              : XTTS-v2 clonando uma voz de referência (leitura LibriVox, MLS pt, CC BY 4.0)
  *-jovem             : mesma voz com tom 3 semitons mais alto (efeito mais jovem)
Uso: python comparar_vozes.py <pasta_com_referencias> <palavras.json>
"""
import json, os, sys, time, pathlib, subprocess, urllib.request, unicodedata
import numpy as np, soundfile as sf, lameenc

R = pathlib.Path(__file__).resolve().parent
DOCS = R.parent.parent / "docs"
REF = pathlib.Path(sys.argv[1]); PAL = json.load(open(sys.argv[2]))
OUTV = DOCS / "vozes"; OUTV.mkdir(exist_ok=True)
FFMPEG = str(pathlib.Path.home() / "bin" / "ffmpeg")
vocab = {v["label"]: v["id"] for v in json.load(open(DOCS / "data" / "vocab.json"))}

def mp3(a, sr):
    a = a.astype(np.float32); a = a / (np.abs(a).max() + 1e-6) * 0.9
    e = lameenc.Encoder(); e.set_bit_rate(48); e.set_in_sample_rate(sr); e.set_channels(1); e.set_quality(2)
    return e.encode((a * 32767).astype(np.int16).tobytes()) + e.flush()

def tom(a, sr, semitons=3):
    """sobe o tom sem mudar a duração (ffmpeg rubberband não está disponível: asetrate + atempo)."""
    f = 2 ** (semitons / 12)
    p = subprocess.run([FFMPEG, "-loglevel", "quiet", "-f", "f32le", "-ar", str(sr), "-ac", "1", "-i", "-",
                        "-af", f"asetrate={int(sr * f)},aresample={sr},atempo={1 / f:.4f}", "-f", "f32le", "-"],
                       input=a.astype(np.float32).tobytes(), capture_output=True)
    return np.frombuffer(p.stdout, dtype=np.float32)

# ---------------- motores ----------------
def piper_voz(nome):
    from piper import PiperVoice
    base = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/{nome.split('-')[0]}/{nome.split('-')[1]}/pt_BR-{nome}.onnx"
    d = R / "out" / "piper"; d.mkdir(parents=True, exist_ok=True)
    for ext in ("", ".json"):
        f = d / f"pt_BR-{nome}.onnx{ext}"
        if not f.exists(): urllib.request.urlretrieve(base + ext, f)
    v = PiperVoice.load(str(d / f"pt_BR-{nome}.onnx"))
    def gerar(texto):
        partes = [np.frombuffer(c.audio_int16_bytes, dtype=np.int16) for c in v.synthesize(texto)]
        return np.concatenate(partes).astype(np.float32) / 32768, v.config.sample_rate
    return gerar

_xtts = None
def xtts_voz(ref_wav):
    global _xtts
    from TTS.api import TTS
    if _xtts is None: _xtts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cuda")
    lat = _xtts.synthesizer.tts_model.get_conditioning_latents(audio_path=[str(ref_wav)])
    def gerar(texto):
        out = _xtts.synthesizer.tts_model.inference(texto, "pt", lat[0], lat[1], temperature=0.3, enable_text_splitting=False)
        return np.array(out["wav"], dtype=np.float32), 24000
    return gerar

def kokoro_existente(g):
    def gerar(texto):
        pid = vocab.get(texto)
        if pid is None: return None, None
        raw = subprocess.run([FFMPEG, "-loglevel", "quiet", "-i", str(DOCS / "audio" / g / f"{pid}.mp3"), "-f", "f32le", "-ac", "1", "-ar", "24000", "-"], capture_output=True).stdout
        return np.frombuffer(raw, dtype=np.float32), 24000
    return gerar

# ---------------- avaliação ----------------
def norm(s): return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn" and (c.isalnum() or c == " ")).strip()
from transformers import pipeline
asr = pipeline("automatic-speech-recognition", "openai/whisper-medium", device=0)
def reconhece(a, sr, alvo):
    raw = subprocess.run([FFMPEG, "-loglevel", "quiet", "-f", "f32le", "-ar", str(sr), "-ac", "1", "-i", "-", "-f", "f32le", "-ar", "16000", "-"],
                         input=a.astype(np.float32).tobytes(), capture_output=True).stdout
    x = np.concatenate([np.zeros(8000, np.float32), np.frombuffer(raw, dtype=np.float32), np.zeros(8000, np.float32)])
    t = asr(x, generate_kwargs=dict(language="portuguese", task="transcribe"))["text"]
    return norm(alvo) in norm(t), t.strip()

VOZES = {
    "kokoro-f": lambda: kokoro_existente("f"), "kokoro-m": lambda: kokoro_existente("m"),
    "piper-faber": lambda: piper_voz("faber-medium"), "piper-cadu": lambda: piper_voz("cadu-medium"),
    "piper-jeff": lambda: piper_voz("jeff-medium"),
}
if os.environ.get("SO_XTTS"): VOZES = {}
for f in sorted(REF.glob("*.wav")):
    VOZES[f"xtts-{f.stem}"] = (lambda f=f: xtts_voz(f))

SAIDA = R / "out" / os.environ.get("VOZES_OUT", "vozes.json")
resultado = json.load(open(SAIDA)) if SAIDA.exists() else {}
for nome, fab in VOZES.items():
    if nome in resultado: continue
    try: gerar = fab()
    except Exception as e: print(nome, "falhou:", e, flush=True); continue
    ok, tot, tempos, erros = 0, 0, [], []
    for w in PAL["teste"]:
        t0 = time.time(); a, sr = gerar(w); tempos.append(time.time() - t0)
        if a is None or not len(a): continue
        hit, t = reconhece(a, sr, w); ok += hit; tot += 1
        if not hit: erros.append([w, t])
    d = OUTV / nome; d.mkdir(exist_ok=True)
    for i, frase in enumerate(PAL["amostra"]):
        a, sr = gerar(frase)
        if a is None: continue
        (d / f"{i}.mp3").write_bytes(mp3(a, sr))
        if nome.startswith("xtts") or nome.startswith("piper"):
            dj = OUTV / f"{nome}-jovem"; dj.mkdir(exist_ok=True)
            (dj / f"{i}.mp3").write_bytes(mp3(tom(a, sr), sr))
    resultado[nome] = dict(acerto=round(100 * ok / max(tot, 1), 1), n=tot, ms_por_palavra=round(1000 * float(np.median(tempos)), 0), erros=erros[:40])
    print(nome, resultado[nome]["acerto"], "%", resultado[nome]["ms_por_palavra"], "ms", flush=True)
    json.dump(resultado, open(SAIDA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(PAL["amostra"], open(OUTV / "frases.json", "w", encoding="utf-8"), ensure_ascii=False)
