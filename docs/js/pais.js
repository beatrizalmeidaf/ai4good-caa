// Área dos pais: PIN, perfil da criança, painel de desenvolvimento, treino de fala e ajustes.
import { store, perfis, registro, hashPin, carregarVocab, pic, Voz, OPT_PADRAO } from "./core.js";

const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const DIA = 864e5;
let V = { vocab: [], by: {} }, P = null, O = null;
const sess = { get() { try { return sessionStorage.getItem("zuli-pais") === "1"; } catch { return false; } }, set(v) { try { v ? sessionStorage.setItem("zuli-pais", "1") : sessionStorage.removeItem("zuli-pais"); } catch {} } };

/* ---------------- PIN ---------------- */
function pinPad(titulo, texto, aoCompletar) {
  let pin = "";
  $("#gate").innerHTML = `<div class="card"><img src="assets/zuli.png" alt=""><h1>${titulo}</h1><p class="muted">${texto}</p>
    <div class="pindots">${"<i></i>".repeat(4)}</div><p class="small" id="pin-msg" style="min-height:1.4em;color:var(--coral)"></p>
    <div class="pinpad">${[1,2,3,4,5,6,7,8,9,"",0,"⌫"].map(k => k === "" ? "<span></span>" : `<button type="button" data-k="${k}" aria-label="${k === "⌫" ? "apagar" : k}">${k}</button>`).join("")}</div>
    <a class="small" href="./">Voltar para a prancha</a></div>`;
  const draw = () => $("#gate").querySelectorAll(".pindots i").forEach((d, i) => d.classList.toggle("on", i < pin.length));
  $("#gate .pinpad").onclick = async e => {
    const k = e.target.closest("button")?.dataset.k; if (k == null) return;
    pin = k === "⌫" ? pin.slice(0, -1) : (pin + k).slice(0, 4); draw();
    if (pin.length === 4) { const p = pin; pin = ""; setTimeout(draw, 150); aoCompletar(p, m => $("#pin-msg").textContent = m); }
  };
}
/* ---------------- primeiro acesso: assistente em 5 passos ---------------- */
function boasVindas() {
  const d = { nome: "", genero: "f", idade: "", fonteVoz: "gravada" };
  let passo = 0, pin1 = null;
  const PASSOS = 5;
  const topo = () => `<div class="wz-top">${passo > 0 && passo < 4 ? `<button type="button" class="btn link" data-a="voltar">← voltar</button>` : "<span></span>"}
    <div class="wz-dots" aria-label="Passo ${passo + 1} de ${PASSOS}">${Array.from({ length: PASSOS }, (_, i) => `<i class="${i < passo ? "ok" : i === passo ? "on" : ""}"></i>`).join("")}</div><span></span></div>`;
  const voz = g => { const v = new Voz(g); v.desbloquear(); v.falar([{ chave: "zuli_0", texto: "Oi! Eu sou o Zuli!" }]); };
  function tela() {
    const el = $("#gate");
    if (passo === 0) el.innerHTML = `<div class="wizard">${topo()}
      <img class="wz-zuli" src="assets/zuli.png" alt="">
      <h1>Oi! Eu sou o Zuli.</h1>
      <p class="lead">Eu ajudo crianças que ainda não falam (ou falam pouco) a se comunicar com desenhos.</p>
      <div class="wz-como">
        <div><span class="n">1</span><b>A criança toca nos desenhos</b><small>Os desenhos ficam sempre no mesmo lugar.</small></div>
        <div><span class="n">2</span><b>Eu sugiro o próximo</b><small>Uma faixa amarela mostra os desenhos mais prováveis.</small></div>
        <div><span class="n">3</span><b>Eu falo a frase</b><small>Quando a criança toca em mim, eu falo em voz alta.</small></div>
      </div>
      <p class="muted small">Vamos configurar em 1 minuto. Tudo fica guardado só neste aparelho.</p>
      <button type="button" class="btn primary big" data-a="seguir">Começar</button></div>`;
    if (passo === 1) el.innerHTML = `<form class="wizard" id="wz-f">${topo()}
      <h1>Quem vai usar o Zuli?</h1>
      <label class="field"><span>Nome ou apelido da criança</span><input type="text" id="wz-nome" required maxlength="30" value="${esc(d.nome)}" placeholder="ex.: Lia" autocomplete="off"></label>
      <div class="field"><span>A criança é</span><div class="seg big" id="wz-gen"><button type="button" data-v="f" aria-pressed="${d.genero === "f"}">menina</button><button type="button" data-v="m" aria-pressed="${d.genero === "m"}">menino</button></div>
        <small class="muted">Isso escolhe a voz do Zuli (feminina ou masculina). Dá para mudar depois.</small></div>
      <label class="field"><span>Idade (opcional)</span><input type="number" id="wz-idade" min="1" max="99" value="${esc(d.idade)}" style="max-width:120px"></label>
      <button type="submit" class="btn primary big">Continuar</button></form>`;
    if (passo === 2) el.innerHTML = `<div class="wizard">${topo()}
      <h1>Como o Zuli vai falar?</h1>
      <p class="muted">Toque para ouvir e escolha.</p>
      <div class="wz-vozes">
        <button type="button" class="wz-voz" data-voz="gravada" aria-pressed="${d.fonteVoz === "gravada"}"><b>Voz do Zuli</b><small>Gravada, ${d.genero === "m" ? "masculina" : "feminina"}. Responde na hora e funciona sem internet.</small><span class="ouvir" data-ouvir="${d.genero}">▶ ouvir</span></button>
        <button type="button" class="wz-voz" data-voz="aparelho" aria-pressed="${d.fonteVoz === "aparelho"}"><b>Voz do tablet</b><small>A voz do próprio aparelho. Pode soar mais natural em frases longas.</small><span class="ouvir" data-ouvir="sistema">▶ ouvir</span></button>
      </div>
      <button type="button" class="btn primary big" data-a="seguir">Continuar</button></div>`;
    if (passo === 3) {
      pinPad(pin1 ? "Confirme o PIN" : "Crie um PIN para os adultos",
        pin1 ? "Digite os mesmos 4 números de novo." : `A prancha é de ${esc(d.nome)}. Os ajustes e o acompanhamento ficam numa área separada, protegida por este PIN, para ninguém mudar nada sem querer.`,
        async (p, msg) => {
          if (!pin1) { pin1 = p; return tela(); }
          if (p !== pin1) { pin1 = null; msg("Os PINs não batem. Vamos de novo."); setTimeout(tela, 1200); return; }
          store.set("pin", await hashPin(p)); sess.set(true);
          const nova = perfis.novo(d.nome, d.genero, +d.idade || null);
          perfis.salvarOpt(nova, Object.assign(perfis.opt(nova), { fonteVoz: d.fonteVoz }));
          passo = 4; tela();
        });
      $("#gate .card").insertAdjacentHTML("afterbegin", topo());
      $("#gate a.small")?.remove();
    }
    if (passo === 4) el.innerHTML = `<div class="wizard">${topo()}
      <img class="wz-zuli festa" src="assets/zuli.png" alt="">
      <h1>Tudo pronto!</h1>
      <p class="lead">Agora é só entregar o tablet para ${esc(d.nome)}.</p>
      <div class="wz-dica"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="8" r="3.2"/><path d="M5.5 20a6.5 6.5 0 0 1 13 0"/></svg>
        <p>Para voltar a esta área, <b>segure por 1 segundo</b> o botão com este desenho, no canto de baixo da prancha, e digite o PIN.</p></div>
      <a class="btn primary big" href="./">Abrir a prancha de ${esc(d.nome)}</a></div>`;
  }
  $("#gate").onclick = e => {
    const b = e.target.closest("button, [data-ouvir]"); if (!b) return;
    if (b.dataset.ouvir) { e.stopPropagation(); return b.dataset.ouvir === "sistema" ? new Voz(d.genero, 1, true).falar([{ chave: "x", texto: "Oi! Eu sou o Zuli!" }]) : voz(b.dataset.ouvir); }
    if (b.dataset.voz) { d.fonteVoz = b.dataset.voz; document.querySelectorAll(".wz-voz").forEach(x => x.setAttribute("aria-pressed", x === b)); return; }
    if (b.closest("#wz-gen") && b.dataset.v) { d.genero = b.dataset.v; b.parentElement.querySelectorAll("button").forEach(x => x.setAttribute("aria-pressed", x === b)); return; }
    if (b.dataset.a === "voltar") { passo--; pin1 = null; return tela(); }
    if (b.dataset.a === "seguir") { passo++; return tela(); }
  };
  $("#gate").onsubmit = e => {
    e.preventDefault(); d.nome = $("#wz-nome").value.trim(); d.idade = $("#wz-idade").value;
    if (d.nome) { passo = 2; tela(); }
  };
  tela();
}

async function portao() {
  const h = store.get("pin", null);
  if (!h && !perfis.lista().length) return boasVindas();
  if (!h) {
    let primeiro = null;
    const pedir = () => pinPad("Bem-vindo ao Zuli", "Crie um PIN de 4 números. Ele protege esta área, para a criança não mudar os ajustes sem querer.", async (p, msg) => {
      if (!primeiro) { primeiro = p; pinPad("Confirme o PIN", "Digite o mesmo PIN de novo.", async (p2, msg2) => {
        if (p2 !== primeiro) { primeiro = null; msg2("Os PINs não batem. Vamos de novo."); setTimeout(pedir, 1200); return; }
        store.set("pin", await hashPin(p2)); sess.set(true); entrar();
      }); }
    });
    return pedir();
  }
  if (sess.get()) return entrar();
  pinPad("Área dos pais", "Digite o PIN.", async (p, msg) => { if (await hashPin(p) === h) { sess.set(true); entrar(); } else msg("PIN errado. Tente de novo."); });
}

/* ---------------- entrada ---------------- */
async function entrar() {
  $("#gate").hidden = true; $("#main").hidden = false;
  V = await carregarVocab();
  P = perfis.ativo();
  if (!P || location.hash === "#novo") { aba("perfil"); return renderPerfil(true); }
  O = perfis.opt(P);
  cabecalho(); aba(location.hash.slice(1) || "desenvolvimento");
}
function cabecalho() {
  $("#h-nome").textContent = P ? `${P.nome}` : "Área dos pais";
  $("#h-sub").textContent = P ? `${P.genero === "m" ? "menino" : "menina"}${P.idade ? `, ${P.idade} anos` : ""} · voz ${P.genero === "m" ? "masculina" : "feminina"}` : "";
}
function aba(v) {
  if (!["desenvolvimento", "treino", "perfil", "ajustes"].includes(v)) v = "desenvolvimento";
  document.querySelectorAll("nav.tabs button").forEach(b => b.setAttribute("aria-selected", b.dataset.v === v));
  document.querySelectorAll("section.view").forEach(s => s.hidden = s.id !== "v-" + v);
  if (!P && v !== "perfil") return;
  ({ desenvolvimento: renderDev, treino: renderTreino, perfil: () => renderPerfil(false), ajustes: renderAjustes })[v]();
}

/* ---------------- gráficos (SVG simples) ---------------- */
function barras(vals, labels, { h = 150, titulo = "" } = {}) {
  const W = 560, pad = { l: 28, r: 8, t: 10, b: 22 }, max = Math.max(1, ...vals), step = (W - pad.l - pad.r) / vals.length;
  const ticks = [...new Set([0, Math.ceil(max / 2), max])];
  return `<svg class="chart" viewBox="0 0 ${W} ${h}" role="img" aria-label="${esc(titulo)}">
    ${ticks.map(t => { const y = pad.t + (h - pad.t - pad.b) * (1 - t / max); return `<line class="grid" x1="${pad.l}" x2="${W - pad.r}" y1="${y}" y2="${y}"/><text x="${pad.l - 6}" y="${y + 4}" text-anchor="end">${t}</text>`; }).join("")}
    ${vals.map((v, i) => { const bh = (h - pad.t - pad.b) * v / max, x = pad.l + i * step + 2;
      return `<rect class="bar" x="${x}" y="${h - pad.b - bh}" width="${Math.max(2, step - 4)}" height="${bh}" rx="3"><title>${labels[i]}: ${v}</title></rect>`; }).join("")}
    ${labels.map((l, i) => i % Math.ceil(vals.length / 7) === 0 || i === vals.length - 1 ? `<text x="${pad.l + i * step + step / 2}" y="${h - 6}" text-anchor="middle">${l}</text>` : "").join("")}
  </svg>`;
}
function linha(vals, labels, { h = 150, titulo = "" } = {}) {
  const W = 560, pad = { l: 34, r: 12, t: 12, b: 22 }, max = Math.max(1, ...vals);
  const x = i => pad.l + (W - pad.l - pad.r) * (vals.length === 1 ? .5 : i / (vals.length - 1)), y = v => pad.t + (h - pad.t - pad.b) * (1 - v / max);
  const pts = vals.map((v, i) => `${x(i)},${y(v)}`).join(" ");
  return `<svg class="chart" viewBox="0 0 ${W} ${h}" role="img" aria-label="${esc(titulo)}">
    ${[...new Set([0, Math.round(max / 2), max])].map(t => `<line class="grid" x1="${pad.l}" x2="${W - pad.r}" y1="${y(t)}" y2="${y(t)}"/><text x="${pad.l - 6}" y="${y(t) + 4}" text-anchor="end">${t}</text>`).join("")}
    <polygon class="area" points="${x(0)},${y(0)} ${pts} ${x(vals.length - 1)},${y(0)}"/>
    <polyline class="line" points="${pts}"/>
    <circle class="dot" cx="${x(vals.length - 1)}" cy="${y(vals.at(-1))}" r="5"><title>${labels.at(-1)}: ${vals.at(-1)}</title></circle>
    ${vals.length > 1 ? `<text x="${x(0)}" y="${h - 6}" text-anchor="start">${labels[0]}</text><text x="${x(vals.length - 1)}" y="${h - 6}" text-anchor="end">${labels.at(-1)}</text>` : `<text x="${x(0)}" y="${h - 6}" text-anchor="middle">${labels[0]}</text>`}
  </svg>`;
}

/* ---------------- desenvolvimento ---------------- */
const diaKey = t => { const d = new Date(t); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; }; // dia no fuso local
const curto = d => d.slice(8, 10) + "/" + d.slice(5, 7);
function renderDev() {
  const log = registro.ler(P), frases = log.filter(e => e.tipo === "frase"), agora = Date.now();
  const el = $("#v-desenvolvimento");
  if (!frases.length) {
    el.innerHTML = `<div class="empty">Ainda não há frases de ${esc(P.nome)}. Quando ${P.genero === "m" ? "ele" : "ela"} montar uma frase e tocar no Zuli, ela aparece aqui.</div>
      <p class="note">O painel mostra: quantas frases por dia, quantas palavras diferentes ${P.genero === "m" ? "ele" : "ela"} já usou, o tamanho das frases, as palavras favoritas e as últimas conversas.</p>`;
    return;
  }
  const semana = frases.filter(e => agora - e.t < 7 * DIA), antes = frases.filter(e => agora - e.t >= 7 * DIA && agora - e.t < 14 * DIA);
  const media = l => l.length ? l.reduce((a, e) => a + e.ids.length, 0) / l.length : 0;
  const distintas = new Set(frases.flatMap(e => e.ids));
  const sug = semana.reduce((a, e) => a + (e.sug || 0), 0), pics = semana.reduce((a, e) => a + e.ids.length, 0);
  const delta = (a, b, fmt = v => v) => b ? `<span class="delta ${a >= b ? "up" : "down"}">${a >= b ? "▲" : "▼"} ${fmt(Math.abs(a - b))} vs. semana anterior</span>` : `<span class="delta muted">primeira semana</span>`;
  // séries de 14 dias
  const dias = Array.from({ length: 14 }, (_, i) => diaKey(agora - (13 - i) * DIA));
  const porDia = dias.map(d => frases.filter(e => diaKey(e.t) === d).length);
  // crescimento do vocabulário (palavras diferentes acumuladas por dia de uso)
  const vistos = new Set(), cres = [], cresL = [];
  for (const d of [...new Set(frases.map(e => diaKey(e.t)))].sort()) { frases.filter(e => diaKey(e.t) === d).forEach(e => e.ids.forEach(i => vistos.add(i))); cres.push(vistos.size); cresL.push(curto(d)); }
  const cont = {}; frases.forEach(e => e.ids.forEach(i => cont[i] = (cont[i] || 0) + 1));
  const top = Object.entries(cont).sort((a, b) => b[1] - a[1]).slice(0, 14);
  const ADULTO = { o_que_quer: "O que você quer?", como_esta: "Como você está?", onde: "Onde?", o_que_fazer: "O que vamos fazer?", o_que_aconteceu: "O que aconteceu?", sim_nao: "Sim ou não?", quem: "Quem?", gosta: "Gostou?", comentario: "comentário", cumprimento: "oi/tchau" };
  el.innerHTML = `
    <div class="kpis">
      <div class="kpi"><span class="v">${semana.length}</span><span class="d">frases nos últimos 7 dias</span>${delta(semana.length, antes.length)}</div>
      <div class="kpi"><span class="v">${distintas.size}</span><span class="d">palavras diferentes já usadas</span></div>
      <div class="kpi"><span class="v">${media(semana).toFixed(1).replace(".", ",")}</span><span class="d">pictogramas por frase (7 dias)</span>${delta(media(semana), media(antes), v => v.toFixed(1).replace(".", ","))}</div>
      <div class="kpi"><span class="v">${pics ? Math.round(100 * sug / pics) : 0}%</span><span class="d">dos toques vieram das sugestões do Zuli</span></div>
    </div>
    <div class="two">
      <div class="card"><h3>Frases por dia</h3>${barras(porDia, dias.map(curto), { titulo: "Frases por dia nos últimos 14 dias" })}</div>
      <div class="card"><h3>Palavras diferentes ao longo do tempo</h3>${linha(cres, cresL, { titulo: "Crescimento do vocabulário" })}</div>
    </div>
    <div class="card"><h3>Palavras que ${esc(P.nome)} mais usa</h3><div class="pics">${top.map(([id, n]) => V.by[id] ? `<div class="pic"><img src="${pic(id)}" alt=""><span>${esc(V.by[id].label)}</span><b>${n}×</b></div>` : "").join("")}</div></div>
    <div class="card"><h3>Últimas frases</h3><div class="frases">${frases.slice(-12).reverse().map(e => `
      <div class="frase"><time>${new Date(e.t).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}</time>
        <div class="seq">${e.ids.map(i => V.by[i] ? `<img src="${pic(i)}" alt="${esc(V.by[i].label)}" title="${esc(V.by[i].label)}">` : "").join("")}</div>
        <small>${esc(e.ids.map(i => V.by[i]?.label).join(" "))}${e.adulto && e.adulto !== "nenhuma" ? ` · respondendo a "${ADULTO[e.adulto] || e.adulto}"` : ""}</small></div>`).join("")}</div></div>`;
}

/* ---------------- treino ---------------- */
function renderTreino() {
  const log = registro.ler(P).filter(e => e.tipo === "treino"), por = {};
  for (const e of log) (por[e.id] ??= []).push(e);
  const linhas = Object.entries(por).map(([id, l]) => {
    const notas = l.map(e => e.nota), ult = notas.slice(-3), m = ult.reduce((a, b) => a + b, 0) / ult.length;
    const status = ult.length >= 2 && ult.slice(-2).every(n => n === 3) ? ["ok", "aprendida"] : m < 2.5 && l.length >= 2 ? ["treinar", "precisa treinar"] : ["novo", "em progresso"];
    const u = l.at(-1); return { id, l, m, status, ouvido: u.parecido != null ? `parecido com a palavra: ${u.parecido}%` : (u.ouvido || "") };
  }).filter(r => V.by[r.id]).sort((a, b) => a.m - b.m);
  const escolhidas = O.treinoPalavras || [];
  const el = $("#v-treino");
  el.innerHTML = `
    <div class="kpis">
      <div class="kpi"><span class="v">${log.length}</span><span class="d">tentativas de fala</span></div>
      <div class="kpi"><span class="v">${linhas.filter(r => r.status[0] === "ok").length}</span><span class="d">palavras aprendidas (2 acertos seguidos)</span></div>
      <div class="kpi"><span class="v">${linhas.filter(r => r.status[0] === "treinar").length}</span><span class="d">palavras que precisam de mais treino</span></div>
    </div>
    <div class="card"><h3>Palavras para treinar</h3>
      <p class="muted small">Escolha até 5 palavras. Se a lista ficar vazia, o Zuli escolhe sozinho: palavras que ${esc(P.nome)} usa e as que tiveram nota baixa.</p>
      <div class="chips" id="tr-chips">${escolhidas.map(id => V.by[id] ? `<button type="button" class="chip" data-rm="${id}" aria-label="Tirar ${esc(V.by[id].label)}"><img src="${pic(id)}" alt="">${esc(V.by[id].label)} ✕</button>` : "").join("") || '<span class="muted small">Automático</span>'}</div>
      <div class="row"><input type="search" id="tr-busca" placeholder="Buscar palavra (ex.: água)" aria-label="Buscar palavra"><div class="chips" id="tr-res"></div></div>
    </div>
    <div class="card"><h3>Progresso por palavra</h3>
      ${linhas.length ? `<div class="tbl"><table><thead><tr><th></th><th>Palavra</th><th>Situação</th><th class="num">Tentativas</th><th>Últimas notas</th><th>Última tentativa</th></tr></thead><tbody>
      ${linhas.map(r => `<tr><td><img src="${pic(r.id)}" alt=""></td><td>${esc(V.by[r.id].label)}</td><td><span class="pill ${r.status[0]}">${r.status[1]}</span></td><td class="num">${r.l.length}</td>
        <td class="stars">${r.l.slice(-5).map(e => "★".repeat(e.nota) + "☆".repeat(3 - e.nota)).join(" ")}</td><td class="muted small">${esc(r.ouvido)}</td></tr>`).join("")}</tbody></table></div>`
      : `<div class="empty">Nenhum treino ainda. Na prancha, toque em <b>Treinar</b>: o Zuli fala a palavra, a criança repete e ele escuta.</div>`}
    </div>
    <p class="note">A nota mede o quanto a fala combina com a palavra pedida, comparando com outras palavras. Em testes, acertou 90% das vezes e aceitou a palavra errada 4% das vezes. Use como sinal de tendência, não como diagnóstico. O áudio não é gravado nem enviado.</p>`;
  $("#tr-busca").oninput = e => {
    const q = e.target.value.trim().toLowerCase();
    $("#tr-res").innerHTML = q ? V.vocab.filter(w => w.label.toLowerCase().startsWith(q)).slice(0, 8).map(w => `<button type="button" class="chip" data-add="${w.id}"><img src="${pic(w.id)}" alt="">${esc(w.label)} +</button>`).join("") : "";
  };
  el.onclick = e => {
    const b = e.target.closest("button"); if (!b) return;
    if (b.dataset.rm) O.treinoPalavras = escolhidas.filter(i => String(i) !== b.dataset.rm);
    else if (b.dataset.add && escolhidas.length < 5 && !escolhidas.includes(+b.dataset.add)) O.treinoPalavras = [...escolhidas, +b.dataset.add];
    else return;
    perfis.salvarOpt(P, O); renderTreino();
  };
}

/* ---------------- perfil ---------------- */
function renderPerfil(novo) {
  const lista = perfis.lista(), el = $("#v-perfil");
  const form = (p = {}) => `<form class="card" id="f-perfil">
      <h3>${p.id ? "Dados da criança" : "Nova criança"}</h3>
      <label class="field"><span>Nome ou apelido</span><input type="text" id="p-nome" required maxlength="30" value="${esc(p.nome || "")}" placeholder="ex.: Lia"></label>
      <div class="field"><span>A criança é</span><div class="seg" id="p-gen"><button type="button" data-v="f" aria-pressed="${p.genero !== "m"}">menina · voz feminina</button><button type="button" data-v="m" aria-pressed="${p.genero === "m"}">menino · voz masculina</button></div></div>
      <label class="field"><span>Idade (opcional)</span><input type="number" id="p-idade" min="1" max="99" value="${esc(p.idade || "")}" style="max-width:120px"></label>
      <div class="row"><button type="submit" class="btn primary">${p.id ? "Salvar" : "Criar e abrir a prancha"}</button><button type="button" class="btn" id="p-ouvir">Ouvir a voz</button></div>
    </form>`;
  el.innerHTML = (novo || !P ? form() : form(P)) + (lista.length ? `<div class="card"><h3>Crianças neste aparelho</h3>
      ${lista.map(p => `<div class="row" style="justify-content:space-between"><span><b>${esc(p.nome)}</b> <span class="muted small">${p.genero === "m" ? "menino" : "menina"}${p.id === P?.id ? " · ativa" : ""}</span></span>
        <span class="row">${p.id !== P?.id ? `<button type="button" class="btn" data-usar="${p.id}">Usar</button>` : ""}<button type="button" class="btn perigo" data-rm="${p.id}">Apagar</button></span></div>`).join("")}
      <div><button type="button" class="btn" id="p-nova">Adicionar outra criança</button></div>
      <p class="note">Cada criança tem sua voz, seu aprendizado e seu histórico, guardados só neste aparelho. Para usar em vários aparelhos e compartilhar com a terapeuta, o próximo passo é uma conta na nuvem.</p></div>` : "");
  let gen = (novo || !P) ? "f" : P.genero;
  $("#p-gen").onclick = e => { const b = e.target.closest("button"); if (!b) return; gen = b.dataset.v; $("#p-gen").querySelectorAll("button").forEach(x => x.setAttribute("aria-pressed", x === b)); };
  $("#p-ouvir").onclick = () => { const v = new Voz(gen); v.desbloquear(); v.falar([{ chave: "zuli_0", texto: "Oi! Eu sou o Zuli!" }]); };
  $("#f-perfil").onsubmit = e => {
    e.preventDefault();
    const nome = $("#p-nome").value.trim(), idade = +$("#p-idade").value || null; if (!nome) return;
    if (novo || !P) { perfis.novo(nome, gen, idade); location.href = "./"; return; }
    Object.assign(P, { nome, genero: gen, idade }); perfis.salvar(P); cabecalho(); renderPerfil(false);
  };
  el.querySelectorAll("[data-usar]").forEach(b => b.onclick = () => { perfis.usar(b.dataset.usar); P = perfis.ativo(); O = perfis.opt(P); cabecalho(); renderPerfil(false); });
  el.querySelectorAll("[data-rm]").forEach(b => b.onclick = () => {
    if (b.dataset.conf !== "1") { b.dataset.conf = "1"; b.textContent = "Toque de novo para apagar tudo"; return; }
    perfis.remover(b.dataset.rm); P = perfis.ativo(); O = P ? perfis.opt(P) : null; cabecalho(); renderPerfil(!P);
  });
  $("#p-nova")?.addEventListener("click", () => renderPerfil(true));
}

/* ---------------- ajustes ---------------- */
function renderAjustes() {
  const el = $("#v-ajustes");
  const seg = (k, itens) => `<div class="seg" data-k="${k}">${itens.map(([v, l]) => `<button type="button" data-v="${v}" aria-pressed="${String(O[k]) === String(v)}">${l}</button>`).join("")}</div>`;
  const chk = (k, t, d = "") => `<label class="check"><input type="checkbox" data-k="${k}" ${O[k] ? "checked" : ""}><span>${t}${d ? `<br><span class="muted small">${d}</span>` : ""}</span></label>`;
  el.innerHTML = `
    <div class="two">
      <div class="card"><h3>Prancha</h3>
        <div class="field"><span>Tamanho dos pictogramas</span>${seg("grade", [["4x3", "enorme (12)"], ["5x3", "grande (15)"], ["6x4", "médio (24)"], ["8x5", "pequeno (40)"]])}</div>
        ${chk("sugestoes", "Mostrar as sugestões do Zuli")}
        ${chk("conceito", "Marcar a página provável do próximo pictograma", "Um ponto amarelo aparece na página onde deve estar a próxima palavra.")}
        ${chk("falarCada", "Falar cada pictograma ao tocar")}
        ${chk("parceiro", "Mostrar a linha \"Adulto\"", "Você toca no que perguntou (\"o que você quer?\", \"onde dói?\") e as sugestões se adaptam.")}
      </div>
      <div class="card"><h3>Contexto e voz</h3>
        <div class="field"><span>Onde a prancha está sendo usada</span>${seg("local", [["casa", "casa"], ["escola", "escola"], ["rua", "passeio"], ["saude", "saúde"], ["terapia", "terapia"]])}</div>
        ${chk("periodoAuto", "Período do dia automático (pelo relógio)")}
        <div class="field"><span>Voz</span>${seg("fonteVoz", [["gravada", "voz do Zuli (funciona offline)"], ["aparelho", "voz do tablet/celular"]])}</div>
        <p class="small"><a href="vozes.html">Ouvir e comparar as vozes que estamos testando</a></p>
        <div class="field"><span>Velocidade da voz</span>${seg("velocidade", [[0.85, "devagar"], [1, "normal"], [1.12, "rápida"]])}</div>
        ${chk("treinoMicrofone", "Treino com microfone", "O Zuli escuta e avalia a fala no próprio aparelho (baixa ~80 MB na primeira vez). Desligado, o adulto avalia.")}
        <div class="field"><span>Preditor</span>${seg("preditor", [["slm", "SLM de símbolos"], ["ngram", "n-grama (comparação)"]])}</div>
      </div>
    </div>
    <div class="card"><h3>Dados</h3>
      <div class="row"><button type="button" class="btn" id="a-exportar">Baixar dados de ${esc(P.nome)} (JSON)</button>
      <button type="button" class="btn perigo" id="a-aprend">Apagar o aprendizado da prancha</button>
      <button type="button" class="btn perigo" id="a-hist">Apagar o histórico</button></div>
      <p class="muted small" id="a-msg"></p>
    </div>
    <div class="card"><h3>PIN</h3><div class="row"><button type="button" class="btn" id="a-pin">Trocar o PIN</button></div></div>`;
  el.querySelectorAll(".seg").forEach(s => s.onclick = e => {
    const b = e.target.closest("button"); if (!b) return; const k = s.dataset.k;
    O[k] = typeof OPT_PADRAO[k] === "number" ? +b.dataset.v : b.dataset.v; perfis.salvarOpt(P, O);
    s.querySelectorAll("button").forEach(x => x.setAttribute("aria-pressed", x === b));
  });
  el.querySelectorAll("input[type=checkbox]").forEach(c => c.onchange = () => { O[c.dataset.k] = c.checked; perfis.salvarOpt(P, O); });
  const confirmar = (b, f) => { if (b.dataset.conf !== "1") { b.dataset.conf = "1"; b.dataset.txt = b.textContent; b.textContent = "Toque de novo para confirmar"; return; } f(); b.textContent = b.dataset.txt; b.dataset.conf = ""; };
  $("#a-aprend").onclick = e => confirmar(e.target, () => { store.del(`pessoal-${P.id}`); $("#a-msg").textContent = "Aprendizado apagado."; });
  $("#a-hist").onclick = e => confirmar(e.target, () => { store.del(`log-${P.id}`); $("#a-msg").textContent = "Histórico apagado."; });
  $("#a-exportar").onclick = () => {
    const blob = new Blob([JSON.stringify({ perfil: P, ajustes: O, historico: registro.ler(P) }, null, 1)], { type: "application/json" });
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = `zuli-${P.nome}.json`; a.click();
  };
  $("#a-pin").onclick = () => { store.del("pin"); sess.set(false); $("#main").hidden = true; $("#gate").hidden = false; portao(); };
}

document.querySelector("nav.tabs").addEventListener("click", e => { const b = e.target.closest("button"); if (b) { history.replaceState(null, "", "#" + b.dataset.v); aba(b.dataset.v); } });
$("#b-sair").onclick = () => { sess.set(false); location.href = "./"; };
portao();
