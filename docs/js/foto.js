// Foto → prancha: o CLIP (lado da imagem) roda no aparelho e compara a foto com os pictogramas.
// A foto não sai do aparelho. Na primeira vez baixa ~90 MB (fica guardado).
import { f16to32 } from "./slm.js";

const LIB = "https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.5.1";
const MODELO = "Xenova/clip-vit-base-patch32";
let pronto = null;

export function carregarVisao(progresso, base = "data/") {
  if (pronto) return pronto;
  pronto = (async () => {
    const T = await import(LIB);
    const cb = p => { if (p.status === "progress" && p.total) progresso?.(p.loaded / p.total); };
    const [proc, model, ids, buf] = await Promise.all([
      T.AutoProcessor.from_pretrained(MODELO, { progress_callback: cb }),
      T.CLIPVisionModelWithProjection.from_pretrained(MODELO, { dtype: "q8", progress_callback: cb }),
      fetch(base + "clip_ids.json").then(r => r.json()),
      fetch(base + "clip_texto.bin").then(r => r.arrayBuffer()),
    ]);
    return { T, proc, model, ids, M: f16to32(new Uint16Array(buf)) };
  })();
  pronto.catch(() => { pronto = null; });
  return pronto;
}

// devolve [{id, nota}] do pictograma mais parecido com a foto ao menos parecido
export async function analisarFoto(arquivo, progresso, base) {
  const { T, proc, model, ids, M } = await carregarVisao(progresso, base);
  const img = await T.RawImage.fromBlob(arquivo);
  const { image_embeds } = await model(await proc(img));
  const v = image_embeds.data, D = v.length;
  let n = 0; for (let i = 0; i < D; i++) n += v[i] * v[i]; n = Math.sqrt(n);
  return ids.map((id, k) => { let s = 0; for (let i = 0; i < D; i++) s += M[k * D + i] * v[i]; return { id, nota: s / n }; })
    .sort((a, b) => b.nota - a.nota);
}

// miniatura pequena da foto (guardada no aparelho para o ícone da aba)
export async function miniatura(arquivo, lado = 96) {
  const bmp = await createImageBitmap(arquivo);
  const c = document.createElement("canvas"); c.width = c.height = lado;
  const s = Math.min(bmp.width, bmp.height);
  c.getContext("2d").drawImage(bmp, (bmp.width - s) / 2, (bmp.height - s) / 2, s, s, 0, 0, lado, lado);
  return c.toDataURL("image/jpeg", 0.7);
}
