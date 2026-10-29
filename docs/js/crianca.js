// Área da criança: prancha fixa, sugestões, Zuli fala a frase, botão Treinar.
import { END, pic, perfis, registro, carregarVocab, PAGINAS, montarPaginas, grupoDe, Voz, Preditor, periodoAgora } from "./core.js";

const $ = s => document.querySelector(s);
const PARCEIRO = [
  ["nenhuma", "ninguém falou"], ["o_que_quer", "o que você quer?"], ["como_esta", "como você está?"], ["onde", "onde?"],
  ["o_que_fazer", "o que vamos fazer?"], ["o_que_aconteceu", "o que aconteceu?"], ["sim_nao", "sim ou não?"],
  ["quem", "quem?"], ["gosta", "gostou?"], ["comentario", "comentou algo"], ["cumprimento", "oi / tchau"],
];

const perfil = perfis.ativo();
if (!perfil) location.replace("pais.html#novo");
const opt = perfil ? perfis.opt(perfil) : {};
const S = { vocab: [], by: {}, pg: {}, page: "nucleo", sub: 0, phrase: [], spoken: false, adulto: "nenhuma", top: [],
  toques: 0, daSugestao: 0, toquesFrase: 0 };
const voz = new Voz(perfil?.genero, opt.velocidade, opt.fonteVoz === "aparelho");
let pred;

function tile(w) {
  if (w === END) return `<button type="button" class="tile end" data-id="${END}" aria-label="Falar a frase"><img src="assets/zuli.png" alt=""><span>falar</span></button>`;
  return `<button type="button" class="tile cat-${w.cor}" data-id="${w.id}" aria-label="${w.label}"><img src="${pic(w.id)}" alt="" decoding="async" draggable="false"><span>${w.label}</span></button>`;
}
const ctx = () => ({ periodo: periodoAgora(opt), local: opt.local, adulto: S.adulto });

/* ---------- sugestões ---------- */
function prever() {
  const prefix = S.spoken ? [] : S.phrase;
  const ranked = pred.prever(ctx(), prefix, opt.preditor === "ngram");
  let top = ranked.slice(0, 6);
  const e = top.find(([k]) => k === END);
  if (e) top = [...top.filter(([k]) => k !== END), e]; // "falar" sempre no último espaço
  S.top = top.map(([k]) => k);
  $("#sugg").innerHTML = opt.sugestoes ? S.top.map(k => tile(k === END ? END : S.by[k])).join("") : "";
  voz.preparar(S.top.filter(k => k !== END));
  // página provável do próximo pictograma (sem contar o que já está nas sugestões)
  const pp = {};
  for (const [k, v] of ranked) { if (k === END || S.top.includes(k)) continue; const g = grupoDe(S.by[k]); pp[g] = (pp[g] || 0) + v; }
  const best = Object.entries(pp).sort((a, b) => b[1] - a[1])[0];
  document.querySelectorAll("#abas button[data-page]").forEach(b => b.classList.toggle("hint", opt.conceito && !!best && b.dataset.page === best[0] && b.dataset.page !== S.page && best[1] > .2));
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
    registro.add(perfil, { tipo: "frase", ids: [...S.phrase], sug: S.daSugestao, toques: S.toquesFrase, adulto: S.adulto, local: opt.local });
  }
  S.spoken = true; S.daSugestao = 0; S.toquesFrase = 0; S.adulto = "nenhuma"; renderParceiro();
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
  // pré-carrega a próxima parte da página
  ids.slice((S.sub + 1) * n, (S.sub + 2) * n).forEach(id => { const i = new Image(); i.src = pic(id); });
}
function renderParceiro() {
  const el = $("#partner"); el.hidden = !opt.parceiro;
  el.innerHTML = `<b>Adulto:</b>` + PARCEIRO.map(([k, l]) => `<button type="button" data-k="${k}" aria-pressed="${k === S.adulto}">${l}</button>`).join("");
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
  pred = new Preditor(vocab, by, perfil);
  renderAbas(); renderGrade(); renderParceiro(); renderFrase();
  $("#loading").hidden = true;            // a prancha aparece antes do modelo terminar de carregar
  await pred.iniciar(); if (opt.preditor === "ngram") await pred.carregarNgram();
  prever();

  // busca o áudio já ao encostar o dedo: quando o toque termina, o som está pronto
  ["#grid", "#sugg"].forEach(sel => $(sel).addEventListener("pointerdown", e => { const t = e.target.closest(".tile[data-id]"); if (t && t.dataset.id !== END) { voz.desbloquear(); voz.carregar(t.dataset.id); } }));
  addEventListener("resize", () => renderGrade());
  $("#grid").addEventListener("click", e => { const t = e.target.closest(".tile:not(.empty)"); if (t) escolher(t.dataset.id, false); });
  $("#sugg").addEventListener("click", e => { const t = e.target.closest(".tile"); if (t) escolher(t.dataset.id, true); });
  $("#abas").addEventListener("click", e => {
    const b = e.target.closest("button"); if (!b || b.id === "b-pais") return;
    if (b.id === "b-treino") return abrirTreino();
    S.toques++; S.toquesFrase++; S.page = b.dataset.page; S.sub = 0; renderGrade();
  });
  $("#partner").addEventListener("click", e => { const b = e.target.closest("button"); if (!b) return; S.adulto = b.dataset.k; renderParceiro(); prever(); });
  $("#pg-prev").addEventListener("click", () => { S.sub--; S.toquesFrase++; renderGrade(); });
  $("#pg-next").addEventListener("click", () => { S.sub++; S.toquesFrase++; renderGrade(); });
  $("#b-back").addEventListener("click", () => { voz.desbloquear(); if (S.spoken) S.spoken = false; else S.phrase.pop(); renderFrase(); prever(); });
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
