"""Confere o FIM dos áudios: 'ponto' lido no final e som sobrando (alucinação do TTS depois da palavra).

O Whisper costuma escrever o "ponto" falado como "." — por isso a transcrição sozinha não pega.
Aqui:
  1) pontuação lida: compara a probabilidade (Whisper, forçando o texto) de "água" e de "água ponto" / "água 1.1"...
  2) som sobrando: trechos de fala separados por pausa > 0,18 s, mais trechos do que palavras;
  3) transcrição tem que ser a palavra.
Se der para consertar cortando o final, devolve o áudio cortado.

Uso: python checar_fim.py <pasta: f|mc> [--cortar]    → out/fim_<pasta>.json (lista do que continua ruim)
"""
import json, sys, pathlib, subprocess, unicodedata, time
import numpy as np, torch

R = pathlib.Path(__file__).resolve().parent; DOCS = R.parent.parent / "docs"
FFMPEG = str(pathlib.Path.home() / "bin" / "ffmpeg")

def norm(s): return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn" and (c.isalnum() or c == " ")).strip()
NUM = {"zero": "0", "um": "1", "dois": "2", "três": "3", "quatro": "4", "cinco": "5", "seis": "6", "sete": "7", "oito": "8", "nove": "9", "dez": "10",
       "onze": "11", "doze": "12", "treze": "13", "catorze": "14", "quatorze": "14", "quinze": "15", "dezesseis": "16", "dezessete": "17",
       "dezoito": "18", "dezenove": "19", "vinte": "20", "cem": "100", "mil": "1000"}
def limpo(t, alvo):
    if alvo.lower() in NUM and "".join(ch for ch in t if ch.isdigit()) == NUM[alvo.lower()] and len(norm(t).split()) == 1: return True
    tt, aa = norm(t).replace("-", " ").split(), norm(alvo).replace("-", " ").split()
    if any(ch.isdigit() for ch in t) or "ponto" in tt and "ponto" not in aa: return False
    return aa == tt or (len(tt) == len(aa) and all(a2[:3] == t2[:3] for a2, t2 in zip(aa, tt)))

def para16k(a, sr):
    if sr == 16000: return a.astype(np.float32)
    p = subprocess.run([FFMPEG, "-loglevel", "quiet", "-f", "f32le", "-ar", str(sr), "-ac", "1", "-i", "-", "-f", "f32le", "-ar", "16000", "-"],
                       input=a.astype(np.float32).tobytes(), capture_output=True)
    return np.frombuffer(p.stdout, dtype=np.float32)

def segmentos(a, sr, gap=0.18):
    """trechos com som (quadros de 20 ms acima de 6% do pico), juntando pausas menores que `gap`"""
    f = int(0.02 * sr); n = len(a) // f
    if n == 0: return []
    rms = np.sqrt((a[: n * f].reshape(n, f) ** 2).mean(1)); thr = max(0.06 * rms.max(), 1e-4)
    on = rms > thr; segs = []; i = 0
    while i < n:
        if on[i]:
            j = i
            while j < n and on[j]: j += 1
            if segs and (i - segs[-1][1]) * 0.02 < gap: segs[-1][1] = j
            else: segs.append([i, j])
            i = j
        else: i += 1
    segs = [s for s in segs if (s[1] - s[0]) * 0.02 >= 0.04]  # descarta estalos
    return [(s * f, e * f) for s, e in segs]

class Juiz:
    def __init__(s, modelo="openai/whisper-medium", dev="cuda"):
        from transformers import WhisperForConditionalGeneration, WhisperProcessor
        s.proc = WhisperProcessor.from_pretrained(modelo)
        s.m = WhisperForConditionalGeneration.from_pretrained(modelo, torch_dtype=torch.float16).to(dev).eval(); s.dev = dev
        tk = s.proc.tokenizer
        s.pre = tk.convert_tokens_to_ids(["<|startoftranscript|>", "<|pt|>", "<|transcribe|>", "<|notimestamps|>"]); s.eot = tk.eos_token_id
    def _enc(s, x16):
        x = np.concatenate([np.zeros(8000, np.float32), x16, np.zeros(8000, np.float32)])
        feats = s.proc(x, sampling_rate=16000, return_tensors="pt").input_features.to(s.dev, torch.float16)
        with torch.no_grad(): return feats, s.m.model.encoder(feats).last_hidden_state
    def transcrever(s, x16):
        feats, _ = s._enc(x16)
        with torch.no_grad(): ids = s.m.generate(feats, language="portuguese", task="transcribe", max_new_tokens=40)
        return s.proc.batch_decode(ids, skip_special_tokens=True)[0].strip()
    def logprob(s, x16, textos):
        """log-prob total de cada texto (com o fim <eot>) dado o áudio"""
        _, h = s._enc(x16); tk = s.proc.tokenizer
        seqs = [s.pre + tk.encode(" " + t, add_special_tokens=False) + [s.eot] for t in textos]
        L = max(map(len, seqs)); ids = torch.full((len(seqs), L), s.eot, device=s.dev)
        for i, q in enumerate(seqs): ids[i, :len(q)] = torch.tensor(q)
        with torch.no_grad():
            lg = s.m(encoder_outputs=(h.expand(len(seqs), -1, -1),), decoder_input_ids=ids[:, :-1]).logits.float().log_softmax(-1)
        out = []
        for i, q in enumerate(seqs):
            out.append(sum(lg[i, j - 1, q[j]].item() for j in range(len(s.pre), len(q))))
        return out
    def tem_ponto(s, x16, alvo):
        a = alvo[:1].upper() + alvo[1:]
        base = [a + ".", a, a + "!", a + "?"]
        ponto = [a + " ponto.", a + ". Ponto.", a + ", ponto.", a + " 1.1", a + " um ponto um.", a + " ponto de interrogação.", a + " ponto de exclamação.", a + " ponto final."]
        lp = s.logprob(x16, base + ponto)
        return max(lp[len(base):]) > max(lp[: len(base)])

    def avaliar(s, a, sr, alvo):
        """-> (ok, motivo, audio_consertado_ou_None)"""
        x16 = para16k(a, sr)
        t = s.transcrever(x16); ok_t = limpo(t, alvo)
        ponto = s.tem_ponto(x16, alvo)
        segs = segmentos(a, sr); nw = max(1, len(alvo.replace("-", " ").split()))
        sobra = len(segs) > nw
        # "ponto" grudado no fim (sem pausa): transcreve só o último meio segundo
        if not ponto and segs and segs[-1][1] - segs[0][0] >= int(0.7 * sr) and "pont" not in norm(alvo):
            fim = segs[-1][1]; cauda = norm(s.transcrever(para16k(a[max(segs[0][0], fim - int(0.55 * sr)): fim + int(0.05 * sr)], sr)))
            ponto = bool(__import__("re").search(r"\bpo(nto|nte|n)?\b", cauda))
        if ok_t and not ponto and not sobra: return True, "ok", None
        motivo = ",".join(m for m, v in (("transcricao:" + t, not ok_t), ("ponto", ponto), ("sobra", sobra)) if v)
        # conserto: corta antes do último trecho (ou fica com os primeiros `nw` trechos)
        for k in sorted({nw, len(segs) - 1}, reverse=True):
            if 1 <= k < len(segs):
                cut = a[: min(len(a), segs[k - 1][1] + int(0.08 * sr))]
                c16 = para16k(cut, sr)
                if limpo(s.transcrever(c16), alvo) and not s.tem_ponto(c16, alvo): return False, motivo, cut
        return False, motivo, None

def ler_mp3(p, sr=24000):
    raw = subprocess.run([FFMPEG, "-loglevel", "quiet", "-i", str(p), "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"], capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32)
def mp3(a, sr=24000):
    import lameenc
    a = a / (np.abs(a).max() + 1e-6) * 0.9
    e = lameenc.Encoder(); e.set_bit_rate(40); e.set_in_sample_rate(sr); e.set_channels(1); e.set_quality(2)
    return e.encode((a * 32767).astype(np.int16).tobytes()) + e.flush()

if __name__ == "__main__":
    pasta = sys.argv[1]; CORTAR = "--cortar" in sys.argv
    OUT = DOCS / "audio" / pasta
    vocab = json.load(open(DOCS / "data" / "vocab.json", encoding="utf-8"))
    j = Juiz(); t0 = time.time(); ruins, cortados, motivos, motivo_de = [], [], {}, {}
    for k, v in enumerate(vocab):
        p = OUT / f"{v['id']}.mp3"
        if not p.exists(): ruins.append(v["id"]); continue
        a = ler_mp3(p)
        ok, mot, cons = j.avaliar(a, 24000, v["label"])
        if ok: continue
        for m in mot.split(","): motivos[m.split(":")[0]] = motivos.get(m.split(":")[0], 0) + 1
        if cons is not None:
            cortados.append([v["label"], mot])
            if CORTAR: p.write_bytes(mp3(cons))
        else: ruins.append(v["id"]); motivo_de[v["id"]] = mot
        if (k + 1) % 200 == 0: print(k + 1, "conferidos", len(cortados), "cortados", len(ruins), "ruins", f"{time.time() - t0:.0f}s", flush=True)
    res = dict(pasta=pasta, cortados=cortados, ruins=ruins, ruins_rotulos=[next(w["label"] for w in vocab if w["id"] == i) for i in ruins], motivos=motivos,
               refazer=[i for i in ruins if any(m in motivo_de.get(i, "ponto") for m in ("ponto", "sobra"))], motivo_de=motivo_de)
    json.dump(res, open(R / "out" / f"fim_{pasta}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("pronto:", pasta, "cortados", len(cortados), "ainda ruins", len(ruins), motivos, f"{time.time() - t0:.0f}s", flush=True)
