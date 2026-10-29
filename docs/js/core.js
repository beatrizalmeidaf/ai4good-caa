// Zuli: código comum à área da criança e à área dos pais.
// Perfis, registros de uso, dados, áudio e previsão. Tudo fica neste aparelho.
import { loadSLM, loadComite } from "./slm.js";

export const DATA = "data/";
export const END = "__end__";
export const pic = id => `p/${id}.webp`;
export const AUDIO_V = 4;  // aumente quando gerar o áudio de novo

/* ---------------- armazenamento local ---------------- */
export const store = {
  get(k, d) { try { const v = localStorage.getItem("zuli-" + k); return v ? JSON.parse(v) : d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem("zuli-" + k, JSON.stringify(v)); return true; } catch { return false; } },
  del(k) { try { localStorage.removeItem("zuli-" + k); } catch {} },
};

export const OPT_PADRAO = {
  grade: "5x3", falarCada: true, sugestoes: true, conceito: true, parceiro: false, ouvirAdulto: true,
  local: "casa", periodoAuto: true, periodo: "manha", velocidade: 1, preditor: "slm",
  treinoPalavras: [], treinoMicrofone: true, fonteVoz: "gravada", rotina: [], calma: true,
};

export const perfis = {
  lista() { return store.get("perfis", []); },
  ativo() { const id = store.get("ativo", null); return this.lista().find(p => p.id === id) || this.lista()[0] || null; },
  salvar(p) { const l = this.lista().filter(x => x.id !== p.id); l.push(p); store.set("perfis", l); },
  usar(id) { store.set("ativo", id); },
  remover(id) {
    store.set("perfis", this.lista().filter(p => p.id !== id));
    for (const k of ["opt", "pessoal", "log"]) store.del(`${k}-${id}`);
  },
  novo(nome, genero, idade) {
    const p = { id: Math.random().toString(36).slice(2, 9), nome, genero, idade, criado: Date.now() };
    this.salvar(p); this.usar(p.id); return p;
  },
  opt(p) { return Object.assign({}, OPT_PADRAO, store.get(`opt-${p.id}`, {})); },
  salvarOpt(p, o) { store.set(`opt-${p.id}`, o); },
};

/* registro de uso, para o painel dos pais (máx. 4000 eventos por criança) */
export const registro = {
  ler(p) { return store.get(`log-${p.id}`, []); },
  add(p, ev) {
    const l = this.ler(p); l.push(Object.assign({ t: Date.now() }, ev));
    while (l.length > 4000) l.shift();
    if (!store.set(`log-${p.id}`, l)) { l.splice(0, 1000); store.set(`log-${p.id}`, l); }
  },
};

/* ---------------- levar os dados para outro aparelho ---------------- */
// Arquivo .zuli.json com tudo de uma criança: perfil, ajustes, aprendizado da prancha e histórico.
export function exportarCrianca(p) {
  const dados = { formato: "zuli-1", exportado: new Date().toISOString(), perfil: p,
    ajustes: store.get(`opt-${p.id}`, {}), pessoal: store.get(`pessoal-${p.id}`, null), historico: registro.ler(p) };
  const blob = new Blob([JSON.stringify(dados)], { type: "application/json" });
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob);
  a.download = `zuli-${p.nome.replace(/[^\p{L}\p{N}]+/gu, "-").toLowerCase()}-${dados.exportado.slice(0, 10)}.zuli.json`;
  document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}
// Lê o arquivo e cadastra a criança neste aparelho. Se já existir (mesmo id), substitui.
export async function importarCrianca(arquivo) {
  let d;
  try { d = JSON.parse(await arquivo.text()); } catch { throw new Error("O arquivo não é um arquivo do Zuli."); }
  if (d?.formato !== "zuli-1" || !d.perfil?.id || !d.perfil?.nome) throw new Error("O arquivo não é um arquivo do Zuli.");
  const p = { id: String(d.perfil.id), nome: String(d.perfil.nome).slice(0, 30), genero: d.perfil.genero === "m" ? "m" : "f",
    idade: d.perfil.idade || null, criado: d.perfil.criado || Date.now() };
  perfis.salvar(p); perfis.usar(p.id);
  if (d.ajustes) store.set(`opt-${p.id}`, d.ajustes);
  if (d.pessoal) store.set(`pessoal-${p.id}`, d.pessoal);
  if (Array.isArray(d.historico)) store.set(`log-${p.id}`, d.historico.slice(-4000));
  return p;
}
// Trocar de família: apaga tudo do Zuli neste aparelho (crianças, histórico, PIN).
export function apagarTudo() {
  try { Object.keys(localStorage).filter(k => k.startsWith("zuli-")).forEach(k => localStorage.removeItem(k)); } catch {}
  try { sessionStorage.removeItem("zuli-pais"); } catch {}
}

/* PIN dos pais: guardado como hash, nunca em texto */
export async function hashPin(pin) {
  const b = await crypto.subtle.digest("SHA-256", new TextEncoder().encode("zuli:" + pin));
  return [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, "0")).join("");
}

/* ---------------- dados ---------------- */
export async function carregarVocab() {
  const vocab = await fetch(DATA + "vocab.json").then(r => r.json());
  const by = {}; vocab.forEach(w => by[w.id] = w);
  return { vocab, by };
}

/* ---------------- texto → pictogramas ----------------
   O que o adulto disse vira pictogramas da prancha, e o modelo usa isso para sugerir a resposta.
   Mesma regra do treino (experiments/v2/texto_pictos.py): formas.json {forma: id}, até 3 palavras juntas. */
const LIGACAO = new Set(["com", "no", "na", "nos", "nas", "para", "pra", "de", "do", "da", "dos", "das", "e", "mas", "ou", "se", "até", "sem",
  "em", "ao", "que", "tão", "embora", "o", "a", "os", "as", "um", "uma", "uns", "umas", "é", "lá", "aí", "aqui", "né", "então"]);
let formasP = null;
export const carregarFormas = () => formasP ??= fetch(DATA + "formas.json").then(r => r.json());
const semAcento = s => s.normalize("NFD").replace(/\p{Mn}/gu, "");
const palavras = t => t.toLowerCase().replace(/’/g, "'").replace(/[^\p{L}\p{N}\s-]/gu, " ").replace(/_/g, " ").split(/[\s-]+/).filter(Boolean);
export function textoParaPictos(texto, F, maximo = 10) {
  const w = palavras(texto || ""), out = [];
  for (let i = 0; i < w.length;) {
    let n = 3;
    for (; n >= 1; n--) {
      if (i + n > w.length) continue;
      const g = w.slice(i, i + n).join(" "), id = F[g] ?? F[semAcento(g)];
      if (id === undefined) continue;
      if (!(n === 1 && LIGACAO.has(w[i])) && !out.includes(id)) out.push(id);
      break;
    }
    i += n >= 1 ? n : 1;
  }
  return out.slice(0, maximo);
}

// Páginas da prancha (poucas, para não poluir): id, nome, cor Fitzgerald, rótulos candidatos a ícone.
export const PAGINAS = [
  ["nucleo", "Principais", "acao", ["querer", "eu"]], ["pessoas", "Pessoas", "pessoa", ["mãe", "eu"]],
  ["acoes", "Fazer", "acao", ["brincar", "fazer"]], ["sentir", "Sentir", "descricao", ["feliz"]],
  ["comida", "Comer", "coisa", ["comer", "pão", "suco"]], ["brincar", "Brincar", "coisa", ["bola", "brinquedo"]],
  ["corpo", "Corpo", "coisa", ["barriga", "corpo"]], ["lugares", "Lugares e coisas", "lugar", ["casa", "escola"]],
  ["conversa", "Conversa", "social", ["oi", "tchau"]],
];
// páginas do vocabulário -> grupo exibido
const GRUPO = { pessoas: "pessoas", acoes: "acoes", sentir: "sentir", descrever: "sentir", comida: "comida",
  brincar: "brincar", animais: "brincar", corpo: "corpo", roupa: "corpo", lugares: "lugares", escola: "lugares",
  coisas: "lugares", conversa: "conversa", perguntas: "conversa" };
export const grupoDe = w => GRUPO[w.pagina] || "lugares";
export function montarPaginas(vocab) {
  const ordem = ["pessoa", "acao", "descricao", "social", "negacao", "tempo", "coisa", "lugar"];
  const pg = { nucleo: vocab.slice(0, 30).sort((a, b) => ordem.indexOf(a.cor) - ordem.indexOf(b.cor) || b.freq - a.freq).map(w => w.id) };
  for (const w of vocab) (pg[grupoDe(w)] ??= []).push(w.id);
  return pg;
}

/* ---------------- áudio ----------------
   Cada pictograma tem um MP3 curto gravado com voz neural (feminina ou masculina).
   Toca na hora pelo Web Audio. A frase é tocada palavra por palavra, sem esperar rede.
   Se faltar um arquivo, usa a voz do sistema (speechSynthesis). */
// Vozes gravadas disponíveis (pasta em docs/audio/<id>)
export const VOZES = [
  { id: "f", nome: "Feminina", desc: "Voz jovem, clara (XTTS)" },
  { id: "mc", nome: "Masculina (criança)", desc: "Voz de menino (F5-TTS)" },
];
// voz escolhida para a criança: o que os adultos escolheram, ou pelo gênero do perfil
export function vozDoPerfil(p, o) {
  const v = o?.voz === "m" ? "mc" : o?.voz;  // a voz de adulto saiu: quem usava passa para a de criança
  return { pasta: v || (p?.genero === "m" ? "mc" : "f"), sistema: o?.fonteVoz === "aparelho" };
}

export class Voz {
  // pasta: "f" (feminina), "mc" (masculina, criança); sistema = voz do aparelho
  constructor(pasta = "f", velocidade = 1, sistema = false) {
    this.g = VOZES.some(v => v.id === pasta) ? pasta : "f"; this.feminina = this.g === "f";
    this.vel = velocidade; this.sistema = sistema; this.buf = new Map(); this.ctx = null; this.fontes = [];
  }
  desbloquear() {
    // iPhone/iPad: sem isto o Web Audio fica mudo com a chave de silencioso ligada
    try { if (navigator.audioSession && navigator.audioSession.type !== "playback") navigator.audioSession.type = "playback"; } catch {}
    if (!this.ctx) { try { this.ctx = new (window.AudioContext || window.webkitAudioContext)(); } catch {} }
    if (this.ctx && this.ctx.state !== "running") this.ctx.resume().catch(() => {});   // "suspended" ou "interrupted" (iOS)
    if (!this.destravado && this.ctx) {
      // iOS antigo: tocar um áudio de mídia (silêncio) no primeiro toque troca a sessão para "reprodução"
      this.destravado = true;
      try { const a = new Audio("assets/silencio.mp3"); a.setAttribute("playsinline", ""); a.volume = 0.01; a.play().catch(() => {}); } catch {}
    }
  }
  // versão no endereço: quando a voz muda, o aparelho baixa o áudio novo em vez de tocar o guardado no cache
  url(chave) { return `audio/${this.g}/${chave}.mp3?v=${AUDIO_V}`; }
  async carregar(chave) {
    if (this.buf.has(chave)) return this.buf.get(chave);
    const pr = (async () => {
      this.desbloquear(); if (!this.ctx) return null;
      try {
        const ab = await fetch(this.url(chave)).then(r => { if (!r.ok) throw 0; return r.arrayBuffer(); });
        const b = await this.ctx.decodeAudioData(ab), d = b.getChannelData(0);
        // acha onde a fala começa e termina: toca só esse trecho (resposta imediata ao toque)
        let mx = 0; for (let i = 0; i < d.length; i++) mx = Math.max(mx, Math.abs(d[i]));
        const thr = mx * 0.02; let a = 0, z = d.length - 1;
        while (a < d.length && Math.abs(d[a]) < thr) a++;
        while (z > a && Math.abs(d[z]) < thr) z--;
        const ini = Math.max(0, a / b.sampleRate - 0.02), fim = Math.min(b.duration, z / b.sampleRate + 0.06);
        return { b, ini, dur: Math.max(0.05, fim - ini) };
      } catch { return null; }
    })();
    this.buf.set(chave, pr); return pr;
  }
  preparar(chaves) { chaves.forEach(c => this.carregar(c)); }
  parar() { this.fontes.forEach(s => { try { s.stop(); } catch {} }); this.fontes = []; try { speechSynthesis.cancel(); } catch {} }
  // itens: [{chave, texto}]; aoPalavra(i) chamado quando cada item começa
  async falar(itens, { aoPalavra, aoFim } = {}) {
    this.parar(); this.desbloquear();
    // voz do aparelho: fala a frase inteira de uma vez (entonação mais natural), menos as falas do Zuli
    if (this.sistema && !itens.every(i => String(i.chave).startsWith("zuli_"))) return this.falarSistema(itens.map(i => i.texto).join(" "), aoFim, aoPalavra, itens);
    if (this.ctx && this.ctx.state !== "running") await Promise.race([this.ctx.resume().catch(() => {}), new Promise(r => setTimeout(r, 300))]);
    // Web Audio parado (alguns iPhones/iPads): toca os mesmos MP3 como mídia comum
    if (!this.ctx || this.ctx.state !== "running") return this.falarMidia(itens, aoPalavra, aoFim);
    const bufs = await Promise.all(itens.map(it => this.carregar(it.chave)));
    if (bufs.some(b => !b)) return this.falarSistema(itens.map(i => i.texto).join(" "), aoFim);
    let t = this.ctx.currentTime + 0.02; const timers = [];
    bufs.forEach((x, i) => {
      const s = this.ctx.createBufferSource(); s.buffer = x.b; s.playbackRate.value = this.vel; s.connect(this.ctx.destination);
      s.start(t, x.ini, x.dur);
      this.fontes.push(s);
      timers.push(setTimeout(() => aoPalavra?.(i), (t - this.ctx.currentTime) * 1000));
      t += x.dur / this.vel + 0.06;
    });
    setTimeout(() => aoFim?.(), (t - this.ctx.currentTime) * 1000 + 50);
  }
  falarMidia(itens, aoPalavra, aoFim) {
    let i = 0; const el = this.midia ??= new Audio(); el.setAttribute("playsinline", "");
    const proximo = () => {
      if (i >= itens.length) return aoFim?.();
      aoPalavra?.(i); el.src = this.url(itens[i++].chave); el.playbackRate = this.vel;
      el.onended = proximo; el.onerror = proximo;
      el.play().catch(() => this.falarSistema(itens.map(x => x.texto).join(" "), aoFim));
    };
    this.fontes.push({ stop: () => { el.onended = null; el.pause(); } });
    proximo();
  }
  falarSistema(texto, aoFim, aoPalavra, itens) {
    try {
      const u = new SpeechSynthesisUtterance(texto); u.lang = "pt-BR"; u.rate = 0.95 * this.vel;
      const vs = speechSynthesis.getVoices().filter(v => v.lang?.replace("_", "-").startsWith("pt"));
      const fem = /luciana|francisca|maria|vit[oó]ria|female|feminina|leila|raquel/i, masc = /daniel|felipe|ant[oô]nio|male|masculina|ricardo/i;
      u.voice = vs.find(v => (this.feminina ? fem : masc).test(v.name) && v.lang.includes("BR")) || vs.find(v => v.lang.includes("BR")) || vs[0] || null;
      if (aoPalavra && itens) { // destaca cada pictograma quando o navegador avisa a palavra
        const ini = []; let p = 0; for (const it of itens) { ini.push(p); p += it.texto.length + 1; }
        u.onboundary = e => { let i = 0; while (i + 1 < ini.length && ini[i + 1] <= e.charIndex) i++; aoPalavra(i); };
      }
      u.onend = () => aoFim?.(); u.onerror = () => aoFim?.();
      speechSynthesis.cancel(); speechSynthesis.speak(u);
    } catch { aoFim?.(); }
  }
}

/* ---------------- previsão ---------------- */
export class Preditor {
  constructor(vocab, by, p) { this.vocab = vocab; this.by = by; this.p = p; this.slm = null; this.ngram = null; this.pessoal = store.get(`pessoal-${p.id}`, { n: 0, bi: {}, tri: {} }); }
  async iniciar() {
    // começa com 1 modelo (rápido); os outros 2 do comitê chegam depois, sem disputar a rede com o áudio
    try { this.slm = await loadSLM(DATA); } catch (e) { console.warn("SLM indisponível", e); await this.carregarNgram(); return; }
    setTimeout(() => loadComite(DATA).then(c => { if (c.membros > 1) this.slm = c; }).catch(() => {}), 6000);
  }
  async carregarNgram() { if (!this.ngram) this.ngram = await fetch(DATA + "ngram.json").then(r => r.json()); }
  ngramProbs(ctx, prefix) {
    const cx = `${ctx.periodo}|${ctx.local}|${ctx.adulto}`, seq = ["<s>", "<s>", ...prefix.map(String)];
    const a = seq.at(-2), b = seq.at(-1), C = this.ngram.counts, L = this.ngram.lambdas;
    const out = {}; let end = 1e-7; for (const w of this.vocab) out[w.id] = 1e-7;
    for (const [k, key] of Object.entries({ ctxb: `${cx}|${b}`, tri: `${a}|${b}`, bi: b, ctx: cx, uni: "" })) {
      const d = C[k]?.[key]; if (!d) continue; let tot = 0; for (const v of Object.values(d)) tot += v;
      for (const [w, c] of Object.entries(d)) { if (w === "</s>") end += L[k] * c / tot; else if (w in out) out[w] += L[k] * c / tot; }
    }
    return { symbols: out, end };
  }
  // devolve [[id|END, prob], ...] ordenado
  prever(ctx, prefix, usarNgram = false) {
    let probs = {}, end = 0;
    if (!usarNgram && this.slm) {
      const o = this.slm.predict(ctx, prefix);
      for (const [k, v] of Object.entries(o.symbols)) probs[k] = Math.exp(v);
      end = Math.exp(o.end);
    } else if (this.ngram) { const o = this.ngramProbs(ctx, prefix); probs = o.symbols; end = o.end; }
    probs[END] = prefix.length ? end : 0;
    const P = this.pessoal, seq = ["<s>", "<s>", ...prefix.map(String)];
    const m = P.tri[`${seq.at(-2)}|${seq.at(-1)}`] || P.bi[seq.at(-1)];
    if (m) {
      let tot = 0; for (const v of Object.values(m)) tot += v;
      const w = Math.min(.5, tot / (tot + 4));
      for (const k of new Set([...Object.keys(probs), ...Object.keys(m)])) probs[k] = (1 - w) * (probs[k] || 0) + w * ((m[k] || 0) / tot);
    }
    if (prefix.length) delete probs[prefix.at(-1)];
    return Object.entries(probs).filter(([k]) => k === END || this.by[k]).sort((a, b) => b[1] - a[1]);
  }
  aprender(seq) {
    const s = ["<s>", "<s>", ...seq.map(String), END], P = this.pessoal;
    for (let i = 2; i < s.length; i++) {
      const t = `${s[i - 2]}|${s[i - 1]}`;
      (P.tri[t] ??= {})[s[i]] = (P.tri[t][s[i]] || 0) + 1;
      (P.bi[s[i - 1]] ??= {})[s[i]] = (P.bi[s[i - 1]][s[i]] || 0) + 1;
    }
    P.n++; store.set(`pessoal-${this.p.id}`, P);
  }
}

export function periodoAgora(opt) {
  if (!opt.periodoAuto) return opt.periodo;
  const h = new Date().getHours(); return h < 12 ? "manha" : h < 18 ? "tarde" : "noite";
}

/* ---------------- comparação de fala (treino) ---------------- */
export function normalizar(s) {
  return s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z ]/g, " ").replace(/\s+/g, " ").trim();
}
function lev(a, b) {
  const d = Array.from({ length: a.length + 1 }, (_, i) => [i]);
  for (let j = 1; j <= b.length; j++) d[0][j] = j;
  for (let i = 1; i <= a.length; i++) for (let j = 1; j <= b.length; j++)
    d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
  return d[a.length][b.length];
}
// semelhança 0..1 entre o que foi ouvido e a palavra-alvo (melhor trecho do que foi ouvido)
export function semelhanca(ouvido, alvo) {
  const o = normalizar(ouvido), a = normalizar(alvo);
  if (!o || !a) return 0;
  if (o.split(" ").includes(a) || o === a) return 1;
  const pal = o.split(" "), n = a.split(" ").length; let best = 0;
  for (let i = 0; i < pal.length; i++) for (let k = 1; k <= n + 1 && i + k <= pal.length; k++) {
    const t = pal.slice(i, i + k).join(" ");
    best = Math.max(best, 1 - lev(t, a) / Math.max(t.length, a.length));
  }
  return best;
}
export const estrelas = s => s >= 0.75 ? 3 : s >= 0.45 ? 2 : 1;
