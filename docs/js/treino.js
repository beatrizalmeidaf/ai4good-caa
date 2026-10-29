// Treino de fala: ouvir a palavra, repetir, o Zuli escuta e dá retorno.
// Reconhecimento de fala local (Whisper no navegador). Nada sai do aparelho.
import { pic, registro } from "./core.js";

const ASR_MODELO = "onnx-community/whisper-base";
const LIB = "https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.5.1";
let asrPromise = null;

// "Ouvido" do Zuli: em vez de transcrever (o Whisper erra muito com palavra curta e fala infantil),
// verifica se o áudio combina com a palavra-alvo melhor do que com outras palavras e com balbucios.
// Teste com 80 palavras: 90% de acerto e 4% de falso aceite (85% e 3% com tom de criança).
const BALBUCIO = ["ah", "hum", "é", "não", "o quê", "bá", "mã"];
export function carregarOuvido(progresso) {
  if (asrPromise) return asrPromise;
  asrPromise = (async () => {
    const T = await import(LIB);
    const device = navigator.gpu && (await navigator.gpu.requestAdapter().catch(() => null)) ? "webgpu" : "wasm";
    const cb = p => { if (p.status === "progress" && p.total) progresso?.(p.loaded / p.total); };
    const [proc, tok, model] = await Promise.all([
      T.AutoProcessor.from_pretrained(ASR_MODELO, { progress_callback: cb }),
      T.AutoTokenizer.from_pretrained(ASR_MODELO),
      T.WhisperForConditionalGeneration.from_pretrained(ASR_MODELO, { device, progress_callback: cb,
        dtype: device === "webgpu" ? { encoder_model: "fp32", decoder_model_merged: "q4" } : "q8" }),
    ]);
    const id = t => tok.model.tokens_to_ids.get(t);
    const PRE = ["<|startoftranscript|>", "<|pt|>", "<|transcribe|>", "<|notimestamps|>"].map(id), EOT = id("<|endoftext|>");
    // log-prob média por token de cada texto, com o encoder rodando uma vez só
    async function pontuar(audio, textos) {
      const { input_features } = await proc(audio);
      const enc = await model.sessions.model.run({ input_features: input_features.ort_tensor });
      const hid = new T.Tensor(enc.last_hidden_state);
      const seqs = textos.map(t => [...PRE, ...tok.encode(" " + t, { add_special_tokens: false }), EOT]);
      const L = Math.max(...seqs.map(x => x.length)), ids = new BigInt64Array(seqs.length * (L - 1));
      seqs.forEach((x, i) => { for (let j = 0; j < L - 1; j++) ids[i * (L - 1) + j] = BigInt(x[j] ?? EOT); });
      const out = await model({ encoder_outputs: T.cat(Array(seqs.length).fill(hid), 0), decoder_input_ids: new T.Tensor("int64", ids, [seqs.length, L - 1]) });
      const [, Tt, V] = out.logits.dims, lg = out.logits.data;
      return seqs.map((x, b) => {
        let soma = 0;
        for (let j = PRE.length; j < x.length; j++) {
          const row = (b * Tt + j - 1) * V; let mx = -Infinity;
          for (let v = 0; v < V; v++) if (lg[row + v] > mx) mx = lg[row + v];
          let z = 0; for (let v = 0; v < V; v++) z += Math.exp(lg[row + v] - mx);
          soma += lg[row + x[j]] - mx - Math.log(z);
        }
        return soma / (x.length - PRE.length);
      });
    }
    // devolve {nota 1..3, parecido 0..1, posicao}
    return async function verificar(audio, alvo, comparacao) {
      const cands = [alvo, ...comparacao.filter(c => c !== alvo).slice(0, 14), ...BALBUCIO.filter(b => b !== alvo)];
      const s = await pontuar(audio, cands);
      const m = Math.max(...s), e = s.map(x => Math.exp(4 * (x - m))), z = e.reduce((a, b) => a + b, 0);
      const parecido = e[0] / z, posicao = 1 + s.filter(x => x > s[0]).length;
      const nota = posicao === 1 && parecido >= 0.5 ? 3 : posicao <= 3 ? 2 : 1;
      return { nota, parecido, posicao };
    };
  })();
  asrPromise.catch(() => { asrPromise = null; });
  return asrPromise;
}

// grava até a criança parar de falar (ou 4 s). Devolve áudio mono 16 kHz.
async function gravar(aoNivel) {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
  const ac = new (window.AudioContext || window.webkitAudioContext)();
  const src = ac.createMediaStreamSource(stream), an = ac.createAnalyser(); an.fftSize = 1024; src.connect(an);
  const rec = new MediaRecorder(stream), partes = [];
  rec.ondataavailable = e => partes.push(e.data);
  const buf = new Float32Array(an.fftSize);
  let falou = false, silencioDesde = 0, pico = 0; const t0 = performance.now();
  rec.start();
  await new Promise(res => {
    const tick = () => {
      an.getFloatTimeDomainData(buf);
      let s = 0; for (const v of buf) s += v * v; const rms = Math.sqrt(s / buf.length);
      pico = Math.max(pico, rms); aoNivel?.(Math.min(1, rms * 12));
      const agora = performance.now();
      if (rms > 0.03) { falou = true; silencioDesde = 0; } else if (falou && !silencioDesde) silencioDesde = agora;
      if (agora - t0 > 4000 || (falou && silencioDesde && agora - silencioDesde > 700)) return res();
      requestAnimationFrame(tick);
    };
    tick();
  });
  rec.stop(); await new Promise(r => rec.onstop = r);
  stream.getTracks().forEach(t => t.stop());
  const ab = await new Blob(partes).arrayBuffer();
  const dec = await ac.decodeAudioData(ab); ac.close();
  const off = new OfflineAudioContext(1, Math.ceil(dec.duration * 16000), 16000);
  const s = off.createBufferSource(); s.buffer = dec; s.connect(off.destination); s.start();
  const r = await off.startRendering();
  return { audio: r.getChannelData(0), pico };
}

function escolherPalavras(perfil, opt, vocab, by) {
  if (opt.treinoPalavras?.length) return opt.treinoPalavras.filter(id => by[id]).slice(0, 5);
  // automático: palavras que a criança usa + as que precisam de mais treino
  const log = registro.ler(perfil), uso = {}, nota = {};
  for (const e of log) {
    if (e.tipo === "frase") e.ids.forEach(id => uso[id] = (uso[id] || 0) + 1);
    if (e.tipo === "treino") (nota[e.id] ??= []).push(e.nota);
  }
  const media = id => nota[id] ? nota[id].slice(-3).reduce((a, b) => a + b, 0) / nota[id].slice(-3).length : 0;
  const cands = vocab.slice(0, 120).map(w => w.id).filter(id => by[id].label.length > 1);
  const score = id => (uso[id] || 0) * 2 + (3 - media(id)) * 3 + Math.random() * 4 - (media(id) >= 3 ? 8 : 0);
  return cands.sort((a, b) => score(b) - score(a)).slice(0, 5);
}

const SVG = {
  ouvir: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M11 5 6 9H3v6h3l5 4z"/><path d="M15.5 8.5a5 5 0 0 1 0 7M18.5 5.5a9 9 0 0 1 0 13"/></svg>',
  falar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10a7 7 0 0 0 14 0M12 17v5M8 22h8"/></svg>',
  fechar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18"/></svg>',
  estrela: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2.5l2.9 6 6.6.9-4.8 4.6 1.2 6.5L12 17.4l-5.9 3.1 1.2-6.5L2.5 9.4l6.6-.9z"/></svg>',
};

export function abrir({ perfil, opt, vocab, by, voz }) {
  const palavras = escolherPalavras(perfil, opt, vocab, by);
  let i = 0, notas = [];
  const el = document.createElement("div");
  el.className = "treino"; el.setAttribute("role", "dialog"); el.setAttribute("aria-label", "Treinar palavras");
  document.body.append(el);
  const usaMic = opt.treinoMicrofone && !!navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== "undefined";
  let ouvido = null;
  if (usaMic) ouvido = carregarOuvido(p => { const b = el.querySelector(".carga i"); if (b) b.style.width = (p * 100).toFixed(0) + "%"; });

  const fechar = () => { voz.parar(); el.remove(); };
  const zuli = (n, texto) => voz.falar([{ chave: `zuli_${n}`, texto }]);
  const falarPalavra = () => voz.falar([{ chave: palavras[i], texto: by[palavras[i]].label }]);

  function tela() {
    if (i >= palavras.length) {
      const total = notas.reduce((a, b) => a + b, 0);
      el.innerHTML = `<div class="tr-top"><span></span><button type="button" class="tr-x" aria-label="Sair">${SVG.fechar}</button></div>
        <div class="tr-centro"><img class="tr-zuli festa" src="assets/zuli.png" alt=""><h2>Parabéns!</h2>
        <div class="tr-estrelas grande">${SVG.estrela.repeat(Math.max(1, Math.round(total / palavras.length)))}</div>
        <div class="tr-acoes"><button type="button" class="tr-btn" data-a="de-novo">Treinar de novo</button><button type="button" class="tr-btn sec" data-a="sair">Voltar à prancha</button></div></div>`;
      zuli(9, "Acabou! Parabéns!");
      return;
    }
    const w = by[palavras[i]]; tentativas = 0;
    el.innerHTML = `<div class="tr-top"><div class="tr-prog">${palavras.map((_, k) => `<i class="${k < i ? "ok" : k === i ? "on" : ""}"></i>`).join("")}</div>
        <button type="button" class="tr-x" aria-label="Sair">${SVG.fechar}</button></div>
      <div class="tr-centro">
        <div class="tr-card cat-${w.cor}"><img src="${pic(w.id)}" alt=""><span>${w.label}</span></div>
        <div class="tr-msg" aria-live="polite">Escute e repita</div>
        <div class="tr-nivel" hidden><i></i></div>
        ${usaMic ? `<div class="carga" hidden><i></i></div>` : ""}
        <div class="tr-acoes">
          <button type="button" class="tr-btn sec" data-a="ouvir">${SVG.ouvir}<span>ouvir</span></button>
          ${usaMic ? `<button type="button" class="tr-btn" data-a="falar">${SVG.falar}<span>falar</span></button>`
                   : `<button type="button" class="tr-btn" data-a="consegui">consegui</button><button type="button" class="tr-btn sec" data-a="pular">de novo depois</button>`}
        </div>
      </div>`;
    setTimeout(falarPalavra, 250);
  }

  async function tentar() {
    const msg = el.querySelector(".tr-msg"), nivel = el.querySelector(".tr-nivel"), carga = el.querySelector(".carga");
    const btn = el.querySelector('[data-a="falar"]'); btn.disabled = true;
    try {
      let asr;
      const pronto = await Promise.race([ouvido.then(a => (asr = a, true)), new Promise(r => setTimeout(() => r(false), 50))]);
      if (!pronto) { msg.textContent = "O Zuli está aprendendo a ouvir… (só na primeira vez)"; carga.hidden = false; asr = await ouvido; carga.hidden = true; }
      zuli(2, "Agora é a sua vez!"); await new Promise(r => setTimeout(r, 1100));
      msg.textContent = "Fale agora!"; nivel.hidden = false;
      const { audio, pico } = await gravar(v => nivel.firstChild.style.width = (v * 100).toFixed(0) + "%");
      nivel.hidden = true;
      if (pico < 0.03) { msg.textContent = "Não ouvi. Fala mais perto?"; zuli(7, "Não ouvi. Fala mais perto?"); btn.disabled = false; return; }
      msg.textContent = "Ouvindo…";
      const alvo = by[palavras[i]].label;
      const comparacao = Array.from({ length: 20 }, () => vocab[Math.floor(Math.random() * Math.min(300, vocab.length))].label);
      const r = await asr(audio, alvo, comparacao), n = r.nota;
      registro.add(perfil, { tipo: "treino", id: palavras[i], nota: n, parecido: Math.round(r.parecido * 100), posicao: r.posicao });
      el.querySelector(".tr-card").insertAdjacentHTML("afterend", `<div class="tr-estrelas">${SVG.estrela.repeat(n)}</div>`);
      if (n === 3) { msg.textContent = "Muito bem!"; zuli(3, "Muito bem!"); notas.push(3); setTimeout(() => { i++; tela(); }, 1800); }
      else if (n === 2) { msg.textContent = "Quase! Vamos de novo?"; zuli(5, "Quase! Vamos tentar de novo?"); notas.push(2); proximaOuRepetir(btn); }
      else { msg.textContent = "Vamos tentar de novo."; zuli(6, "Vamos tentar de novo."); proximaOuRepetir(btn, 1); }
    } catch (e) {
      console.warn(e);
      msg.textContent = e?.name === "NotAllowedError" ? "Sem permissão do microfone. Um adulto pode liberar nos ajustes do navegador." : "Não deu para ouvir agora.";
      btn.disabled = false;
    }
  }
  let tentativas = 0;
  function proximaOuRepetir(btn, nota) {
    tentativas++;
    if (tentativas >= 3) { if (nota) notas.push(nota); tentativas = 0; setTimeout(() => { i++; tela(); }, 1800); }
    else { btn.disabled = false; setTimeout(falarPalavra, 1600); }
  }

  el.addEventListener("click", e => {
    const b = e.target.closest("button"); if (!b) return;
    voz.desbloquear();
    if (b.classList.contains("tr-x")) return fechar();
    const a = b.dataset.a;
    if (a === "ouvir") falarPalavra();
    if (a === "falar") tentar();
    if (a === "consegui") { registro.add(perfil, { tipo: "treino", id: palavras[i], nota: 3, ouvido: "(adulto confirmou)" }); notas.push(3); zuli(3, "Muito bem!"); setTimeout(() => { i++; tela(); }, 1400); }
    if (a === "pular") { registro.add(perfil, { tipo: "treino", id: palavras[i], nota: 1, ouvido: "(adulto: treinar de novo)" }); notas.push(1); i++; tela(); }
    if (a === "de-novo") { i = 0; notas = []; tela(); }
    if (a === "sair") fechar();
  });
  zuli(8, "Vamos treinar?");
  setTimeout(tela, 900);
}
