// SLM de símbolos: transformer minúsculo em JavaScript puro.
// Mesma conta do modelo PyTorch em experiments/v2/treinar.py.
// Sem dependências: roda em qualquer navegador, offline, em ~1 ms.

export async function loadSLM(base = "data/") {
  const [meta, buf] = await Promise.all([
    fetch(base + "slm.json").then(r => r.json()),
    fetch(base + "slm.bin").then(r => r.arrayBuffer()),
  ]);
  const data = meta.config.dtype === "float16" ? f16to32(new Uint16Array(buf)) : new Float32Array(buf);
  return makeSLM(meta, data);
}

export function f16to32(u16) {
  const out = new Float32Array(u16.length);
  for (let i = 0; i < u16.length; i++) {
    const h = u16[i], s = h & 0x8000 ? -1 : 1, e = (h >> 10) & 0x1f, f = h & 0x3ff;
    out[i] = e === 0 ? s * 2 ** -14 * (f / 1024) : e === 31 ? (f ? NaN : s * Infinity) : s * 2 ** (e - 15) * (1 + f / 1024);
  }
  return out;
}

export function makeSLM(meta, data) {
  const { D, layers, heads, tokens, n_symbols } = meta.config;
  const W = {};
  for (const [k, t] of Object.entries(meta.tensors)) {
    const n = t.shape.reduce((a, b) => a * b, 1);
    W[k] = data.subarray(t.offset, t.offset + n);
  }
  const V = tokens.length, dh = D / heads;
  const index = Object.fromEntries(tokens.map((t, i) => [t, i]));

  // y[o] = b[o] + sum_i x[i] * w[o, i]   (formato nn.Linear: [out, in])
  function linear(x, w, b, nIn, nOut) {
    const y = new Float32Array(nOut);
    for (let o = 0; o < nOut; o++) {
      let s = b ? b[o] : 0;
      const row = o * nIn;
      for (let i = 0; i < nIn; i++) s += x[i] * w[row + i];
      y[o] = s;
    }
    return y;
  }
  function layerNorm(x, g, b) {
    let m = 0; for (let i = 0; i < D; i++) m += x[i]; m /= D;
    let v = 0; for (let i = 0; i < D; i++) v += (x[i] - m) ** 2; v /= D;
    const r = 1 / Math.sqrt(v + 1e-5), y = new Float32Array(D);
    for (let i = 0; i < D; i++) y[i] = (x[i] - m) * r * g[i] + b[i];
    return y;
  }
  function erf(x) { // Abramowitz-Stegun 7.1.26
    const s = Math.sign(x); x = Math.abs(x);
    const t = 1 / (1 + 0.3275911 * x);
    const y = 1 - ((((1.061405429 * t - 1.453152027) * t + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-x * x);
    return s * y;
  }
  const gelu = x => 0.5 * x * (1 + erf(x / Math.SQRT2));

  // ids -> log-probabilidades do próximo token (todos os tokens)
  function forward(ids) {
    const T = ids.length;
    let h = ids.map((id, t) => {
      const v = new Float32Array(D);
      for (let i = 0; i < D; i++) v[i] = W["emb.weight"][id * D + i] + W["pos.weight"][t * D + i];
      return v;
    });
    for (let l = 0; l < layers; l++) {
      const p = `blocks.${l}.`;
      const qkv = h.map(x => linear(layerNorm(x, W[p + "ln1.weight"], W[p + "ln1.bias"]), W[p + "qkv.weight"], W[p + "qkv.bias"], D, 3 * D));
      const att = h.map(() => new Float32Array(D));
      for (let hd = 0; hd < heads; hd++) {
        const o = hd * dh;
        for (let t = 0; t < T; t++) {
          const sc = new Float32Array(t + 1);
          let mx = -Infinity;
          for (let u = 0; u <= t; u++) {
            let s = 0;
            for (let i = 0; i < dh; i++) s += qkv[t][o + i] * qkv[u][D + o + i];
            sc[u] = s / Math.sqrt(dh); if (sc[u] > mx) mx = sc[u];
          }
          let z = 0; for (let u = 0; u <= t; u++) { sc[u] = Math.exp(sc[u] - mx); z += sc[u]; }
          for (let u = 0; u <= t; u++) {
            const a = sc[u] / z;
            for (let i = 0; i < dh; i++) att[t][o + i] += a * qkv[u][2 * D + o + i];
          }
        }
      }
      h = h.map((x, t) => {
        const pr = linear(att[t], W[p + "proj.weight"], W[p + "proj.bias"], D, D);
        const x1 = x.map((v, i) => v + pr[i]);
        const f1 = linear(layerNorm(x1, W[p + "ln2.weight"], W[p + "ln2.bias"]), W[p + "fc1.weight"], W[p + "fc1.bias"], D, 4 * D).map(gelu);
        const f2 = linear(f1, W[p + "fc2.weight"], W[p + "fc2.bias"], 4 * D, D);
        return x1.map((v, i) => v + f2[i]);
      });
    }
    const last = layerNorm(h[T - 1], W["lnf.weight"], W["lnf.bias"]);
    const logits = linear(last, W["emb.weight"], null, D, V);
    let mx = -Infinity; for (const v of logits) if (v > mx) mx = v;
    let z = 0; for (const v of logits) z += Math.exp(v - mx);
    const lz = mx + Math.log(z);
    return logits.map(v => v - lz);
  }

  // Interface de alto nível: contexto + pictogramas já escolhidos -> {id: logprob} e logprob do fim de frase.
  // ctx = {periodo, local, adulto, adp}; adp = pictogramas do que o adulto disse (modelo v3, token <a>).
  // Tokens de contexto que o modelo não conhece são ignorados.
  const comAdulto = "<a>" in index, maxA = meta.config.max_adulto || 10;
  function predict(ctx, prefix) {
    // d:… = estilo de fala (modelo treinado com marca de fonte): o site pede o de criança/CAA de verdade
    const c = ["p:" + ctx.periodo, "l:" + ctx.local, "a:" + (ctx.adulto || "nenhuma"), "d:" + (meta.config.dominio || "real")].filter(t => t in index).map(t => index[t]);
    const a = comAdulto ? [index["<a>"], ...(ctx.adp || []).map(s => index[String(s)]).filter(i => i !== undefined).slice(0, maxA)] : [];
    const ids = [...c, ...a, index["<s>"], ...prefix.slice(-20).map(s => index[String(s)]).filter(i => i !== undefined)];
    const lp = forward(ids);
    const out = {};
    for (let i = 0; i < n_symbols; i++) out[tokens[i]] = lp[i];
    return { symbols: out, end: lp[index["</s>"]] };
  }
  return { predict, forward, config: meta.config };
}

// Comitê: o mesmo modelo treinado 3 vezes (sementes diferentes). A média das previsões erra menos.
// Carrega slm.bin + slm_1.bin + slm_2.bin (mesmo slm.json); se algum faltar, segue com os que vieram.
export async function loadComite(base = "data/") {
  const meta = await fetch(base + "slm.json").then(r => r.json());
  const bins = await Promise.all(["slm.bin", "slm_1.bin", "slm_2.bin"].map(f =>
    fetch(base + f).then(r => r.ok ? r.arrayBuffer() : null).catch(() => null)));
  const membros = bins.filter(Boolean).map(buf => makeSLM(meta, meta.config.dtype === "float16" ? f16to32(new Uint16Array(buf)) : new Float32Array(buf)));
  if (!membros.length) throw new Error("modelo indisponível");
  if (membros.length === 1) return membros[0];
  return {
    config: meta.config, membros: membros.length,
    predict(ctx, prefix) {
      const outs = membros.map(m => m.predict(ctx, prefix)), n = outs.length, symbols = {};
      for (const k of Object.keys(outs[0].symbols)) symbols[k] = Math.log(outs.reduce((s, o) => s + Math.exp(o.symbols[k]), 0) / n);
      return { symbols, end: Math.log(outs.reduce((s, o) => s + Math.exp(o.end), 0) / n) };
    },
  };
}
