"""Foto → prancha: pré-calcula o lado de texto do CLIP para os pictogramas concretos.

No aparelho, só o lado de imagem do CLIP roda (transformers.js, Xenova/clip-vit-base-patch32, mesmos pesos
de openai/clip-vit-base-patch32). A foto é comparada com estes vetores e os pictogramas mais parecidos
viram uma prancha temporária.
Saída: docs/data/clip_texto.bin (float16, N×512) e docs/data/clip_ids.json
Uso: python clip_textos.py [--testar foto1.jpg foto2.jpg ...]
"""
import json, sys, pathlib
import numpy as np, torch
from transformers import CLIPModel, CLIPProcessor

R = pathlib.Path(__file__).resolve().parent; DOCS = R.parent.parent / "docs"
D = json.load(open(R / "out" / "dataset.json", encoding="utf-8"))
en = {v["id"]: v.get("en", []) for v in D["vocab"]}
vocab = json.load(open(DOCS / "data" / "vocab.json", encoding="utf-8"))
PRONOMES = {"eu", "você", "ele", "ela", "nós", "eles", "elas", "meu", "seu", "comigo", "alguém", "todo mundo", "todos"}
# só o que dá para ver numa foto: coisas, lugares, ações e pessoas (menos pronomes)
alvo = [w for w in vocab if w["cor"] in ("coisa", "lugar", "acao", "pessoa") and w["label"] not in PRONOMES and en.get(w["id"])]

modelo = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").eval()
proc = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
MODELOS = ["a photo of {}.", "a picture of a {}.", "children and {}."]
with torch.no_grad():
    vets = []
    for w in alvo:
        termo = en[w["id"]][0]
        frases = [m.format(termo) for m in MODELOS]
        t = modelo.get_text_features(**proc(text=frases, return_tensors="pt", padding=True))
        t = t / t.norm(dim=-1, keepdim=True); m = t.mean(0); vets.append((m / m.norm()).numpy())
M = np.stack(vets).astype(np.float16)
M.tofile(DOCS / "data" / "clip_texto.bin")
json.dump([w["id"] for w in alvo], open(DOCS / "data" / "clip_ids.json", "w"))
print(len(alvo), "pictogramas,", (DOCS / "data" / "clip_texto.bin").stat().st_size // 1024, "KB")

if "--testar" in sys.argv:
    from PIL import Image
    for f in sys.argv[sys.argv.index("--testar") + 1:]:
        with torch.no_grad():
            im = modelo.get_image_features(**proc(images=Image.open(f).convert("RGB"), return_tensors="pt"))
        im = (im / im.norm(dim=-1, keepdim=True))[0].numpy()
        s = M.astype(np.float32) @ im
        top = np.argsort(-s)[:15]
        print(pathlib.Path(f).name, "→", ", ".join(alvo[i]["label"] for i in top))
