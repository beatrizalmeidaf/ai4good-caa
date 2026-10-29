"""Baixa os PNGs (300px) do vocabulário v2 para docs/pictos e gera folhas de contato para revisão."""
import json, pathlib, sys
from concurrent.futures import ThreadPoolExecutor
import requests
from PIL import Image, ImageDraw, ImageFont
R = pathlib.Path(__file__).resolve().parent
PIC = R / "out" / "pictos_png"  # originais em PNG (fora do site); o site usa docs/p/*.webp
PIC.mkdir(parents=True, exist_ok=True)
vocab = json.load(open(R.parent.parent / "docs" / "data" / "vocab.json"))

def get(pid):
    f = PIC / f"{pid}.png"
    if f.exists() and f.stat().st_size > 500: return True
    for url in (f"https://static.arasaac.org/pictograms/{pid}/{pid}_300.png",
                f"https://api.arasaac.org/v1/pictograms/{pid}?resolution=300&download=false"):
        try:
            r = requests.get(url, timeout=30)
            if r.status_code == 200 and r.headers.get("content-type") == "image/png":
                f.write_bytes(r.content); return True
        except Exception: pass
    return False

with ThreadPoolExecutor(16) as ex: ok = list(ex.map(get, [v["id"] for v in vocab]))
print("baixados", sum(ok), "de", len(vocab), "falhas:", [v["id"] for v, o in zip(vocab, ok) if not o])

if "--folhas" in sys.argv:
    C, S = 14, 110
    try: font = ImageFont.truetype("DejaVuSans.ttf", 12)
    except Exception: font = ImageFont.load_default()
    out = R / "out" / "folhas"; out.mkdir(exist_ok=True)
    per = C * 10
    for k in range(0, len(vocab), per):
        part = vocab[k:k + per]
        img = Image.new("RGB", (C * S, ((len(part) + C - 1) // C) * (S + 16)), "white"); d = ImageDraw.Draw(img)
        for i, v in enumerate(part):
            x, y = (i % C) * S, (i // C) * (S + 16)
            try:
                p = Image.open(PIC / f"{v['id']}.png").convert("RGBA").resize((S - 12, S - 12)); img.paste(p, (x + 6, y + 2), p)
            except Exception: pass
            d.text((x + 3, y + S - 8), f"{v['label'][:16]}", fill="black", font=font)
        img.save(out / f"folha_{k // per:02d}.png")
    print("folhas em", out)
