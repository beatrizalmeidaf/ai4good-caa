// O adulto fala com a criança: segura o botão do microfone, fala ("quer suco ou água?") e solta.
// O Whisper (no navegador, nada sai do aparelho) escreve o que ouviu; as palavras viram pictogramas
// e o modelo usa isso para sugerir a resposta da criança.
const ASR_MODELO = "onnx-community/whisper-base";
const LIB = "https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.5.1";
let asrP = null;

export function carregarEscuta(progresso) {
  if (asrP) return asrP;
  asrP = (async () => {
    const T = await import(LIB);
    const device = navigator.gpu && (await navigator.gpu.requestAdapter().catch(() => null)) ? "webgpu" : "wasm";
    return T.pipeline("automatic-speech-recognition", ASR_MODELO, {
      device, dtype: device === "webgpu" ? { encoder_model: "fp32", decoder_model_merged: "q4" } : "q8",
      progress_callback: p => { if (p.status === "progress" && p.total) progresso?.(p.loaded / p.total); },
    });
  })();
  asrP.catch(() => { asrP = null; });
  return asrP;
}

// Grava enquanto o botão está apertado. parar() devolve áudio mono 16 kHz (ou null se foi curto demais).
export async function comecarGravacao() {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
  const rec = new MediaRecorder(stream), partes = [], t0 = performance.now();
  rec.ondataavailable = e => partes.push(e.data);
  rec.start();
  return async function parar() {
    rec.stop(); await new Promise(r => rec.onstop = r);
    stream.getTracks().forEach(t => t.stop());
    if (performance.now() - t0 < 500) return null;
    const ac = new (window.AudioContext || window.webkitAudioContext)();
    const dec = await ac.decodeAudioData(await new Blob(partes).arrayBuffer()); ac.close();
    const off = new OfflineAudioContext(1, Math.ceil(dec.duration * 16000), 16000);
    const s = off.createBufferSource(); s.buffer = dec; s.connect(off.destination); s.start();
    return (await off.startRendering()).getChannelData(0);
  };
}

export async function transcrever(audio) {
  const asr = await carregarEscuta();
  const r = await asr(audio, { language: "portuguese", task: "transcribe" });
  return (r.text || "").trim();
}

// Tipo da fala do adulto (o mesmo conjunto do treino), pelas palavras-chave.
export function tipoDaFala(texto) {
  const t = " " + texto.toLowerCase().normalize("NFD").replace(/\p{Mn}/gu, "").replace(/[^a-z ]/g, " ") + " ";
  const tem = (...w) => w.some(x => t.includes(" " + x + " "));
  if (tem("oi", "ola", "tchau", "bom dia", "boa tarde", "boa noite")) return "cumprimento";
  if (tem("aconteceu", "houve")) return "o_que_aconteceu";
  if (tem("quem")) return "quem";
  if (tem("onde", "cade")) return "onde";
  if (tem("como") && tem("esta", "ta", "voce esta", "se sente", "sente")) return "como_esta";
  if (tem("gostou", "gosta", "gostaste", "achou")) return "gosta";
  if (tem("quer", "queres", "querer") && tem("o que", "qual", "ou")) return "o_que_quer";
  if (tem("vamos", "fazer", "brincar de")) return "o_que_fazer";
  if (tem("quer", "queres", "pode", "posso", "esta", "foi", "tem", "vai", "precisa")) return "sim_nao";
  return "comentario";
}
