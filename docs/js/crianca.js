// Área da criança: prancha fixa, sugestões, Zuli fala a frase, botão Treinar.
import { END, pic, perfis, registro, carregarVocab, PAGINAS, montarPaginas, grupoDe, Voz, Preditor, periodoAgora, vozDoPerfil, carregarFormas, textoParaPictos } from "./core.js";

const $ = s => document.querySelector(s);
const PARCEIRO = [
  ["nenhuma", "ninguém falou"], ["o_que_quer", "o que você quer?"], ["como_esta", "como você está?"], ["onde", "onde?"],
  ["o_que_fazer", "o que vamos fazer?"], ["o_que_aconteceu", "o que aconteceu?"], ["sim_nao", "sim ou não?"],
  ["quem", "quem?"], ["gosta", "gostou?"], ["comentario", "comentou algo"], ["cumprimento", "oi / tchau"],
];

const perfil = perfis.ativo();
if (!perfil) location.replace("./");  // sem criança cadastrada: volta para a página inicial
const opt = perfil ? perfis.opt(perfil) : {};
const S = { vocab: [], by: {}, pg: {}, page: "nucleo", sub: 0, phrase: [], spoken: false, adulto: "nenhuma", adp: [], adTexto: "", top: [],
  toques: 0, daSugestao: 0, toquesFrase: 0 };
const vz = vozDoPerfil(perfil, opt), voz = new Voz(vz.pasta, opt.velocidade, vz.sistema);
let pred;

function tile(w) {
  if (w === END) return `<button type="button" class="tile end" data-id="${END}" aria-label="Falar a frase"><img src="assets/zuli.png" alt=""><span>falar</span></button>`;
  return `<button type="button" class="tile cat-${w.cor}" data-id="${w.id}" aria-label="${w.label}"><img src="${pic(w.id)}" alt="" decoding="async" draggable="false"><span>${w.label}</span></button>`;
}
// adulto: tipo da fala (escolhido na linha do adulto) ou "desconhecido" quando veio só pelo microfone; adp: pictogramas do que ele disse
const ctx = () => ({ periodo: periodoAgora(opt), local: opt.local, adulto: S.adp.length && S.adulto === "nenhuma" ? "desconhecido" : S.adulto, adp: S.adp });

/* ---------- sugestões ---------- */
// Planejamento motor também na faixa: o que continua sugerido fica no mesmo espaço; só os espaços que mudam recebem novidades.
function estabilizar(novos, antigos, n = 6) {
  const fim = novos.includes(END), lista = novos.filter(k => k !== END).slice(0, fim ? n - 1 : n);
  const out = Array(n).fill(null);
  antigos.forEach((k, i) => { if (k !== END && i < (fim ? n - 1 : n) && lista.includes(k)) out[i] = k; });
  const resto = lista.filter(k => !out.includes(k));
  for (let i = 0; i < n; i++) if (out[i] === null && !(fim && i === n - 1)) out[i] = resto.shift() ?? null;
  if (fim) out[n - 1] = END;
  return out.filter(k => k !== null);
}
function prever() {
  const prefix = S.spoken ? [] : S.phrase;
  let ranked = pred.prever(ctx(), prefix, opt.preditor === "ngram");
  // rotina: a atividade de agora fica mais provável
  const ag = rotinaAgora();
  if (ag && !prefix.includes(ag.id)) ranked = ranked.map(([k, v]) => [k, String(k) === String(ag.id) ? v + 0.15 : v]).sort((a, b) => b[1] - a[1]);
  if (S.calmaAte > Date.now()) return mostrarCalma();
  // o que já está na tela não ocupa a faixa (tocar ali custa o mesmo): sobra espaço para palavras de outras páginas
  const { n } = grade(), naTela = new Set((S.pg[S.page] || []).slice(S.sub * n, S.sub * n + n).map(String));
  const top = estabilizar(ranked.filter(([k]) => !naTela.has(String(k))).slice(0, 6).map(([k]) => k), S.top);
  S.top = top;
  $("#sugg").classList.remove("calma");
  $("#sugg").innerHTML = (S.agoraHtml || "") + (opt.sugestoes ? S.top.map(k => tile(k === END ? END : S.by[k])).join("") : "");
  voz.preparar(S.top.filter(k => k !== END));
  // página provável do próximo pictograma (sem contar o que já está nas sugestões)
  const pp = {};
  for (const [k, v] of ranked) { if (k === END || S.top.includes(k)) continue; const g = grupoDe(S.by[k]); pp[g] = (pp[g] || 0) + v; }
  const best = Object.entries(pp).sort((a, b) => b[1] - a[1])[0];
  document.querySelectorAll("#abas button[data-page]").forEach(b => b.classList.toggle("hint", opt.conceito && !!best && b.dataset.page === best[0] && b.dataset.page !== S.page && best[1] > .2));
}

/* ---------- rotina: bloco "Agora" ---------- */
// opt.rotina = [{ inicio: "14:00", fim: "15:00", id: <pictograma>, dias: [1,2,3,4,5] }]
function rotinaAgora() {
  const r = opt.rotina || []; if (!r.length) return null;
  const d = new Date(), min = d.getHours() * 60 + d.getMinutes(), hm = t => { const [h, m] = t.split(":").map(Number); return h * 60 + m; };
  return r.find(x => (!x.dias?.length || x.dias.includes(d.getDay())) && min >= hm(x.inicio) && min < hm(x.fim) && S.by[x.id]) || null;
}
function renderAgora() {
  if (!(opt.rotina || []).length) { S.agoraHtml = ""; $("#sugg").classList.remove("com-agora"); return; }
  $("#sugg").classList.add("com-agora");      // o espaço "Agora" só existe se a rotina estiver configurada
  const ag = rotinaAgora();
  S.agoraHtml = ag ? `<button type="button" class="tile agora cat-${S.by[ag.id].cor}" data-id="${ag.id}" aria-label="Agora: ${S.by[ag.id].label}"><em>agora</em><img src="${pic(ag.id)}" alt=""><span>${S.by[ag.id].label}</span></button>`
                   : `<div class="tile agora vazio" aria-hidden="true"><em>agora</em></div>`;
}

/* ---------- autorregulação: toques muito rápidos ou repetidos ---------- */
const CALMA = ["pausa", "parar", "silêncio", "abraço", "música", "ajuda"];
const toquesRecentes = [];
function observarToque(id) {
  if (opt.calma === false) return;
  const agora = Date.now(); toquesRecentes.push({ t: agora, id });
  while (toquesRecentes.length && agora - toquesRecentes[0].t > 6000) toquesRecentes.shift();
  const em5s = toquesRecentes.filter(x => agora - x.t <= 5000).length;
  const repetido = id != null && toquesRecentes.filter(x => x.id === id).length >= 4;
  if ((em5s >= 12 || repetido) && agora > (S.calmaPausa || 0)) {
    S.calmaAte = agora + 20000; S.calmaPausa = agora + 60000; toquesRecentes.length = 0;
    registro.add(perfil, { tipo: "calma", motivo: repetido ? "repetido" : "rapido" });
    mostrarCalma(); setTimeout(prever, 20200);
  }
}
function mostrarCalma() {
  const ids = CALMA.map(l => S.vocab.find(w => w.label === l)).filter(Boolean).slice(0, 6);
  $("#sugg").classList.add("calma");
  $("#sugg").innerHTML = (S.agoraHtml || "") + ids.map(w => tile(w)).join("");
}

/* ---------- frase ---------- */
function renderFrase() {
  const el = $("#phrase");
  el.innerHTML = S.phrase.length ? S.phrase.map(id => tile(S.by[id]).replace("<button", '<button tabindex="-1"')).join("")
    : `<span class="hint">Toque nos desenhos. Depois toque no Zuli.</span>`;
  el.scrollLeft = el.scrollWidth;
  el.classList.toggle("spoken", S.spoken);
  $("#b-speak").classList.toggle("ready", !S.spoken && S.phrase.length >= 2);
}
function escolher(id, daSug) {
  voz.desbloquear(); S.toques++; S.toquesFrase++;
  if (id === END) { if (daSug) S.daSugestao++; return falarFrase(); }
  observarToque(String(id));
  if ($("#sugg").classList.contains("calma") && daSug) { S.calmaAte = 0; }  // escolheu um atalho de calma: volta ao normal
  if (S.spoken) { S.phrase = []; S.spoken = false; }
  S.phrase.push(+id); if (daSug) S.daSugestao++;
  if (opt.falarCada) voz.falar([{ chave: id, texto: S.by[id].label }]);
  renderFrase(); prever();
}
function falarFrase() {
  voz.desbloquear();
  if (!S.phrase.length) { voz.falar([{ chave: "zuli_0", texto: "Oi! Eu sou o Zuli!" }]); return; }
  const tiles = [...$("#phrase").querySelectorAll(".tile")], z = $("#b-speak");
  const marcar = i => tiles.forEach((t, j) => t.classList.toggle("say", j === i));
  z.classList.add("talking");
  voz.falar(S.phrase.map(id => ({ chave: id, texto: S.by[id].label.replace(/\?/g, "") })), {
    aoPalavra: marcar, aoFim: () => { marcar(-1); z.classList.remove("talking"); },
  });
  if (!S.spoken) {
    pred.aprender(S.phrase);
    registro.add(perfil, { tipo: "frase", ids: [...S.phrase], sug: S.daSugestao, toques: S.toquesFrase, adulto: S.adulto, adp: [...S.adp], local: opt.local });
  }
  S.spoken = true; S.daSugestao = 0; S.toquesFrase = 0; S.adulto = "nenhuma"; S.adp = []; S.adTexto = ""; renderParceiro();
  renderFrase(); prever();
}

/* ---------- prancha ---------- */
// grade: no celular em pé, troca colunas por linhas (peças continuam grandes)
function grade() {
  let [c, r] = (opt.grade || "5x3").split("x").map(Number);
  if (innerHeight > innerWidth * 1.15 && c > r) [c, r] = [r, c];
  return { c, r, n: c * r };
}
const MIC = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10a7 7 0 0 0 14 0M12 17v5M8 22h8"/></svg>';
const PAIS = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="8" r="3.2"/><path d="M5.5 20a6.5 6.5 0 0 1 13 0"/></svg>';
function renderAbas() {
  const icone = (id, cands) => cands.map(l => S.vocab.find(w => w.label === l && (id === "nucleo" || grupoDe(w) === id))).find(Boolean) || S.by[S.pg[id][0]];
  $("#abas").innerHTML = PAGINAS.filter(([id]) => S.pg[id]?.length).map(([id, nome, cor, c]) =>
    `<button type="button" data-page="${id}" aria-pressed="${id === S.page}" style="--cat:var(--c-${cor})"><span class="likely" aria-hidden="true"></span><img src="${pic(icone(id, c).id)}" alt="">${nome}</button>`).join("")
    + (opt.pranchasFoto || []).map(f => `<button type="button" data-page="${f.id}" aria-pressed="${f.id === S.page}" style="--cat:var(--coral)"><img src="${f.thumb}" alt="" style="border-radius:10px;object-fit:cover">${f.nome.replace(/[<>&"]/g, "")}</button>`).join("")
    + `<button type="button" id="b-treino" aria-label="Treinar palavras">${MIC}Treinar</button>`
    + `<button type="button" id="b-pais" aria-label="Área dos pais (segure)"><span class="ring" id="gear-ring"></span>${PAIS}</button>`;
}
function renderGrade() {
  const { c, r, n } = grade(), ids = S.pg[S.page] || [], total = Math.max(1, Math.ceil(ids.length / n));
  S.sub = Math.min(S.sub, total - 1);
  const parte = ids.slice(S.sub * n, S.sub * n + n);
  const g = $("#grid"); g.style.setProperty("--cols", c); g.style.setProperty("--rows", r);
  g.innerHTML = parte.map(id => tile(S.by[id])).join("") + '<div class="tile empty"></div>'.repeat(n - parte.length);
  $("#pg-prev").disabled = S.sub === 0; $("#pg-next").disabled = S.sub >= total - 1;
  document.querySelectorAll("#abas button[data-page]").forEach(b => b.setAttribute("aria-pressed", b.dataset.page === S.page));
  // áudio das peças visíveis já fica pronto: o toque toca na hora, sem esperar a rede
  clearTimeout(S.tAudio); S.tAudio = setTimeout(() => voz.preparar(parte), 250);
  // pré-carrega a próxima parte da página
  ids.slice((S.sub + 1) * n, (S.sub + 2) * n).forEach(id => { const i = new Image(); i.src = pic(id); });
}
/* ---------- linha do adulto: o que ele disse vira contexto para as sugestões ---------- */
const temMic = !!(window.SpeechRecognition || window.webkitSpeechRecognition) || (!!navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== "undefined");
const MIC_AD = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10a7 7 0 0 0 14 0M12 17v5"/></svg>';
function renderParceiro(estado) {
  const el = $("#partner"), mic = opt.ouvirAdulto !== false;
  el.hidden = !opt.parceiro && !mic;
  const esc = s => s.replace(/[<>&"]/g, "");
  const ouvido = S.adp.length
    ? `<span class="adp" title="${esc(S.adTexto)}">${S.adp.map(id => `<img src="${pic(id)}" alt="${esc(S.by[id]?.label || "")}">`).join("")}<button type="button" class="limpar" data-acao="limpar" aria-label="Limpar o que o adulto disse">×</button></span>`
    : S.adTexto ? `<span class="adp vazio">"${esc(S.adTexto)}"</span>` : "";
  el.innerHTML = `<b>Adulto</b>`
    + (mic ? `<button type="button" class="mic-adulto${estado === "ouvindo" ? " on" : ""}" data-acao="mic" ${temMic ? "" : "hidden"} aria-label="Segure e fale com a criança">${MIC_AD}${estado === "ouvindo" ? "Ouvindo…" : estado === "pensando" ? "Entendendo…" : estado || "Segure e fale"}</button>`
      + `<button type="button" data-acao="escrever" aria-label="Escrever o que você disse">${temMic ? "✎" : "✎ Escrever o que disse"}</button>` : "")
    + ouvido
    + (opt.parceiro ? PARCEIRO.map(([k, l]) => `<button type="button" data-k="${k}" aria-pressed="${k === S.adulto}">${l}</button>`).join("") : "");
}
async function usarFalaDoAdulto(texto) {
  const F = await carregarFormas();
  S.adTexto = texto; S.adp = textoParaPictos(texto, F);
  if (S.spoken) { S.phrase = []; S.spoken = false; renderFrase(); }   // pergunta nova: frase nova
  renderParceiro(); prever();
}
function ligarMicAdulto() {
  const el = $("#partner"); let parar = null, mod = null, segurando = false;
  el.addEventListener("pointerdown", async e => {
    const b = e.target.closest('[data-acao="mic"]'); if (!b) return;
    e.preventDefault(); voz.desbloquear(); segurando = true;
    mod ??= await import("./adulto.js");
    if (!mod.podeOuvir()) return renderParceiro("Use ✎ para escrever");
    // computador sem ditado: baixa o Whisper antes (só uma vez), sem gravar ainda
    if (mod.precisaBaixar() && !S.escutaPronta) {
      try { await mod.carregarEscuta(p => renderParceiro(`Baixando ${Math.round(p * 100)}%`)); S.escutaPronta = true; return renderParceiro("Pronto! Segure e fale"); }
      catch { return renderParceiro("Use ✎ para escrever"); }
    }
    try {
      const p = await mod.comecarEscuta();
      if (!segurando) { p().catch(() => {}); return renderParceiro("Segure enquanto fala"); }   // soltou antes de o microfone abrir
      parar = p; renderParceiro("ouvindo");
    } catch { parar = null; renderParceiro("Sem microfone · use ✎"); }
  });
  const soltar = async () => {
    segurando = false;
    if (!parar) return; const p = parar; parar = null;
    renderParceiro("pensando");
    try {
      const texto = await p();
      if (!texto) return renderParceiro("Não ouvi · segure e fale");
      await usarFalaDoAdulto(texto);
    } catch (err) { console.warn(err); renderParceiro(String(err.message).includes("not-allowed") ? "Microfone bloqueado · use ✎" : "Não entendi · use ✎"); }
  };
  ["pointerup", "pointercancel"].forEach(ev => el.addEventListener(ev, soltar));
  el.addEventListener("pointerleave", e => { if (e.target === el) soltar(); });
}

/* guarda todos os pictogramas no cache aos poucos, sem atrapalhar o uso */
function aquecerCache() {
  const ids = S.vocab.map(w => w.id); let i = 0;
  const passo = () => {
    const lote = ids.slice(i, i + 8); i += 8;
    Promise.all(lote.map(id => fetch(pic(id)).catch(() => {}))).then(() => { if (i < ids.length) setTimeout(passo, 250); });
  };
  setTimeout(passo, 4000); // só depois da tela pronta, em lotes pequenos
}

/* engrenagem: segurar 1,2 s para ir à área dos pais */
function segurarParaAbrir(btn, ring, acao) {
  let t0 = 0, raf = 0;
  const tick = () => { const p = Math.min(1, (performance.now() - t0) / 1200); ring.style.setProperty("--p", p); if (p >= 1) { parar(); acao(); } else raf = requestAnimationFrame(tick); };
  const parar = () => { cancelAnimationFrame(raf); ring.style.setProperty("--p", 0); };
  btn.addEventListener("pointerdown", e => { e.preventDefault(); t0 = performance.now(); raf = requestAnimationFrame(tick); });
  ["pointerup", "pointerleave", "pointercancel"].forEach(ev => btn.addEventListener(ev, parar));
  btn.addEventListener("keydown", e => { if (e.key === "Enter") acao(); });
}

async function iniciar() {
  if (!perfil) return;
  document.documentElement.dataset.genero = perfil.genero;
  const { vocab, by } = await carregarVocab();
  S.vocab = vocab; S.by = by; S.pg = montarPaginas(vocab);
  // pranchas por foto (criadas pelos adultos): palavras básicas + o vocabulário da cena
  const base = ["eu", "querer", "ver", "gostar", "não", "mais"].map(l => vocab.find(w => w.label === l)?.id).filter(Boolean);
  for (const f of opt.pranchasFoto || []) S.pg[f.id] = [...base, ...f.ids.filter(id => by[id] && !base.includes(id))];
  pred = new Preditor(vocab, by, perfil);
  renderAbas(); renderGrade(); renderParceiro(); renderFrase(); renderAgora();
  // enquanto o modelo chega, a faixa já mostra as palavras mais usadas (nunca fica vazia)
  S.top = vocab.slice(0, 6).map(w => w.id);
  $("#sugg").innerHTML = (S.agoraHtml || "") + (opt.sugestoes ? S.top.map(id => tile(by[id])).join("") : "");
  setInterval(() => { renderAgora(); if (!S.calmaAte || S.calmaAte < Date.now()) prever(); }, 60000);  // rotina muda com o relógio
  $("#loading").hidden = true;            // a prancha aparece antes do modelo terminar de carregar
  await pred.iniciar(); if (opt.preditor === "ngram") await pred.carregarNgram();
  prever();

  // busca o áudio já ao encostar o dedo: quando o toque termina, o som está pronto
  ["#grid", "#sugg"].forEach(sel => $(sel).addEventListener("pointerdown", e => { const t = e.target.closest(".tile[data-id]"); if (t && t.dataset.id !== END) { voz.desbloquear(); voz.carregar(t.dataset.id); } }));
  addEventListener("resize", () => renderGrade());
  $("#grid").addEventListener("click", e => { const t = e.target.closest(".tile:not(.empty)"); if (t) escolher(t.dataset.id, false); });
  $("#sugg").addEventListener("click", e => { const t = e.target.closest(".tile[data-id]"); if (t) escolher(t.dataset.id, true); });
  $("#abas").addEventListener("click", e => {
    const b = e.target.closest("button"); if (!b || b.id === "b-pais") return;
    if (b.id === "b-treino") return abrirTreino();
    S.toques++; S.toquesFrase++; S.page = b.dataset.page; S.sub = 0; renderGrade();
  });
  $("#partner").addEventListener("click", e => {
    const b = e.target.closest("button"); if (!b) return;
    if (b.dataset.acao === "limpar") { S.adp = []; S.adTexto = ""; renderParceiro(); return prever(); }
    if (b.dataset.acao === "escrever") { const t = prompt("O que você disse para a criança?", S.adTexto || ""); if (t != null) usarFalaDoAdulto(t.trim()); return; }
    if (!b.dataset.k) return;
    S.adulto = b.dataset.k; renderParceiro(); prever();
  });
  ligarMicAdulto();
  $("#pg-prev").addEventListener("click", () => { S.sub--; S.toquesFrase++; renderGrade(); });
  $("#pg-next").addEventListener("click", () => { S.sub++; S.toquesFrase++; renderGrade(); });
  $("#b-back").addEventListener("click", () => { voz.desbloquear(); observarToque("apagar"); if (S.spoken) S.spoken = false; else S.phrase.pop(); renderFrase(); prever(); });
  $("#b-speak").addEventListener("click", falarFrase);
  segurarParaAbrir($("#b-pais"), $("#gear-ring"), () => location.href = "pais.html");
  aquecerCache();
  if ("serviceWorker" in navigator && location.protocol === "https:") navigator.serviceWorker.register("sw.js").catch(() => {});
}

async function abrirTreino() {
  voz.desbloquear();
  const m = await import("./treino.js");
  m.abrir({ perfil, opt, vocab: S.vocab, by: S.by, voz });
}

iniciar().catch(e => { $("#loading").innerHTML = `<div><img src="assets/zuli.png" alt=""><span>Não deu para abrir (${e.message}).</span></div>`; });
