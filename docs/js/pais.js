// Área dos pais: PIN, perfil da criança, painel de desenvolvimento, treino de fala e ajustes.
import { store, perfis, registro, hashPin, carregarVocab, pic, Voz, OPT_PADRAO, exportarCrianca, importarCrianca, apagarTudo, grupoDe, VOZES, vozDoPerfil } from "./core.js";

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
    <a class="small" href="./">Voltar ao início</a></div>`;
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
        <button type="button" class="wz-voz" data-voz="gravada" aria-pressed="${d.fonteVoz === "gravada"}"><b>Voz do Zuli</b><small>Gravada, ${d.genero === "m" ? "voz de menino" : "voz feminina jovem"}. Responde na hora e funciona sem internet.</small><span class="ouvir" data-ouvir="${d.genero === "m" ? "mc" : "f"}">▶ ouvir</span></button>
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
          perfis.salvarOpt(nova, Object.assign(perfis.opt(nova), { fonteVoz: d.fonteVoz, voz: d.genero === "m" ? "mc" : "f" }));
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
      <details class="wz-cores"><summary><b>Por que os desenhos têm cores?</b></summary><p class="small muted">Cada tipo de palavra tem sempre a mesma cor (chave Fitzgerald, padrão de comunicação alternativa). Assim a criança aprende onde procurar.</p>${legendaCores()}</details>
      <a class="btn primary big" href="prancha.html">Abrir a prancha de ${esc(d.nome)}</a></div>`;
  }
  $("#gate").onclick = e => {
    const b = e.target.closest("button, [data-ouvir]"); if (!b) return;
    if (b.dataset.ouvir) { e.stopPropagation(); return b.dataset.ouvir === "sistema" ? new Voz(d.genero === "m" ? "mc" : "f", 1, true).falar([{ chave: "x", texto: "Oi! Eu sou o Zuli!" }]) : voz(b.dataset.ouvir); }
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

// Esqueci o PIN: confirma com o nome de uma criança cadastrada e cria um PIN novo (os dados ficam).
function esqueciPin() {
  $("#gate").innerHTML = `<form class="card" id="f-esq"><img src="assets/zuli.png" alt=""><h1>Criar um PIN novo</h1>
    <p class="muted">Para confirmar que é um adulto, digite o nome de uma criança cadastrada neste aparelho. Os dados dela continuam guardados.</p>
    <input type="text" id="esq-nome" autocomplete="off" required style="width:100%;font-size:1.1rem;padding:12px">
    <p class="small" id="esq-msg" style="min-height:1.4em;color:var(--coral)"></p>
    <button type="submit" class="btn primary big">Continuar</button><a class="small" href="pais.html">Voltar</a></form>`;
  $("#f-esq").onsubmit = e => {
    e.preventDefault();
    const n = $("#esq-nome").value.trim().toLowerCase();
    if (!perfis.lista().some(p => p.nome.trim().toLowerCase() === n)) { $("#esq-msg").textContent = "Esse nome não está cadastrado aqui."; return; }
    store.del("pin"); portao();
  };
}

async function portao() {
  const h = store.get("pin", null);
  if (!perfis.lista().length) return boasVindas();  // nenhuma criança cadastrada: sempre a recepção (mesmo com PIN antigo)
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
  pinPad("Área dos adultos", "Digite o PIN.", async (p, msg) => { if (await hashPin(p) === h) { sess.set(true); entrar(); } else msg("PIN errado. Tente de novo."); });
  $("#gate .card").insertAdjacentHTML("beforeend", `<button type="button" class="btn link small" id="b-esqueci">Esqueci o PIN</button>`);
  $("#b-esqueci").onclick = esqueciPin;
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
  const vz = P ? vozDoPerfil(P, perfis.opt(P)) : null;
  $("#h-sub").textContent = P ? `${P.genero === "m" ? "menino" : "menina"}${P.idade ? `, ${P.idade} anos` : ""} · ${vz.sistema ? "voz do aparelho" : "voz " + VOZES.find(v => v.id === vz.pasta).nome.toLowerCase()}` : "";
}
function aba(v) {
  if (!["desenvolvimento", "treino", "rotina", "foto", "perfil", "ajustes", "guia"].includes(v)) v = "desenvolvimento";
  document.querySelectorAll("nav.tabs button").forEach(b => b.setAttribute("aria-selected", b.dataset.v === v));
  document.querySelectorAll("section.view").forEach(s => s.hidden = s.id !== "v-" + v);
  if (!P && v !== "perfil") return;
  ({ desenvolvimento: renderDev, treino: renderTreino, perfil: () => renderPerfil(false), ajustes: renderAjustes, guia: renderGuia, rotina: renderRotina, foto: renderFoto })[v]();
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
function renderDevBase() {
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


/* ---------------- resumo da semana (texto para pais e terapeuta) ----------------
   Montado por regras a partir do histórico deste aparelho: cada frase só aparece se os dados sustentam. */
const NOME_GRUPO = { pessoas: "pessoas", acoes: "ações", sentir: "sentimentos e descrições", comida: "comida", brincar: "brincadeiras",
  corpo: "corpo e higiene", lugares: "lugares e objetos", conversa: "conversa e perguntas" };
const PERIODO = h => h < 12 ? "manhã" : h < 18 ? "tarde" : "noite";
function resumoSemana() {
  const log = registro.ler(P), agora = Date.now(), ele = P.genero === "m" ? "ele" : "ela", Ele = P.genero === "m" ? "Ele" : "Ela";
  const sem = log.filter(e => agora - e.t < 7 * DIA), ant = log.filter(e => agora - e.t >= 7 * DIA && agora - e.t < 14 * DIA);
  const fr = sem.filter(e => e.tipo === "frase"), frAnt = ant.filter(e => e.tipo === "frase");
  const textos = [], sugestoes = [];
  if (!fr.length) return { textos: [`Ainda não há frases de ${P.nome} nesta semana.`], sugestoes: ["Use a prancha junto com a criança, tocando você também nos desenhos (modelagem)."] };
  const media = l => l.reduce((a, e) => a + e.ids.length, 0) / Math.max(1, l.length);
  const pct = (a, b) => Math.round(100 * a / Math.max(1, b));
  // volume e tamanho
  let t = `Nesta semana, ${P.nome} montou ${fr.length} ${fr.length === 1 ? "frase" : "frases"} com o Zuli`;
  if (frAnt.length) t += fr.length >= frAnt.length ? ` (${fr.length - frAnt.length >= 0 ? "+" : ""}${fr.length - frAnt.length} em relação à semana anterior)` : ` (${frAnt.length - fr.length} a menos que na semana anterior)`;
  t += `, com ${media(fr).toFixed(1).replace(".", ",")} pictogramas por frase em média`;
  if (frAnt.length >= 3 && media(fr) - media(frAnt) >= 0.3) t += `, frases mais longas que antes`;
  textos.push(t + ".");
  // iniciativa
  const comAdulto = fr.filter(e => e.adulto && e.adulto !== "nenhuma");
  if (comAdulto.length >= 3) textos.push(`${pct(fr.length - comAdulto.length, fr.length)}% das frases foram iniciadas por ${ele}, sem pergunta do adulto antes; as outras foram respostas.`);
  // assuntos por período do dia
  const porPer = {};
  for (const e of fr) for (const id of e.ids) { const w = V.by[id]; if (!w) continue; const per = PERIODO(new Date(e.t).getHours()); (porPer[per] ??= {})[grupoDe(w)] = (porPer[per]?.[grupoDe(w)] || 0) + 1; }
  const destaques = Object.entries(porPer).map(([per, g]) => { const tot = Object.values(g).reduce((a, b) => a + b, 0);
    const [top, n] = Object.entries(g).filter(([k]) => !["pessoas", "acoes", "conversa"].includes(k)).sort((a, b) => b[1] - a[1])[0] || [];
    return top && n / tot >= 0.2 && tot >= 6 ? `pela ${per}, o assunto mais frequente foi ${NOME_GRUPO[top]}` : null; }).filter(Boolean);
  if (destaques.length) textos.push(destaques.join("; ").replace(/^p/, "P") + ".");
  // emoções
  const tot = fr.reduce((a, e) => a + e.ids.length, 0);
  const sentir = fr.flatMap(e => e.ids).filter(id => V.by[id] && grupoDe(V.by[id]) === "sentir");
  const emocoes = [...new Set(sentir.map(id => V.by[id].label))];
  if (emocoes.length) textos.push(`${Ele} usou palavras de sentimentos e descrições ${sentir.length} ${sentir.length === 1 ? "vez" : "vezes"} (${emocoes.slice(0, 6).join(", ")}).`);
  if (tot >= 20 && sentir.length / tot < 0.05) {
    textos.push(`Sentimentos apareceram pouco: ${pct(sentir.length, tot)}% dos pictogramas.`);
    sugestoes.push("Reforçar a página Sentir: nomear emoções em situações reais (\"você está bravo\") tocando o pictograma junto.");
  }
  // palavras novas
  const antesIds = new Set(log.filter(e => e.tipo === "frase" && agora - e.t >= 7 * DIA).flatMap(e => e.ids));
  const novas = [...new Set(fr.flatMap(e => e.ids))].filter(id => !antesIds.has(id) && V.by[id]);
  if (novas.length && antesIds.size) textos.push(`Palavras usadas pela primeira vez: ${novas.slice(0, 10).map(id => V.by[id].label).join(", ")}${novas.length > 10 ? ` e mais ${novas.length - 10}` : ""}.`);
  // sugestões da faixa
  const pics = fr.reduce((a, e) => a + e.ids.length, 0), sug = fr.reduce((a, e) => a + (e.sug || 0), 0);
  if (pics >= 10) textos.push(`${pct(sug, pics)}% dos pictogramas vieram das sugestões do Zuli${pct(sug, pics) < 15 ? ", o que indica que a faixa ainda é pouco usada" : ""}.`);
  if (pics >= 10 && pct(sug, pics) < 15) sugestoes.push("Mostrar a faixa amarela de sugestões: tocar nela junto com a criança algumas vezes.");
  // calma
  const calma = sem.filter(e => e.tipo === "calma");
  if (calma.length) {
    const h = calma.map(e => new Date(e.t).getHours()), moda = h.sort((a, b) => h.filter(x => x === b).length - h.filter(x => x === a).length)[0];
    textos.push(`O Zuli percebeu toques muito rápidos ou repetidos ${calma.length} ${calma.length === 1 ? "vez" : "vezes"} e ofereceu os atalhos de calma${calma.length >= 2 ? `, principalmente por volta das ${moda}h` : ""}.`);
    if (calma.length >= 2) sugestoes.push(`Observar o que acontece por volta das ${moda}h (fome, cansaço, barulho, transição de atividade) e antecipar com a rotina visual.`);
  }
  // treino de fala
  const tr = sem.filter(e => e.tipo === "treino");
  if (tr.length) {
    const ok = [...new Set(tr.filter(e => e.nota === 3).map(e => e.id))].filter(id => V.by[id]);
    const dif = [...new Set(tr.filter(e => e.nota === 1).map(e => e.id))].filter(id => V.by[id] && !ok.includes(id));
    textos.push(`No treino de fala foram ${tr.length} tentativas${ok.length ? `; ${ele} conseguiu bem: ${ok.slice(0, 6).map(id => V.by[id].label).join(", ")}` : ""}.`);
    if (dif.length) sugestoes.push(`Praticar de novo: ${dif.slice(0, 5).map(id => V.by[id].label).join(", ")}.`);
  }
  if (!sugestoes.length) sugestoes.push("Continuar usando a prancha nas rotinas do dia e comemorar cada frase.");
  return { textos, sugestoes };
}
function renderDev() {
  renderDevBase();
  const { textos, sugestoes } = resumoSemana();
  const txt = `Resumo da semana — ${P.nome}\n\n${textos.join("\n")}\n\nSugestões:\n${sugestoes.map(x => "• " + x).join("\n")}\n\n(Gerado pelo Zuli a partir do uso neste aparelho.)`;
  $("#v-desenvolvimento").insertAdjacentHTML("afterbegin", `<div class="card resumo"><div class="row" style="justify-content:space-between"><h3>Resumo da semana</h3>
      <button type="button" class="btn" id="b-copiar">Copiar para enviar à terapeuta</button></div>
    ${textos.map(x => `<p>${esc(x)}</p>`).join("")}
    <p><b>Sugestões para a próxima semana</b></p><ul style="margin:0;padding-left:1.2em">${sugestoes.map(x => `<li>${esc(x)}</li>`).join("")}</ul>
    <p class="muted small">Montado automaticamente a partir do uso neste aparelho. Não substitui a avaliação de um profissional.</p></div>`);
  $("#b-copiar").onclick = async e => {
    try { await navigator.clipboard.writeText(txt); e.target.textContent = "Copiado!"; }
    catch { const ta = document.createElement("textarea"); ta.value = txt; document.body.append(ta); ta.select(); document.execCommand("copy"); ta.remove(); e.target.textContent = "Copiado!"; }
  };
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


/* ---------------- rotina visual ---------------- */
const DIAS = ["D", "S", "T", "Q", "Q", "S", "S"];
function renderRotina() {
  const r = (O.rotina || []).slice().sort((a, b) => a.inicio.localeCompare(b.inicio));
  // sugestões aprendidas: assuntos que se repetem no mesmo horário
  const log = registro.ler(P).filter(e => e.tipo === "frase"), nucleo = new Set(V.vocab.slice(0, 30).map(w => w.id));
  const porHora = {};
  for (const e of log) for (const id of e.ids) {
    const w = V.by[id]; if (!w || nucleo.has(id) || ["pessoas", "acoes", "conversa", "sentir"].includes(grupoDe(w))) continue;
    const h = new Date(e.t).getHours(); (porHora[h] ??= {})[id] = (porHora[h][id] || 0) + 1;
  }
  const aprendidas = Object.entries(porHora).flatMap(([h, c]) => { const tot = Object.values(c).reduce((a, b) => a + b, 0);
    return Object.entries(c).filter(([id, n]) => n >= 3 && n / tot >= 0.3).map(([id, n]) => ({ h: +h, id: +id, n })); })
    .filter(x => !r.some(i => String(i.id) === String(x.id))).sort((a, b) => b.n - a.n).slice(0, 4);
  const hh = h => String(h).padStart(2, "0") + ":00";
  $("#v-rotina").innerHTML = `
    <div class="card"><h3>Rotina visual de ${esc(P.nome)}</h3>
      <p class="small muted">Na hora de cada atividade, a prancha mostra um quadro <b>Agora</b> com o pictograma dela, sempre no mesmo lugar (à esquerda das sugestões). Saber o que vem agora diminui a ansiedade. A atividade também fica mais provável nas sugestões.</p>
      ${r.length ? r.map((x, i) => V.by[x.id] ? `<div class="rot-item"><img src="${pic(x.id)}" alt=""><div><b>${esc(V.by[x.id].label)}</b><div class="h">${x.inicio}–${x.fim} · ${x.dias?.length && x.dias.length < 7 ? x.dias.map(d => DIAS[d]).join(" ") : "todos os dias"}</div></div>
        <button type="button" class="btn perigo" data-rm="${i}">Tirar</button></div>` : "").join("") : `<div class="empty">Nenhuma atividade ainda. Exemplos: 12:00 almoço, 14:00 fono, 20:30 dormir.</div>`}
    </div>
    ${aprendidas.length ? `<div class="card"><h3>O Zuli percebeu</h3>${aprendidas.map(x => `<div class="rot-item"><img src="${pic(x.id)}" alt=""><div>Por volta das <b>${x.h}h</b>, ${esc(P.nome)} costuma falar de <b>${esc(V.by[x.id].label)}</b> <span class="muted small">(${x.n} vezes)</span></div>
      <button type="button" class="btn" data-sug="${x.h}|${x.id}">Adicionar à rotina</button></div>`).join("")}</div>` : ""}
    <form class="card" id="f-rot"><h3>Adicionar atividade</h3>
      <div class="row"><input type="search" id="rot-busca" placeholder="Buscar pictograma (ex.: almoço, fono, escola)" style="flex:1" autocomplete="off"></div>
      <div class="chips" id="rot-res"></div>
      <div class="row"><span>Escolhido:</span><b id="rot-esc" class="muted">nenhum</b></div>
      <div class="row"><label>Das <input type="time" id="rot-ini" value="12:00" required></label><label>às <input type="time" id="rot-fim" value="13:00" required></label></div>
      <div class="dias">${DIAS.map((d, i) => `<label title="${["domingo", "segunda", "terça", "quarta", "quinta", "sexta", "sábado"][i]}"><input type="checkbox" value="${i}" checked>${d}</label>`).join("")}</div>
      <div class="row"><button type="submit" class="btn primary">Adicionar</button><span class="small" id="rot-msg"></span></div>
    </form>`;
  let escolhido = null;
  const salvar = () => { perfis.salvarOpt(P, O); renderRotina(); };
  $("#rot-busca").oninput = e => { const q = e.target.value.trim().toLowerCase();
    $("#rot-res").innerHTML = q ? V.vocab.filter(w => w.label.toLowerCase().startsWith(q)).slice(0, 8).map(w => `<button type="button" class="chip" data-esc="${w.id}"><img src="${pic(w.id)}" alt="">${esc(w.label)}</button>`).join("") : ""; };
  $("#v-rotina").onclick = e => {
    const b = e.target.closest("button"); if (!b) return;
    if (b.dataset.esc) { escolhido = +b.dataset.esc; $("#rot-esc").textContent = V.by[escolhido].label; $("#rot-esc").classList.remove("muted"); }
    if (b.dataset.rm) { O.rotina = r.filter((_, i) => i !== +b.dataset.rm); salvar(); }
    if (b.dataset.sug) { const [h, id] = b.dataset.sug.split("|").map(Number); O.rotina = [...r, { inicio: hh(h), fim: hh(Math.min(23, h + 1)), id, dias: [] }]; salvar(); }
  };
  $("#f-rot").onsubmit = e => {
    e.preventDefault();
    if (!escolhido) { $("#rot-msg").textContent = "Escolha um pictograma."; return; }
    const ini = $("#rot-ini").value, fim = $("#rot-fim").value;
    if (fim <= ini) { $("#rot-msg").textContent = "O fim precisa ser depois do início."; return; }
    const dias = [...document.querySelectorAll("#f-rot .dias input:checked")].map(i => +i.value);
    O.rotina = [...r, { inicio: ini, fim, id: escolhido, dias: dias.length === 7 ? [] : dias }]; salvar();
  };
}


/* ---------------- prancha por foto ---------------- */
function renderFoto() {
  const lista = O.pranchasFoto || [];
  $("#v-foto").innerHTML = `
    <div class="card"><h3>Prancha por foto</h3>
      <p class="small muted">Tire uma foto do lugar (zoológico, festa, parque, consultório). O Zuli olha a foto <b>neste aparelho</b> e sugere os desenhos que combinam com a cena. Você revisa e salva: vira uma aba nova no fim da prancha de ${esc(P.nome)}. A foto não é enviada para lugar nenhum.</p>
      <div style="display:flex;gap:10px;flex-wrap:wrap">
        <label class="btn primary big" for="foto-cam">Tirar foto</label>
        <label class="btn big" for="foto-in">Escolher das fotos</label>
      </div>
      <input type="file" id="foto-cam" accept="image/*" capture="environment" hidden>
      <input type="file" id="foto-in" accept="image/*" hidden>
      <div id="foto-area"></div></div>
    ${lista.length ? `<div class="card"><h3>Pranchas por foto salvas</h3>${lista.map((f, i) => `<div class="pf-item"><img src="${f.thumb}" alt=""><div><b>${esc(f.nome)}</b><div class="small muted">${f.ids.length} desenhos</div></div>
      <button type="button" class="btn perigo" data-rmf="${i}">Tirar</button></div>`).join("")}</div>` : ""}`;
  $("#v-foto").onclick = e => { const b = e.target.closest("[data-rmf]"); if (!b) return; O.pranchasFoto = lista.filter((_, i) => i !== +b.dataset.rmf); perfis.salvarOpt(P, O); renderFoto(); };
  $("#foto-cam").onchange = e => $("#foto-in").onchange(e);
  $("#foto-in").onchange = async e => {
    const f = e.target.files[0]; if (!f) return;
    const area = $("#foto-area");
    area.innerHTML = `<img class="foto-prev" src="${URL.createObjectURL(f)}" alt="Foto escolhida"><p class="small" id="foto-st">Olhando a foto… (na primeira vez o Zuli baixa ~90 MB)</p><div class="carga"><i id="foto-bar"></i></div>`;
    try {
      const { analisarFoto, miniatura } = await import("./foto.js");
      const notas = await analisarFoto(f, x => { const b = $("#foto-bar"); if (b) b.style.width = Math.round(x * 100) + "%"; });
      const cands = notas.slice(0, 30).filter(x => V.by[x.id]).map(x => x.id), sel = new Set(cands.slice(0, 12));
      const thumb = await miniatura(f);
      area.innerHTML = `<img class="foto-prev" src="${thumb}" alt="" style="max-height:120px">
        <label class="field"><span>Nome da prancha</span><input type="text" id="foto-nome" maxlength="18" value="Passeio" style="max-width:280px"></label>
        <p class="small muted">Toque para tirar ou pôr de volta. Os mais prováveis vêm primeiro.</p>
        <div class="escolha" id="foto-esc">${cands.map(id => `<button type="button" data-id="${id}" aria-pressed="${sel.has(id)}"><img src="${pic(id)}" alt="">${esc(V.by[id].label)}</button>`).join("")}</div>
        <div class="row"><input type="search" id="foto-busca" placeholder="Adicionar outro desenho (ex.: girafa)" autocomplete="off"></div><div class="chips" id="foto-res"></div>
        <div class="row"><button type="button" class="btn primary" id="foto-salvar">Salvar na prancha de ${esc(P.nome)}</button><span class="small" id="foto-msg"></span></div>`;
      $("#foto-esc").onclick = ev => { const b = ev.target.closest("button[data-id]"); if (!b) return; const id = +b.dataset.id; sel.has(id) ? sel.delete(id) : sel.add(id); b.setAttribute("aria-pressed", sel.has(id)); };
      $("#foto-busca").oninput = ev => { const q = ev.target.value.trim().toLowerCase();
        $("#foto-res").innerHTML = q ? V.vocab.filter(w => w.label.toLowerCase().startsWith(q)).slice(0, 8).map(w => `<button type="button" class="chip" data-add="${w.id}"><img src="${pic(w.id)}" alt="">${esc(w.label)} +</button>`).join("") : ""; };
      $("#foto-res").onclick = ev => { const b = ev.target.closest("[data-add]"); if (!b) return; const id = +b.dataset.add;
        if (!cands.includes(id)) { cands.unshift(id); $("#foto-esc").insertAdjacentHTML("afterbegin", `<button type="button" data-id="${id}" aria-pressed="true"><img src="${pic(id)}" alt="">${esc(V.by[id].label)}</button>`); }
        sel.add(id); $("#foto-esc").querySelector(`[data-id="${id}"]`)?.setAttribute("aria-pressed", "true"); };
      $("#foto-salvar").onclick = () => {
        const ids = cands.filter(id => sel.has(id));
        if (!ids.length) { $("#foto-msg").textContent = "Escolha pelo menos um desenho."; return; }
        const nova = { id: "foto-" + Date.now().toString(36), nome: $("#foto-nome").value.trim() || "Foto", ids, thumb };
        O.pranchasFoto = [nova, ...lista].slice(0, 3); perfis.salvarOpt(P, O); renderFoto();
        $("#foto-area").innerHTML = `<p>Pronto! A aba <b>${esc(nova.nome)}</b> está no fim da prancha de ${esc(P.nome)}. <a href="prancha.html">Abrir a prancha</a></p>`;
      };
    } catch (err) { console.warn(err); area.insertAdjacentHTML("beforeend", `<p class="small" style="color:var(--coral)">Não deu para analisar a foto agora (${esc(err.message || err)}). Precisa de internet na primeira vez.</p>`); }
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
      <div class="row"><button type="button" class="btn" id="p-nova">Adicionar outra criança</button></div>
      <p class="note">Cada criança tem sua voz, seu aprendizado e seu histórico, guardados só neste aparelho.</p></div>` : "")
    + `<div class="card"><h3>Levar para outro aparelho</h3>
      <p class="small muted">Baixe um arquivo com tudo de uma criança (ajustes, o que a prancha aprendeu e o histórico) e abra no outro tablet, celular ou computador. Também serve para enviar à terapeuta.</p>
      <div class="row">${P ? `<button type="button" class="btn" id="p-exportar">Baixar dados de ${esc(P.nome)}</button>` : ""}
        <label class="btn" for="p-importar">Abrir arquivo do Zuli</label><input type="file" id="p-importar" accept=".json,application/json" hidden></div>
      <p class="small" id="p-msg" style="min-height:1.4em"></p></div>
    <div class="card"><h3>Trocar de família</h3>
      <p class="small muted">Apaga todas as crianças, os históricos e o PIN deste aparelho, e volta para a recepção. Baixe os dados antes, se quiser guardar.</p>
      <div class="row"><button type="button" class="btn perigo" id="p-apagar-tudo">Apagar tudo deste aparelho</button></div></div>`;
  let gen = (novo || !P) ? "f" : P.genero;
  $("#p-gen").onclick = e => { const b = e.target.closest("button"); if (!b) return; gen = b.dataset.v; $("#p-gen").querySelectorAll("button").forEach(x => x.setAttribute("aria-pressed", x === b)); };
  $("#p-ouvir").onclick = () => { const v = new Voz(gen === "m" ? "mc" : "f"); v.desbloquear(); v.falar([{ chave: "zuli_0", texto: "Oi! Eu sou o Zuli!" }]); };
  $("#f-perfil").onsubmit = e => {
    e.preventDefault();
    const nome = $("#p-nome").value.trim(), idade = +$("#p-idade").value || null; if (!nome) return;
    if (novo || !P) { perfis.novo(nome, gen, idade); location.href = "prancha.html"; return; }
    Object.assign(P, { nome, genero: gen, idade }); perfis.salvar(P); cabecalho(); renderPerfil(false);
  };
  el.querySelectorAll("[data-usar]").forEach(b => b.onclick = () => { perfis.usar(b.dataset.usar); P = perfis.ativo(); O = perfis.opt(P); cabecalho(); renderPerfil(false); });
  el.querySelectorAll("[data-rm]").forEach(b => b.onclick = () => {
    if (b.dataset.conf !== "1") { b.dataset.conf = "1"; b.textContent = "Toque de novo para apagar tudo"; return; }
    perfis.remover(b.dataset.rm); P = perfis.ativo(); O = P ? perfis.opt(P) : null; cabecalho(); renderPerfil(!P);
  });
  $("#p-nova")?.addEventListener("click", () => renderPerfil(true));
  $("#p-exportar")?.addEventListener("click", () => { exportarCrianca(P); $("#p-msg").textContent = "Arquivo baixado. Abra-o no outro aparelho em Criança > Abrir arquivo do Zuli."; });
  $("#p-importar").addEventListener("change", async e => {
    const f = e.target.files[0]; if (!f) return;
    try { P = await importarCrianca(f); O = perfis.opt(P); cabecalho(); renderPerfil(false); $("#p-msg").textContent = `${P.nome} foi adicionada a este aparelho.`; }
    catch (err) { $("#p-msg").textContent = err.message; }
  });
  $("#p-apagar-tudo").addEventListener("click", e => {
    const b = e.currentTarget;
    if (b.dataset.conf !== "1") { b.dataset.conf = "1"; b.textContent = "Tem certeza? Toque de novo para apagar tudo"; return; }
    apagarTudo(); location.href = "./";
  });
}


/* ---------------- guia e cores ---------------- */
// Chave Fitzgerald: cada tipo de palavra tem uma cor (padrão usado em CAA no mundo todo)
const CORES = [
  ["pessoa", "Amarelo · pessoas", "quem: eu, você, mãe, amigo", ["eu", "mãe", "amigo"]],
  ["acao", "Verde · ações", "o que faz: comer, brincar, ir", ["comer", "brincar", "ir"]],
  ["descricao", "Azul · sentir e descrever", "como é ou está: feliz, grande, quente", ["feliz", "grande", "cansado"]],
  ["coisa", "Laranja · coisas", "objetos, comidas, animais, corpo", ["bola", "suco", "cachorro"]],
  ["lugar", "Roxo · lugares", "onde: casa, escola, parque", ["casa", "escola", "parque"]],
  ["social", "Rosa · conversa", "oi, tchau, obrigado, por favor", ["oi", "obrigado", "por favor"]],
  ["negacao", "Vermelho · não e parar", "não, acabar, parar", ["não", "acabar", "parar"]],
  ["tempo", "Cinza · perguntas e tempo", "onde, quando, agora, depois", ["onde", "agora", "depois"]],
];
export function legendaCores(byLabel = {}) {
  return `<div class="cores">${CORES.map(([c, t, d, ex]) => `<div class="cor" style="--cat:var(--c-${c})"><span class="sw"></span><b>${t}</b><small>${d}</small>
    ${ex.some(l => byLabel[l]) ? `<span class="ex">${ex.filter(l => byLabel[l]).map(l => `<img src="${pic(byLabel[l].id)}" alt="${esc(l)}" title="${esc(l)}">`).join("")}</span>` : ""}</div>`).join("")}</div>`;
}
function renderGuia() {
  const byLabel = Object.fromEntries(V.vocab.map(w => [w.label, w]));
  $("#v-guia").innerHTML = `
    <div class="card"><h3>Por que os desenhos têm cores diferentes?</h3>
      <p>As cores seguem a <b>chave Fitzgerald</b>, um padrão usado em comunicação alternativa no mundo todo. Cada tipo de palavra tem sempre a mesma cor. Com o tempo, a criança aprende onde procurar: quer dizer quem, vai no amarelo; quer dizer o que fazer, vai no verde.</p>
      ${legendaCores(byLabel)}
      <p class="muted small">A mesma cor aparece na borda e no fundo do desenho, e na aba da categoria na parte de baixo da prancha.</p></div>
    <div class="card"><h3>As cores ajudam a montar a frase</h3>
      <p>A ordem mais comum de uma frase vira um caminho de cores:</p>
      <div class="ordem"><span style="background:color-mix(in srgb,var(--c-pessoa) 30%,#fff)">quem · amarelo</span>→<span style="background:color-mix(in srgb,var(--c-acao) 30%,#fff)">faz · verde</span>→<span style="background:color-mix(in srgb,var(--c-coisa) 30%,#fff)">o quê · laranja</span></div>
      <p class="muted small">Exemplo: eu (amarelo) + querer (verde) + suco (laranja).</p></div>
    <div class="card"><h3>Dicas para usar com a criança</h3>
      <ol class="small" style="margin:0;padding-left:1.2em;display:grid;gap:6px">
        <li><b>Mostre usando.</b> Fale com a criança tocando você mesmo nos desenhos. É assim que ela aprende onde está cada palavra.</li>
        <li><b>A prancha não muda de lugar.</b> Só a faixa amarela de sugestões muda. Isso ajuda a criança a decorar os caminhos.</li>
        <li><b>Toque no Zuli para falar.</b> A frase só é falada quando a criança toca no Zuli. Comemore cada frase.</li>
        <li><b>Use a linha "Adulto"</b> (em Ajustes) quando fizer uma pergunta. Ela adapta as sugestões à sua pergunta.</li>
        <li><b>Toda tentativa conta.</b> No treino de fala, o Zuli nunca diz que errou. Uma estrela já é uma tentativa.</li>
      </ol></div>`;
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
        ${chk("calma", "Atalhos de calma", "Se a criança tocar muito rápido ou repetir o mesmo desenho várias vezes, as sugestões viram pausa, parar, silêncio, abraço, música e ajuda por 20 segundos.")}
        ${chk("ouvirAdulto", "Botão \"Segure e fale\" para o adulto", "Segure o botão e fale com a criança (\"quer suco ou água?\"). O Zuli transforma o que você disse em pictogramas e sugere a resposta. Usa o reconhecimento de fala do aparelho (o mesmo do ditado do teclado); se não houver, use o ✎ para escrever.")}
        ${chk("parceiro", "Mostrar os tipos de pergunta na linha \"Adulto\"", "Você também pode tocar no tipo do que perguntou (\"o que você quer?\", \"onde?\").")}
      </div>
      <div class="card"><h3>Contexto e voz</h3>
        <div class="field"><span>Onde a prancha está sendo usada</span>${seg("local", [["casa", "casa"], ["escola", "escola"], ["rua", "passeio"], ["saude", "saúde"], ["terapia", "terapia"]])}</div>
        ${chk("periodoAuto", "Período do dia automático (pelo relógio)")}
        <div class="field"><span>Voz do Zuli</span><div class="vozes-esc" id="vozes-esc">${[...VOZES.map(v => [v.id, v.nome, v.desc]), ["aparelho", "Voz do aparelho", "A do tablet/celular (precisa ter voz em português)"]].map(([id, n, d]) => {
          const vz = vozDoPerfil(P, O), on = id === "aparelho" ? vz.sistema : !vz.sistema && vz.pasta === id;
          return `<div class="voz-op" aria-pressed="${on}"><button type="button" class="voz-sel" data-voz="${id}"><b>${n}</b><small>${d}</small></button><button type="button" class="btn" data-ouvir="${id}">▶ ouvir</button></div>`; }).join("")}</div>
          <a class="small" href="vozes.html">Comparar todas as vozes testadas</a></div>
        <div class="field"><span>Velocidade da voz</span>${seg("velocidade", [[0.85, "devagar"], [1, "normal"], [1.12, "rápida"]])}</div>
        ${chk("treinoMicrofone", "Treino com microfone", "O Zuli escuta e avalia a fala no próprio aparelho (baixa ~40 MB no celular/tablet, ~80 MB no computador, na primeira vez). Desligado, o adulto avalia.")}
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
  $("#vozes-esc").onclick = e => {
    const o = e.target.closest("[data-ouvir]"), sel = e.target.closest("[data-voz]");
    if (o) { const id = o.dataset.ouvir, v = new Voz(id === "aparelho" ? vozDoPerfil(P, O).pasta : id, O.velocidade, id === "aparelho"); v.desbloquear(); return v.falar([{ chave: "zuli_0", texto: "Oi! Eu sou o Zuli!" }]); }
    if (sel) { const id = sel.dataset.voz; if (id === "aparelho") O.fonteVoz = "aparelho"; else { O.fonteVoz = "gravada"; O.voz = id; }
      perfis.salvarOpt(P, O); cabecalho(); renderAjustes(); }
  };
  const confirmar = (b, f) => { if (b.dataset.conf !== "1") { b.dataset.conf = "1"; b.dataset.txt = b.textContent; b.textContent = "Toque de novo para confirmar"; return; } f(); b.textContent = b.dataset.txt; b.dataset.conf = ""; };
  $("#a-aprend").onclick = e => confirmar(e.target, () => { store.del(`pessoal-${P.id}`); $("#a-msg").textContent = "Aprendizado apagado."; });
  $("#a-hist").onclick = e => confirmar(e.target, () => { store.del(`log-${P.id}`); $("#a-msg").textContent = "Histórico apagado."; });
  $("#a-exportar").onclick = () => exportarCrianca(P);
  $("#a-pin").onclick = () => { store.del("pin"); sess.set(false); $("#main").hidden = true; $("#gate").hidden = false; portao(); };
}

document.querySelector("nav.tabs").addEventListener("click", e => { const b = e.target.closest("button"); if (b) { history.replaceState(null, "", "#" + b.dataset.v); aba(b.dataset.v); } });
$("#b-sair").onclick = () => { sess.set(false); location.href = "./"; };
portao();
