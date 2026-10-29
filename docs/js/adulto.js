// O adulto fala com a criança: segura o botão do microfone, fala ("quer suco ou água?") e solta.
// O que ele disse vira pictogramas, e o modelo usa isso para sugerir a resposta da criança.
// 1º: reconhecimento de fala do próprio aparelho (ditado do iPhone/iPad/Android): rápido, sem baixar nada.
// 2º (computador sem isso): Whisper no navegador. Em celular/tablet o Whisper não é usado (pesa demais e o navegador fecha a aba).
const ASR_MODELO = "onnx-community/whisper-base";
const LIB = "https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.5.1";
const Nativo = window.SpeechRecognition || window.webkitSpeechRecognition;
const movel = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
export const podeOuvir = () => !!Nativo || (!movel && !!navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== "undefined");
export const precisaBaixar = () => !Nativo;
let asrP = null;

export function carregarEscuta(progresso) {
  if (Nativo) return Promise.resolve(null);
  if (asrP) return asrP;
  asrP = (async () => {
    const T = await import(LIB);
    return T.pipeline("automatic-speech-recognition", ASR_MODELO, {
      device: "wasm", dtype: "q8",
      progress_callback: p => { if (p.status === "progress" && p.total) progresso?.(p.loaded / p.total); },
    });
  })();
  asrP.catch(() => { asrP = null; });
  return asrP;
}

// Começa a ouvir enquanto o botão está apertado. parar() devolve o texto (ou "" se não ouviu nada).
export async function comecarEscuta() {
  if (Nativo) {
    const r = new Nativo(); r.lang = "pt-BR"; r.continuous = true; r.interimResults = true; r.maxAlternatives = 1;
    let texto = "", erro = null, fim;
    const acabou = new Promise(res => fim = res);
    r.onresult = e => { texto = [...e.results].map(x => x[0].transcript).join(" ").trim(); };
    r.onerror = e => { erro = e.error; };
    r.onend = () => fim();
    r.start();
    return async function parar() {
      try { r.stop(); } catch {}
      await Promise.race([acabou, new Promise(res => setTimeout(res, 2500))]);
      if (!texto && erro && erro !== "no-speech" && erro !== "aborted") throw new Error(erro);
      return texto;
    };
  }
  const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
  const rec = new MediaRecorder(stream), partes = [], t0 = performance.now();
  rec.ondataavailable = e => partes.push(e.data);
  rec.start();
  return async function parar() {
    rec.stop(); await new Promise(r => rec.onstop = r);
    stream.getTracks().forEach(t => t.stop());
    if (performance.now() - t0 < 500) return "";
    const ac = new (window.AudioContext || window.webkitAudioContext)();
    const dec = await ac.decodeAudioData(await new Blob(partes).arrayBuffer()); ac.close();
    const off = new OfflineAudioContext(1, Math.ceil(dec.duration * 16000), 16000);
    const s = off.createBufferSource(); s.buffer = dec; s.connect(off.destination); s.start();
    const audio = (await off.startRendering()).getChannelData(0);
    const asr = await carregarEscuta();
    return ((await asr(audio, { language: "portuguese", task: "transcribe" })).text || "").trim();
  };
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
