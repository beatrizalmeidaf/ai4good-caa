import json, pathlib
from PIL import Image, ImageDraw, ImageFont
R = pathlib.Path(__file__).resolve().parent.parent
rows = json.load(open(R/"experiments/results/01_cobertura.json"))
C, S = 12, 130
img = Image.new("RGB", (C*S, ((len(rows)+C-1)//C)*(S+18)), "white")
d = ImageDraw.Draw(img)
try: f = ImageFont.truetype("DejaVuSans.ttf", 13)
except Exception: f = ImageFont.load_default()
for i, r in enumerate(rows):
    x, y = (i % C)*S, (i//C)*(S+18)
    p = Image.open(R/f"docs/pictos/{r['arasaac_id']}.png").convert("RGBA").resize((S-14, S-14))
    img.paste(p, (x+7, y+2), p)
    d.text((x+4, y+S-8), r["label"][:17], fill="red" if r["mode"]=="curado" else "black", font=f)
img.save(R/"experiments/results/contact_sheet.png")
