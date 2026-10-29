"""Gera o áudio de cada pictograma com XTTS-v2 clonando uma voz de referência, com tom mais jovem.

Para cada palavra tenta até 3 vezes e fica com a primeira versão que o Whisper reconhece
e que não tem som sobrando (palavra solta às vezes sai com ruído extra no XTTS).
Uso: python gerar_audio_xtts.py <f|m> <referencia.wav> [semitons=3] [--tudo]
Saída: docs/audio/<f|m>/<id>.mp3, docs/audio/<f|m>/zuli_<n>.mp3, out/audio_xtts_<g>.json
"""
import json, sys, time, pathlib, subprocess, unicodedata
import numpy as np, lameenc, torch

R = pathlib.Path(__file__).resolve().parent; DOCS = R.parent.parent / "docs"
FFMPEG = str(pathlib.Path.home() / "bin" / "ffmpeg")
G, REF = sys.argv[1], sys.argv[2]; SEMI = float(sys.argv[3]) if len(sys.argv) > 3 and not sys.argv[3].startswith("--") else 3
OUT = DOCS / "audio" / G; OUT.mkdir(parents=True, exist_ok=True)
vocab = json.load(open(DOCS / "data" / "vocab.json", encoding="utf-8"))
ZULI = json.load(open(DOCS / "data" / "zuli_falas.json", encoding="utf-8"))

from TTS.api import TTS
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cuda")
m = tts.synthesizer.tts_model
lat = m.get_conditioning_latents(audio_path=[REF])
from transformers import pipeline
asr = pipeline("automatic-speech-recognition", "openai/whisper-medium", device=0)

def norm(s): return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn" and (c.isalnum() or c == " ")).strip()
def ff(a, sr_in, filtro, sr_out):
    p = subprocess.run([FFMPEG, "-loglevel", "quiet", "-f", "f32le", "-ar", str(sr_in), "-ac", "1", "-i", "-", "-af", filtro, "-f", "f32le", "-ar", str(sr_out), "-"],
                       input=a.astype(np.float32).tobytes(), capture_output=True)
    return np.frombuffer(p.stdout, dtype=np.float32)
def aparar(a, sr=24000):
    thr = 0.02 * np.abs(a).max(); idx = np.where(np.abs(a) > thr)[0]
    return a[max(0, idx[0] - int(.05 * sr)): idx[-1] + int(.12 * sr)] if len(idx) else a
def mais_jovem(a, sr=24000):
    f = 2 ** (SEMI / 12)
    return ff(a, sr, f"asetrate={int(sr * f)},aresample={sr},atempo={1 / f:.4f}", sr) if SEMI else a
def mp3(a, sr=24000):
    a = a / (np.abs(a).max() + 1e-6) * 0.9
    e = lameenc.Encoder(); e.set_bit_rate(40); e.set_in_sample_rate(sr); e.set_channels(1); e.set_quality(2)
    return e.encode((a * 32767).astype(np.int16).tobytes()) + e.flush()
def reconhece(a, alvo):
    x = ff(a, 24000, "anull", 16000)
    t = asr(np.concatenate([np.zeros(8000, np.float32), x, np.zeros(8000, np.float32)]), generate_kwargs=dict(language="portuguese", task="transcribe"))["text"]
    return limpo(t, alvo), t.strip()
def limpo(t, alvo):
    """a fala é só a palavra: sem 'ponto', número ou palavra a mais."""
    tt, aa = norm(t).replace("-", " ").split(), norm(alvo).replace("-", " ").split()
    if any(ch.isdigit() for ch in t) or "ponto" in tt and "ponto" not in aa: return False
    return aa == tt or (len(tt) == len(aa) and all(a2[:3] == t2[:3] for a2, t2 in zip(aa, tt)))

def sintetizar(texto, temp):
    torch.manual_seed(int(temp * 100))
    out = m.inference(texto, "pt", lat[0], lat[1], temperature=temp, enable_text_splitting=False, repetition_penalty=5.0)
    return np.array(out["wav"], dtype=np.float32)

stats = dict(ok=0, total=0, tentativas=0, falhas=[])
itens = [(str(v["id"]), v["label"], True) for v in vocab] + [(f"zuli_{i}", t, False) for i, t in enumerate(ZULI)]
t0 = time.time()
TUDO = "--tudo" in sys.argv  # sem --tudo, só gera o que ainda não tem áudio (palavras novas)
REFAZER = "--refazer-ruins" in sys.argv  # transcreve os áudios existentes e refaz os que têm sobra
def existente(chave):
    raw = subprocess.run([FFMPEG, "-loglevel", "quiet", "-i", str(OUT / f"{chave}.mp3"), "-f", "f32le", "-ac", "1", "-ar", "24000", "-"], capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32)
ruins = []
for chave, texto, palavra in itens:
    if REFAZER and palavra and (OUT / f"{chave}.mp3").exists():
        ok_atual, t_atual = reconhece(existente(chave), texto)
        if ok_atual: continue
        ruins.append([texto, t_atual])
    elif not TUDO and (OUT / f"{chave}.mp3").exists(): continue
    falado = texto.replace("_", " ")
    melhor, ok = None, False
    tentativas = [(falado, 0.3), (falado, 0.55), (falado, 0.75), (falado, 0.9)]
    if REFAZER: tentativas = [(falado, 0.45), (falado, 0.65), (falado, 0.85), (falado + "!", 0.5), (falado + "?", 0.6), (falado, 1.0)]
    for k, (variante, temp) in enumerate(tentativas if palavra else [(falado, 0.3)]):
        a = aparar(sintetizar(variante, temp)); stats["tentativas"] += 1
        if melhor is None: melhor = a
        longo = palavra and len(a) / 24000 > 0.9 + 0.12 * len(falado)  # som sobrando
        if longo: continue
        hit, _ = reconhece(a, texto)
        if hit or not palavra: melhor, ok = a, True; break
    stats["total"] += 1; stats["ok"] += ok
    if not ok: stats["falhas"].append(texto)
    (OUT / f"{chave}.mp3").write_bytes(mp3(mais_jovem(melhor)))
    if stats["total"] % 100 == 0: print(stats["total"], "itens", f"{time.time() - t0:.0f}s", flush=True)
stats["acerto"] = round(100 * stats["ok"] / max(1, stats["total"]), 1); stats["ruins_encontrados"] = ruins
json.dump(stats, open(R / "out" / f"audio_xtts_{G}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("pronto:", stats["acerto"], "% reconhecido,", stats["tentativas"], "sínteses,", f"{time.time() - t0:.0f}s")
