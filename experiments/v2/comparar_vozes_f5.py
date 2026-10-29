"""F5-TTS pt-BR (firstpixel/F5-TTS-pt-br, CC BY-NC 4.0) no mesmo protocolo de comparar_vozes.py.

Uso: python comparar_vozes_f5.py <pasta_com_referencias> <palavras.json>
Saída: docs/vozes/f5-<ref>/<n>.mp3, docs/vozes/f5-<ref>-jovem/<n>.mp3, out/vozes_f5.json
"""
import json, os, sys, time, pathlib, subprocess, unicodedata
import numpy as np, soundfile as sf
from huggingface_hub import hf_hub_download

R = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(R))
DOCS = R.parent.parent / "docs"; OUTV = DOCS / "vozes"
REF = pathlib.Path(sys.argv[1]); PAL = json.load(open(sys.argv[2]))
FFMPEG = str(pathlib.Path.home() / "bin" / "ffmpeg")

def mp3(a, sr):
    import lameenc
    a = a.astype(np.float32); a = a / (np.abs(a).max() + 1e-6) * 0.9
    e = lameenc.Encoder(); e.set_bit_rate(48); e.set_in_sample_rate(sr); e.set_channels(1); e.set_quality(2)
    return e.encode((a * 32767).astype(np.int16).tobytes()) + e.flush()

def tom(a, sr, semitons=3):
    f = 2 ** (semitons / 12)
    p = subprocess.run([FFMPEG, "-loglevel", "quiet", "-f", "f32le", "-ar", str(sr), "-ac", "1", "-i", "-",
                        "-af", f"asetrate={int(sr * f)},aresample={sr},atempo={1 / f:.4f}", "-f", "f32le", "-"],
                       input=a.astype(np.float32).tobytes(), capture_output=True)
    return np.frombuffer(p.stdout, dtype=np.float32)

from f5_tts.api import F5TTS
ckpt = hf_hub_download("firstpixel/F5-TTS-pt-br", "pt-br/model_last.safetensors")
tts = F5TTS(model="F5TTS_Base", ckpt_file=ckpt, device="cuda")

def norm(s): return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn" and (c.isalnum() or c == " ")).strip()
from transformers import pipeline
asr = pipeline("automatic-speech-recognition", "openai/whisper-medium", device=0)
def reconhece(a, sr, alvo):
    raw = subprocess.run([FFMPEG, "-loglevel", "quiet", "-f", "f32le", "-ar", str(sr), "-ac", "1", "-i", "-", "-f", "f32le", "-ar", "16000", "-"],
                         input=a.astype(np.float32).tobytes(), capture_output=True).stdout
    x = np.concatenate([np.zeros(8000, np.float32), np.frombuffer(raw, dtype=np.float32), np.zeros(8000, np.float32)])
    t = asr(x, generate_kwargs=dict(language="portuguese", task="transcribe"))["text"]
    return norm(alvo) in norm(t), t.strip()

saida = R / "out" / os.environ.get("VOZES_OUT", "vozes_f5.json")
res = json.load(open(saida)) if saida.exists() else {}
for ref in sorted(REF.glob("*.wav")):
    if f"f5-{ref.stem}" in res: continue  # já feita
    curto = R / "out" / f"ref10_{ref.stem}.wav"
    subprocess.run([FFMPEG, "-loglevel", "quiet", "-y", "-i", str(ref), "-t", "10", "-ac", "1", "-ar", "24000", str(curto)])
    x16 = np.frombuffer(subprocess.run([FFMPEG, "-loglevel", "quiet", "-i", str(curto), "-f", "f32le", "-ac", "1", "-ar", "16000", "-"], capture_output=True).stdout, dtype=np.float32)
    ref_text = asr(x16.copy(), generate_kwargs=dict(language="portuguese", task="transcribe"))["text"].strip().lower()
    def gerar(texto):
        wav, sr, _ = tts.infer(ref_file=str(curto), ref_text=ref_text, gen_text=texto.lower() + ".", remove_silence=True, speed=0.95, nfe_step=32)
        return np.asarray(wav, dtype=np.float32), sr
    nome = f"f5-{ref.stem}"
    ok, tot, tempos, erros = 0, 0, [], []
    for w in PAL["teste"]:
        t0 = time.time(); a, sr = gerar(w); tempos.append(time.time() - t0)
        hit, t = reconhece(a, sr, w); ok += hit; tot += 1
        if not hit: erros.append([w, t])
    for pasta, f in ((nome, lambda a, sr: a), (nome + "-jovem", tom)):
        (OUTV / pasta).mkdir(parents=True, exist_ok=True)
    for i, frase in enumerate(PAL["amostra"]):
        a, sr = gerar(frase)
        (OUTV / nome / f"{i}.mp3").write_bytes(mp3(a, sr))
        (OUTV / f"{nome}-jovem" / f"{i}.mp3").write_bytes(mp3(tom(a, sr), sr))
    res[nome] = dict(acerto=round(100 * ok / tot, 1), n=tot, ms_por_palavra=round(1000 * float(np.median(tempos))), erros=erros[:40], ref_text=ref_text)
    print(nome, res[nome]["acerto"], "%", res[nome]["ms_por_palavra"], "ms", flush=True)
    json.dump(res, open(saida, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
