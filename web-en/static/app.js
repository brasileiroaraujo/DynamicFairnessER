/* X-TREATS console — vanilla JS, no external dependencies. */
(function () {
  "use strict";

  // ───────────── helpers ─────────────
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const num = (v, d = 2) => (v == null || isNaN(v) ? "–" : Number(v).toFixed(d));
  const secs = (v) => (v == null ? "–" : (v >= 100 ? v.toFixed(0) : v.toFixed(1)) + " s");
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } },
  };
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  const state = {
    cfg: null, runId: null, es: null, timer: null,
    run: null, // {state, params, incs:[], expected, simulated, startedAt, ...}
  };

  // ───────────── theme ─────────────
  const savedTheme = store.get("xtreats-theme");
  if (savedTheme) document.documentElement.setAttribute("data-theme", savedTheme);
  $("theme-toggle").addEventListener("click", () => {
    const cur = document.documentElement.getAttribute("data-theme") ||
      (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const next = cur === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    store.set("xtreats-theme", next);
    renderCharts();
  });

  // ───────────── config / form ─────────────
  function radio(name, value, label, opts = {}) {
    return `<label class="${opts.cls || ""}"><input type="radio" name="${name}" value="${esc(value)}"` +
      `${opts.checked ? " checked" : ""}${opts.disabled ? " disabled" : ""}>` + opts.render(label) + `</label>`;
  }

  function renderDatasets(selected) {
    $("dataset-options").innerHTML = state.cfg.datasets.map((ds) => {
      const card = radio("dataset", ds.name, ds, {
        cls: "card-opt", checked: ds.name === selected, disabled: !ds.available,
        render: (x) => `<span class="face"><span class="name">${esc(x.name)}${x.custom ? '<span class="tag custom">uploaded</span>' : ""}</span>` +
          `<span class="meta">${esc(x.domain)} · groups by ${esc(x.groups.attribute)}` +
          `${x.available ? "" : " · unavailable"}</span></span>`,
      });
      const del = ds.custom
        ? `<button type="button" class="del" data-del="${esc(ds.name)}" title="Remove this uploaded dataset and its model" aria-label="Remove ${esc(ds.name)}">✕</button>`
        : "";
      return `<div class="card-wrap">${card}${del}</div>`;
    }).join("");
  }

  async function reloadDatasets(select) {
    const cur = (document.querySelector("input[name=dataset]:checked") || {}).value;
    state.cfg.datasets = await (await fetch("/api/datasets")).json();
    const names = state.cfg.datasets.map((d) => d.name);
    renderDatasets(select || (names.includes(cur) ? cur : state.cfg.defaults.dataset));
  }

  $("dataset-options").addEventListener("click", async (e) => {
    const b = e.target.closest("[data-del]");
    if (!b) return;
    e.preventDefault();
    const name = b.dataset.del;
    if (!confirm(`Remove "${name}" and its uploaded model from disk?`)) return;
    const r = await fetch(`/api/datasets/${encodeURIComponent(name)}`, { method: "DELETE" });
    const body = await r.json().catch(() => ({}));
    if (!r.ok) { alert(body.error || "Could not remove the dataset."); return; }
    reloadDatasets();
  });

  async function loadConfig() {
    const r = await fetch("/api/config");
    state.cfg = await r.json();
    const d = state.cfg.defaults;

    const kb = $("kafka-badge");
    kb.textContent = state.cfg.kafka.available ? "Kafka connected" : "Kafka offline · in-memory queue";
    kb.classList.add(state.cfg.kafka.available ? "ok" : "off");
    kb.title = state.cfg.kafka.detail;

    renderDatasets(d.dataset);

    // Explanation off => 0 (TREATS). On => choose 1 (LEMON) or 2 (SHAP).
    const methods = state.cfg.algorithms.filter((a) => a.id > 0);
    const defMethod = d.algorithm > 0 ? d.algorithm : methods[0].id;
    $("method-options").innerHTML = methods.map((a) => radio("method", a.id, a, {
      checked: a.id === defMethod, render: (x) => `<span>${esc(x.label.replace("X-TREATS · ", ""))}</span>`,
    })).join("");
    $("explain-toggle").checked = d.algorithm > 0;
    const syncExplain = () => {
      const on = $("explain-toggle").checked;
      $("method-wrap").hidden = !on;
      const id = on ? +document.querySelector("input[name=method]:checked").value : 0;
      $("algorithm-hint").textContent = state.cfg.algorithms.find((a) => a.id === id).hint;
    };
    $("explain-toggle").addEventListener("change", syncExplain);
    $("method-options").addEventListener("change", syncExplain);
    syncExplain();

    $("pairs-presets").innerHTML = d.pairs_options.map((n) => radio("pairs-preset", n, n, {
      checked: n === d.pairs_per_increment, render: (x) => `<span>${x}</span>`,
    })).join("");
    $("pairs").value = d.pairs_per_increment;
    $("pairs-presets").addEventListener("change", (e) => { $("pairs").value = e.target.value; });
    $("pairs").addEventListener("input", () => {
      document.querySelectorAll("input[name=pairs-preset]").forEach((r) => { r.checked = r.value === $("pairs").value; });
    });

    $("tau").value = d.tau; $("tau-range").value = Math.min(120, d.tau);
    $("tau-range").addEventListener("input", () => { $("tau").value = $("tau-range").value; });
    $("tau").addEventListener("input", () => { $("tau-range").value = Math.min(120, Math.max(5, $("tau").value || 5)); });
    $("k").value = d.k; $("max-increments").value = d.max_increments;

    if (state.cfg.active_run) attach(state.cfg.active_run);
  }

  function readForm() {
    return {
      dataset: (document.querySelector("input[name=dataset]:checked") || {}).value,
      algorithm: $("explain-toggle").checked ? +document.querySelector("input[name=method]:checked").value : 0,
      pairs_per_increment: +$("pairs").value,
      tau: +$("tau").value,
      k: +$("k").value,
      max_increments: +$("max-increments").value || 0,
      simulate: $("simulate").checked,
    };
  }

  function setBusy(busy) {
    $("start-btn").hidden = busy;
    $("stop-btn").hidden = !busy;
    document.querySelectorAll("#run-form input").forEach((el) => { el.disabled = busy; });
    if (!busy) state.cfg.datasets.forEach((ds) => {
      const el = document.querySelector(`input[name=dataset][value="${ds.name}"]`);
      if (el) el.disabled = !ds.available;
    });
  }

  $("run-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const err = $("form-error"); err.hidden = true;
    const resp = await fetch("/api/runs", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(readForm()),
    });
    const body = await resp.json();
    if (!resp.ok) { err.textContent = body.error || "Could not start the run."; err.hidden = false; return; }
    attach(body.id);
  });

  $("stop-btn").addEventListener("click", async () => {
    if (!state.runId) return;
    $("stop-btn").disabled = true;
    await fetch(`/api/runs/${state.runId}/stop`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    $("stop-btn").disabled = false;
  });

  // ───────────── run lifecycle ─────────────
  function newRun(id) {
    return { id, state: "starting", params: null, incs: [], expected: 0, simulated: false, transport: null,
      startedAt: Date.now() / 1000, endedAt: null, statusText: "Starting…", lag: null, logs: [], error: null };
  }

  async function attach(runId) {
    if (state.es) { state.es.close(); state.es = null; }
    state.runId = runId;
    state.run = newRun(runId);
    history.replaceState(null, "", "#run=" + runId);
    try {
      const s = await (await fetch(`/api/runs/${runId}`)).json();
      if (state.runId !== runId) return;
      state.run.params = s.params || null;
      if (s.started_at) state.run.startedAt = s.started_at;
    } catch (e) { /* params only drive labels */ }
    $("empty-state").hidden = true; $("run-view").hidden = false;
    $("feed").innerHTML = ""; $("log").textContent = ""; $("error-box").hidden = true;
    $("metrics-table").querySelector("tbody").innerHTML = "";
    $("sim-flag").hidden = true;
    renderAll();

    const es = new EventSource(`/api/runs/${runId}/events`);
    state.es = es;
    es.onmessage = (m) => handle(JSON.parse(m.data));
    es.addEventListener("log", (m) => appendLog(JSON.parse(m.data)));
    es.addEventListener("end", () => { es.close(); state.es = null; refreshHistory(); });
    clearInterval(state.timer);
    state.timer = setInterval(renderElapsed, 1000);
    refreshHistory();
  }

  function handle(ev) {
    const r = state.run;
    switch (ev.type) {
      case "status": r.state = ev.state; r.statusText = ev.message || ""; if (!r.startedAt || ev.seq === 1) r.startedAt = ev.t; break;
      case "transport": r.transport = ev; break;
      case "run_started":
        r.state = "running"; r.expected = ev.n_increments; r.simulated = ev.simulated;
        r.statusText = `Stream open · ${ev.n_increments} increments expected (${ev.total_pairs} pairs)`; break;
      case "increment_started":
        r.statusText = `Processing increment ${ev.index} (${ev.pairs} pairs)…`; r.lag = ev.lag_s; break;
      case "increment": addIncrement(ev); break;
      case "done": r.state = "done"; r.endedAt = ev.t; r.statusText = "Run finished."; setBusy(false); break;
      case "stopped": r.state = "stopped"; r.endedAt = ev.t; r.statusText = "Stopped by the user."; setBusy(false); break;
      case "error": r.state = "error"; r.endedAt = ev.t; r.error = ev; r.statusText = "Failed."; setBusy(false); break;
    }
    if (!["done", "stopped", "error"].includes(r.state)) setBusy(true);
    renderStatus();
    if (ev.type === "run_started") renderCharts();
  }

  function addIncrement(ev) {
    const r = state.run;
    r.incs.push(ev); r.lag = ev.timings.lag;
    r.statusText = `Increment ${ev.index} finished in ${secs(ev.timings.processing)}` +
      (ev.over_budget ? " — over the time budget" : "") + ". Waiting for the next micro-batch…";
    const isLive = !["done", "stopped", "error"].includes(r.state);
    const feed = $("feed");
    if (r.incs.length === 1) feed.innerHTML = "";
    feed.insertAdjacentHTML("afterbegin", incrementHtml(ev, isLive));
    if (isLive) feed.querySelectorAll("details.inc").forEach((d, i) => { if (i > 0) d.open = false; });
    addTableRow(ev);
    renderKpis(); renderCharts();
  }

  // ───────────── rendering: status / kpis ─────────────
  const STATE_UI = {
    starting: ["Starting", "run", ""], loading: ["Loading model", "run", ""], running: ["Running", "run", ""],
    done: ["Finished", "good", "✓"], error: ["Failed", "bad", "✕"], stopped: ["Stopped", "warn", "■"],
  };
  const ALG_LABEL = ["TREATS", "X-TREATS+LEMON", "X-TREATS+SHAP"];
  const MAX_SEGMENTS = 80;  // above this, the plain progress bar is used

  function renderRunHeader() {
    const r = state.run, p = r.params || {};
    $("run-title").textContent = p.dataset ? `${p.dataset} · ${ALG_LABEL[p.algorithm] || "?"}` : "Run";
    const chip = (k, v) => `<span class="chip">${esc(k)} <b>${esc(v)}</b></span>`;
    $("run-chips").innerHTML = p.dataset ? [
      chip("Pairs / increment", p.pairs_per_increment),
      chip("τ", p.tau + " s"),
      chip("Top-k", p.k),
      chip("Threshold", p.threshold),
      p.max_increments ? chip("Max. increments", p.max_increments) : "",
      r.transport ? chip("Transport", r.transport.name) : "",
      p.custom ? '<span class="tag custom">uploaded dataset</span>' : "",
    ].join("") : "";
  }

  function renderProgress() {
    const r = state.run, n = r.incs.length, exp = r.expected;
    const box = $("progress"), segs = $("progress-segs");
    const useSegs = exp > 0 && exp <= MAX_SEGMENTS;
    box.classList.toggle("segmented-on", useSegs);
    if (useSegs) {
      const live = !["done", "stopped", "error"].includes(r.state);
      segs.innerHTML = Array.from({ length: exp }, (_, i) => {
        const inc = r.incs[i];
        const cls = inc ? (inc.over_budget ? "over" : "ok") : (live && i === n ? "cur" : "");
        const tip = inc ? `Increment ${i + 1}: ${secs(inc.timings.processing)}${inc.over_budget ? " (over τ)" : ""}` : `Increment ${i + 1}`;
        return `<i class="${cls}" title="${tip}"></i>`;
      }).join("");
    }
    const pct = exp ? Math.round((n / exp) * 100) : 0;
    $("progress-bar").style.width = pct + "%";
    box.setAttribute("aria-valuenow", pct);
  }

  function renderAll() { renderStatus(); renderKpis(); renderCharts(); }

  function renderStatus() {
    const r = state.run; if (!r) return;
    const [label, cls, icon] = STATE_UI[r.state] || ["—", "", ""];
    const pill = $("state-pill"); pill.textContent = icon ? `${icon} ${label}` : label; pill.className = "pill " + cls;
    $("status-text").textContent = r.statusText;
    $("sim-flag").hidden = !r.simulated;
    const n = r.incs.length, exp = r.expected;
    $("f-incs").textContent = `${n} / ${exp || "–"}`;
    $("f-pairs").textContent = n ? r.incs[n - 1].pairs_processed.toLocaleString("en-US") : "0";
    $("f-lag").textContent = r.lag == null ? "–" : secs(r.lag);
    renderRunHeader();
    renderProgress();
    renderElapsed();
    if (r.error) {
      $("error-box").hidden = false;
      $("error-msg").textContent = r.error.message || "Unknown error.";
      $("error-trace").textContent = r.error.traceback || "";
    }
  }

  function renderElapsed() {
    const r = state.run; if (!r) return;
    const end = r.endedAt || Date.now() / 1000;
    const s = Math.max(0, Math.round(end - r.startedAt));
    $("f-elapsed").textContent = s >= 60 ? `${Math.floor(s / 60)} min ${s % 60} s` : `${s} s`;
  }

  /** Tiny trend line for a KPI tile (single series → no legend; the tile label names it). */
  function sparkline(values) {
    const v = values.filter((x) => x != null);
    if (v.length < 2) return "";
    const W = 74, H = 28, lo = Math.min(...v), hi = Math.max(...v), span = hi - lo || 1;
    const pts = v.map((x, i) => [(i / (v.length - 1)) * W, H - 3 - ((x - lo) / span) * (H - 6)]);
    const d = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ");
    const last = pts[pts.length - 1];
    return `<svg class="spark" viewBox="0 0 ${W} ${H}" aria-hidden="true"><path class="area" d="${d} L${W} ${H} L0 ${H} Z"/>` +
      `<path d="${d}"/><circle cx="${last[0]}" cy="${last[1]}" r="2.6"/></svg>`;
  }

  function kpi(label, value, prev, lowerBetter, sub, series) {
    let delta = "";
    if (value != null && prev != null) {
      const d = value - prev;
      if (Math.abs(d) < 0.0005) delta = `<span class="delta">= no change</span>`;
      else {
        const good = lowerBetter ? d < 0 : d > 0;
        delta = `<span class="delta ${good ? "good" : "bad"}">${d > 0 ? "▲ +" : "▼ −"}${Math.abs(d).toFixed(3)} ${good ? "(better)" : "(worse)"}</span>`;
      }
    }
    return `<div class="kpi"><div class="label">${label}</div><div class="kv"><div class="value">${num(value, 2)}</div>${sparkline(series || [])}</div>${delta}` +
      `${sub ? `<div class="sub">${sub}</div>` : ""}</div>`;
  }

  function renderKpis() {
    const r = state.run, incs = r ? r.incs : [];
    const last = incs[incs.length - 1], prev = incs[incs.length - 2];
    const m = (x, k) => (x ? x.metrics[k] : null);
    const s = (k) => incs.map((i) => i.metrics[k]);
    $("kpis").innerHTML = last
      ? kpi("Precision@20", m(last, "p20"), m(prev, "p20"), false, "higher is better", s("p20")) +
        kpi("Bias@k", m(last, "bias"), m(prev, "bias"), true, "0 = balanced groups", s("bias")) +
        kpi("PPVP", m(last, "ppvp"), m(prev, "ppvp"), true, "0 = parity", s("ppvp")) +
        kpi("TPRP", m(last, "tprp"), m(prev, "tprp"), true, "0 = parity", s("tprp")) +
        kpi("Explanation Score", m(last, "es"), m(prev, "es"), false, last.metrics.es == null ? "TREATS does not explain" : "higher is better", s("es"))
      : "";
  }

  // ───────────── rendering: increments ─────────────
  function groupLabel(g) {
    const ds = state.cfg.datasets.find((d) => d.name === (state.run.params || {}).dataset);
    const l = ds && ds.groups.labels[g];
    return l ? `${esc(l)}` : `G${g}`;
  }

  function attrLabel(key) {
    const m = /^[ab]\.(left|right)_(.+)$/.exec(key);
    return m ? `${m[1]} · ${m[2]}` : key;
  }

  /** Short reading guide for the per-attribute explanation (definitions from the X-TREATS paper, §3.1–3.2). */
  function explainNote(attributes) {
    const noPotential = attributes.every((a) => a.potential == null);
    return `<div class="explain-note">
      <p><span class="term"><i class="sw pos"></i><i class="sw neg"></i>Weight</span><span>How much the attribute pushed the matcher’s decision
        towards <b>match</b> (blue, to the right) or <b>non-match</b> (red, to the left). Longer bar = stronger influence.</span></p>
      <p><span class="term">Potential</span><span>How much the match score would increase if this attribute agreed perfectly between the two
        entities. High potential with a low weight = useful evidence the model is not exploiting (e.g. “USA” vs “U.S.A.”).
        ${noPotential ? "<em>Not computed by SHAP (shown as –).</em>" : ""}</span></p>
      <p class="muted">Averaged over all pairs explained so far · <code>left</code>/<code>right</code> = attribute of the left/right entity.</p>
    </div>`;
  }

  function incrementHtml(ev, fresh) {
    const t = ev.timings, tot = Math.max(t.processing, 0.001);
    const seg = (v, c) => `<i style="width:${(v / tot) * 100}%;background:var(${c})"></i>`;
    const budget = ev.over_budget
      ? `<span class="pill warn" title="Processing took longer than τ: the next batches wait in the queue">⚠ over τ=${t.tau}s</span>`
      : `<span class="pill good">✓ within τ=${t.tau}s</span>`;
    const m = ev.metrics;
    const rows = ev.top.map((x) => `<tr>
      <td>${x.rank}</td><td title="${esc(x.left)}">${esc(x.left)}</td><td title="${esc(x.right)}">${esc(x.right)}</td>
      <td>${num(x.sim, 4)}</td><td>${groupLabel(x.group)}</td><td>${x.es == null ? "–" : num(x.es, 2)}</td>
      <td>${x.correct === true ? '<span class="ok">✓ match</span>' : x.correct === false ? '<span class="ko">✕ non-match</span>' : "–"}</td>
      <td>${x.new ? '<span class="tag new">new</span>' : '<span class="tag">kept</span>'}</td></tr>`).join("");

    const maxA = Math.max(0.0001, ...ev.attributes.map((a) => Math.abs(a.weight || 0)));
    const attrs = ev.attributes.length
      ? ev.attributes.map((a) => {
          const w = a.weight || 0, pct = (Math.abs(w) / maxA) * 50;
          const bar = w >= 0 ? `left:50%;width:${pct}%;background:var(--pos)` : `right:50%;width:${pct}%;background:var(--neg)`;
          return `<div class="attr"><span class="key" title="${esc(a.key)}">${esc(attrLabel(a.key))}</span>
            <span class="track"><span class="bar" style="${bar}"></span></span>
            <span class="nums">weight ${w >= 0 ? "+" : "−"}${Math.abs(w).toFixed(3)} · potential ${a.potential == null ? "–" : num(a.potential, 3)}</span></div>`;
        }).join("")
      : `<p class="muted">No explanation in this mode (TREATS).</p>`;

    return `<details class="inc${fresh ? " fresh" : ""}" ${fresh || state.run.incs.length <= 1 ? "open" : ""}>
      <summary><span class="title">Increment ${ev.index}</span>${budget}
        <span class="chips"><span><b>${ev.pairs}</b> pairs</span><span>processing <b>${secs(t.processing)}</b></span>
        <span>P@20 <b>${num(m.p20)}</b></span><span>Bias <b>${num(m.bias)}</b></span>
        <span>ES <b>${m.es == null ? "–" : num(m.es)}</b></span></span></summary>
      <div class="body">
        <div><div class="sec-title">Increment time</div>
          <div class="timebar" role="img" aria-label="matching ${num(t.match, 1)} s, ranking ${num(t.rank, 2)} s, explanation ${num(t.explain, 1)} s">
            ${seg(t.match, "--s1")}${seg(t.rank, "--s2")}${seg(t.explain, "--s3")}</div>
          <div class="timelegend"><span><i style="background:var(--s1)"></i>Matching ${secs(t.match)}</span>
            <span><i style="background:var(--s2)"></i>Ranking ${secs(t.rank)}</span>
            <span><i style="background:var(--s3)"></i>Explanation ${secs(t.explain)}</span>
            <span>Queue wait ${secs(t.lag)}</span><span>End-to-end latency ${secs(t.latency)}</span></div></div>
        <div><div class="sec-title">Global top-${ev.top.length} after this increment</div>
          <div class="table-wrap"><table class="topk"><thead><tr><th>#</th><th>Entity (left)</th><th>Entity (right)</th>
            <th>Similarity</th><th>Group</th><th>ES</th><th>Ground truth</th><th>Origin</th></tr></thead><tbody>${rows}</tbody></table></div></div>
        <div><div class="sec-title">Average explanation per attribute (cumulative)</div>${ev.attributes.length ? explainNote(ev.attributes) : ""}<div class="attrs">${attrs}</div></div>
      </div></details>`;
  }

  function addTableRow(ev) {
    const t = ev.timings, m = ev.metrics;
    const tr = `<tr><td>${ev.index}</td><td>${num(m.p5)}</td><td>${num(m.p10)}</td><td>${num(m.p15)}</td><td>${num(m.p20)}</td>
      <td>${num(m.bias)}</td><td>${num(m.ppvp)}</td><td>${num(m.tprp)}</td><td>${m.es == null ? "–" : num(m.es)}</td>
      <td>${num(t.match, 2)}</td><td>${num(t.rank, 3)}</td><td>${num(t.explain, 2)}</td><td>${num(t.processing, 2)}</td><td>${t.tau}</td></tr>`;
    $("metrics-table").querySelector("tbody").insertAdjacentHTML("beforeend", tr);
  }

  $("expand-all").addEventListener("click", () => document.querySelectorAll("#feed details").forEach((d) => { d.open = true; }));
  $("collapse-all").addEventListener("click", () => document.querySelectorAll("#feed details").forEach((d) => { d.open = false; }));

  // ───────────── charts (inline SVG) ─────────────
  const W = 420, H = 190, M = { l: 38, r: 52, t: 10, b: 24 };
  const tip = $("tooltip");

  function showTip(html, x, y) {
    tip.innerHTML = html; tip.hidden = false;
    const w = tip.offsetWidth, h = tip.offsetHeight;
    tip.style.left = Math.min(innerWidth - w - 8, x + 14) + "px";
    tip.style.top = Math.max(8, Math.min(innerHeight - h - 8, y + 14)) + "px";
  }
  const hideTip = () => { tip.hidden = true; };

  function niceMax(v) { const p = Math.pow(10, Math.floor(Math.log10(v || 1))); return Math.ceil(v / p * 2) / 2 * p || 1; }

  /** series: [{name, color:"--s1", values:[n|null...]}] ; mode "line" | "stack" */
  function chart(opts) {
    const { title, series, mode = "line", fmt = (v) => num(v, 2), yMin = 0, yMax, tau, expected } = opts;
    const n = Math.max(expected || 0, ...series.map((s) => s.values.length), 2);
    const have = Math.max(...series.map((s) => s.values.filter((v) => v != null).length));
    const iw = W - M.l - M.r, ih = H - M.t - M.b;
    const x = (i) => M.l + (mode === "stack" ? (i + 0.5) / n * iw : (n === 1 ? 0 : i / (n - 1) * iw));
    let top = yMax;
    if (top == null) {
      const maxv = mode === "stack"
        ? Math.max(0, ...series[0].values.map((_, i) => series.reduce((a, s) => a + (s.values[i] || 0), 0)))
        : Math.max(0, ...series.flatMap((s) => s.values.filter((v) => v != null)));
      top = niceMax(Math.max(maxv, tau || 0) * 1.1);
    }
    const y = (v) => M.t + ih - ((v - yMin) / (top - yMin || 1)) * ih;
    let g = "";
    for (let i = 0; i <= 4; i++) {
      const v = yMin + ((top - yMin) * i) / 4;
      g += `<line x1="${M.l}" x2="${W - M.r}" y1="${y(v)}" y2="${y(v)}"/>`;
    }
    let ax = "";
    for (let i = 0; i <= 4; i++) {
      const v = yMin + ((top - yMin) * i) / 4;
      ax += `<text x="${M.l - 6}" y="${y(v) + 4}" text-anchor="end">${fmt(v)}</text>`;
    }
    const step = Math.max(1, Math.ceil(n / 8));
    for (let i = 0; i < n; i += step) ax += `<text x="${x(i)}" y="${H - 6}" text-anchor="middle">${i + 1}</text>`;

    let marks = "";
    if (!have) marks = `<text class="nodata" x="${W / 2}" y="${H / 2}" text-anchor="middle">waiting for data…</text>`;
    else if (mode === "line") {
      const ends = [];
      series.forEach((s) => {
        const pts = s.values.map((v, i) => (v == null ? null : [x(i), y(v)]));
        const d = pts.filter(Boolean).map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ");
        marks += `<path class="line" d="${d}" style="stroke:var(${s.color})"/>`;
        const lastI = pts.map((p, i) => (p ? i : -1)).filter((i) => i >= 0).pop();
        if (lastI != null) {
          const p = pts[lastI];
          marks += `<circle class="dot" cx="${p[0]}" cy="${p[1]}" r="4" style="fill:var(${s.color})"/>`;
          ends.push({ x: p[0], y: p[1], ly: p[1], label: s.short || s.name });
        }
      });
      if (series.length > 1) {  // direct labels, nudged apart so they never collide
        ends.sort((a, b) => a.y - b.y);
        for (let i = 1; i < ends.length; i++) ends[i].ly = Math.max(ends[i].ly, ends[i - 1].ly + 13);
        ends.forEach((e) => { marks += `<text class="endlabel" x="${e.x + 8}" y="${e.ly + 4}">${esc(e.label)}</text>`; });
      }
    } else {
      const bw = Math.min(26, iw / n - 4);
      for (let i = 0; i < n; i++) {
        let acc = 0;
        series.forEach((s) => {
          const v = s.values[i]; if (!v) return;
          const y0 = y(acc), y1 = y(acc + v); acc += v;
          marks += `<rect x="${x(i) - bw / 2}" y="${y1}" width="${bw}" height="${Math.max(1, y0 - y1 - 2)}" rx="2" style="fill:var(${s.color})"/>`;
        });
      }
    }
    if (tau) marks += `<line class="tau" x1="${M.l}" x2="${W - M.r}" y1="${y(tau)}" y2="${y(tau)}"/>` +
      `<text class="tau-label" x="${W - M.r + 4}" y="${y(tau) + 4}">τ ${tau}s</text>`;

    const legend = series.length > 1 || mode === "stack"
      ? `<div class="legend">${series.map((s) => `<span><i style="background:var(${s.color})"></i>${esc(s.name)}</span>`).join("")}</div>` : "";
    const id = "c" + Math.random().toString(36).slice(2, 8);
    return {
      html: `<div class="chart" id="${id}"><h3>${esc(title)}</h3>${legend}
        <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(title)}">
          <g class="grid">${g}</g><line class="baseline" x1="${M.l}" x2="${W - M.r}" y1="${y(yMin)}" y2="${y(yMin)}"/>
          <g class="axis">${ax}</g>${marks}<line class="cross" y1="${M.t}" y2="${M.t + ih}" visibility="hidden"/>
          <rect class="hit" x="${M.l}" y="${M.t}" width="${iw}" height="${ih}" fill="transparent"/></svg></div>`,
      bind() {
        const host = document.getElementById(id); if (!host || !have) return;
        const svg = host.querySelector("svg"), hit = svg.querySelector(".hit"), cross = svg.querySelector(".cross");
        hit.addEventListener("pointermove", (e) => {
          const rect = svg.getBoundingClientRect();
          const px = ((e.clientX - rect.left) / rect.width) * W;
          let i = mode === "stack" ? Math.floor(((px - M.l) / iw) * n) : Math.round(((px - M.l) / iw) * (n - 1));
          i = Math.max(0, Math.min(n - 1, i));
          if (series.every((s) => s.values[i] == null)) { cross.setAttribute("visibility", "hidden"); hideTip(); return; }
          cross.setAttribute("x1", x(i)); cross.setAttribute("x2", x(i)); cross.setAttribute("visibility", "visible");
          const rows = series.map((s) => `<div><i style="background:var(${s.color})"></i>${esc(s.name)}: <b>${s.values[i] == null ? "–" : fmt(s.values[i])}</b></div>`).join("");
          showTip(`<div class="tt-h">Increment ${i + 1}</div>${rows}`, e.clientX, e.clientY);
        });
        hit.addEventListener("pointerleave", () => { cross.setAttribute("visibility", "hidden"); hideTip(); });
      },
    };
  }

  function renderCharts() {
    const r = state.run; if (!r) return;
    const incs = r.incs, col = (f) => incs.map(f);
    const hasEs = incs.some((i) => i.metrics.es != null);
    const pv = col((i) => i.metrics.p20).concat(col((i) => i.metrics.p5));
    const pMin = pv.length ? Math.max(0, Math.floor((Math.min(...pv) - 0.05) * 10) / 10) : 0;
    const tau = (r.params && r.params.tau) || (incs[0] && incs[0].timings.tau) || null;
    const defs = [
      chart({ title: "Precision@k", expected: r.expected, yMin: pMin, yMax: 1, series: [
        { name: "P@5", short: "@5", color: "--s1", values: col((i) => i.metrics.p5) },
        { name: "P@10", short: "@10", color: "--s2", values: col((i) => i.metrics.p10) },
        { name: "P@15", short: "@15", color: "--s3", values: col((i) => i.metrics.p15) },
        { name: "P@20", short: "@20", color: "--s4", values: col((i) => i.metrics.p20) }] }),
      chart({ title: "Fairness (0 = parity)", expected: r.expected, fmt: (v) => num(v, 2), series: [
        { name: "Bias@k", short: "Bias", color: "--s1", values: col((i) => i.metrics.bias) },
        { name: "PPVP", short: "PPVP", color: "--s2", values: col((i) => i.metrics.ppvp) },
        { name: "TPRP", short: "TPRP", color: "--s3", values: col((i) => i.metrics.tprp) }] }),
      chart({ title: "Explanation Score (mean ES of the top-k)", expected: r.expected, fmt: (v) => num(v, 2),
        series: [{ name: "ES", color: "--s1", values: hasEs ? col((i) => i.metrics.es) : [] }] }),
      chart({ title: "Time per increment vs. time budget", expected: r.expected, mode: "stack", tau, fmt: (v) => secs(v),
        series: [
          { name: "Matching", color: "--s1", values: col((i) => i.timings.match) },
          { name: "Ranking", color: "--s2", values: col((i) => i.timings.rank) },
          { name: "Explanation", color: "--s3", values: col((i) => i.timings.explain) }] }),
    ];
    $("charts").innerHTML = defs.map((d) => d.html).join("");
    defs.forEach((d) => d.bind());
  }

  // ───────────── log / history ─────────────
  function appendLog(lines) {
    const pre = $("log"), nearEnd = pre.scrollTop + pre.clientHeight >= pre.scrollHeight - 30;
    pre.textContent += lines.join("\n") + "\n";
    const all = pre.textContent.split("\n");
    if (all.length > 800) pre.textContent = all.slice(-600).join("\n");
    $("log-count").textContent = `(${all.length} lines)`;
    if (nearEnd) pre.scrollTop = pre.scrollHeight;
  }

  async function refreshHistory() {
    try {
      const runs = await (await fetch("/api/runs")).json();
      const ul = $("history-list");
      if (!runs.length) { ul.innerHTML = '<li class="muted">None yet.</li>'; return; }
      ul.innerHTML = runs.map((r) => {
        const p = r.params || {}, d = new Date((r.started_at || 0) * 1000);
        const stLabel = { done: "finished", error: "failed", stopped: "stopped" }[r.state] || "running";
        return `<li><button type="button" data-id="${esc(r.id)}" ${r.id === state.runId ? 'aria-current="true"' : ""}>
          <span class="h1"><i class="st-dot st-${esc(r.state)}" title="${stLabel}" aria-label="${stLabel}"></i>${esc(p.dataset || "?")} · ${esc(ALG_LABEL[p.algorithm] || "?")}${p.simulate ? " · simulation" : ""}</span>
          <span class="h2">${esc(d.toLocaleString("en-US"))} · ${r.increments || 0} incr. · ${p.pairs_per_increment || "?"} pairs · τ ${p.tau || "?"}s</span></button></li>`;
      }).join("");
      ul.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => attach(b.dataset.id)));
    } catch (e) { /* history is best-effort */ }
  }


  // ───────────── add dataset & model ─────────────
  const dlg = $("add-dialog");
  const up = { xhr: null, token: null, busy: false, attrs: [] };
  const ATTR_RE = /^[A-Za-z_][A-Za-z0-9_]*$/;
  const NAME_RE = /^[A-Za-z][A-Za-z0-9_-]{1,39}$/;
  const mb = (n) => (n < 1048576 ? Math.max(1, Math.round(n / 1024)) + " KB" : (n / 1048576).toFixed(n > 1.05e9 ? 0 : 1) + " MB");

  function parseKeywords(raw) {
    const out = [];
    raw.split(",").map((s) => s.trim().toLowerCase()).filter(Boolean).forEach((k) => { if (!out.includes(k)) out.push(k); });
    return out;
  }

  function renderChips() {
    const kws = parseKeywords($("up-groups").value);
    const chips = ['<span class="tag">0 · others</span>'].concat(kws.map((k, i) => `<span class="tag new">${i + 1} · ${esc(k)}</span>`));
    $("up-chips").innerHTML = chips.join("") +
      (kws.length > state.cfg.upload.max_groups ? `<span class="form-error">max ${state.cfg.upload.max_groups} groups</span>` : "");
  }

  function setInfo(ok, text) {
    const el = $("up-test-info");
    el.className = "info " + (ok ? "ok" : "bad");
    el.textContent = text;
  }

  async function previewTest(file) {
    up.attrs = [];
    const sel = $("up-sens");
    sel.innerHTML = '<option value="">Choose the dataset file first</option>'; sel.disabled = true;
    if (!file) { $("up-test-info").className = "info"; return; }
    const CHUNK = 262144;
    let lines = (await file.slice(0, CHUNK).text()).split(/\r?\n/);
    if (file.size > CHUNK) lines.pop();               // last line may be cut
    lines = lines.filter((l) => l.trim());
    if (!lines.length) return setInfo(false, "The file looks empty.");
    let attrs = null;
    for (let i = 0; i < lines.length; i++) {
      const f = lines[i].replace(/\s+$/, "").split("\t");
      const at = `line ${i + 1}: `;
      if (f.length !== 3) return setInfo(false, at + `expected 3 tab-separated fields (left ⇥ right ⇥ label), found ${f.length}.`);
      if (!["0", "1"].includes(f[2].trim())) return setInfo(false, at + "the label must be 0 or 1.");
      const sides = [];
      for (const side of [f[0], f[1]]) {
        const parts = side.split("COL").slice(1).map((c) => c.split("VAL"));
        if (!parts.length || parts.some((q) => q.length !== 2)) return setInfo(false, at + "entities must look like “COL name VAL value COL …” (the words COL/VAL cannot appear inside values).");
        sides.push(parts.map((q) => q[0].trim()));
      }
      if (sides[0].join("|") !== sides[1].join("|")) return setInfo(false, at + "left and right entities must have the same attributes in the same order.");
      if (!attrs) {
        attrs = sides[0];
        const bad = attrs.filter((a) => !ATTR_RE.test(a));
        if (bad.length) return setInfo(false, at + `invalid attribute name(s): ${bad.join(", ")} — use letters, digits and “_” only.`);
      } else if (attrs.join("|") !== sides[0].join("|")) return setInfo(false, at + "attributes differ from the first line.");
    }
    up.attrs = attrs;
    sel.innerHTML = attrs.map((a, i) => `<option value="${esc(a)}"${i === Math.min(1, attrs.length - 1) ? " selected" : ""}>${esc(a)}</option>`).join("");
    sel.disabled = false;
    setInfo(true, `✓ ${lines.length} sample lines checked · attributes: ${attrs.join(", ")} · ${mb(file.size)}. The first attribute (“${attrs[0]}”) identifies each record.`);
  }

  function resetAdd() {
    $("add-form").reset();
    up.attrs = []; up.token = null;
    $("up-lm").innerHTML = state.cfg.upload.lms.map((l) => `<option>${esc(l)}</option>`).join("");
    $("up-threshold").value = "0.5";
    $("up-test-info").className = "info";
    $("up-test-info").innerHTML = "The pairs that will be streamed in micro-batches (stored as <code>test.txt</code>).";
    $("up-sens").innerHTML = '<option value="">Choose the dataset file first</option>'; $("up-sens").disabled = true;
    $("up-error").hidden = true; $("up-progress").hidden = true; $("up-progress").innerHTML = "";
    $("up-submit").disabled = false; renderChips();
  }

  function showUpError(msg) { const e = $("up-error"); e.textContent = msg; e.hidden = false; }

  async function postJson(url, body) {
    const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.error || `Request failed (HTTP ${r.status})`);
    return data;
  }

  function putFile(token, kind, file, onProgress) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest(); up.xhr = xhr;
      xhr.open("PUT", `/api/datasets/uploads/${token}/${kind}`);
      xhr.setRequestHeader("Content-Type", "application/octet-stream");
      xhr.upload.onprogress = (e) => { if (e.lengthComputable) onProgress(e.loaded, e.total); };
      xhr.onload = () => {
        let b = {}; try { b = JSON.parse(xhr.responseText); } catch (_) { /* not JSON */ }
        xhr.status >= 200 && xhr.status < 300 ? resolve(b) : reject(new Error(b.error || `Upload failed (HTTP ${xhr.status})`));
      };
      xhr.onerror = () => reject(new Error("Network error during the upload."));
      xhr.onabort = () => reject(new Error("Upload cancelled."));
      xhr.send(file);
    });
  }

  function closeAdd() {
    if (up.busy) {
      if (!confirm("An upload is in progress. Cancel it?")) return;
      if (up.xhr) up.xhr.abort();
    }
    dlg.close();
  }

  $("add-dataset-btn").addEventListener("click", () => { resetAdd(); dlg.showModal(); });
  $("add-close").addEventListener("click", closeAdd);
  $("up-cancel").addEventListener("click", closeAdd);
  dlg.addEventListener("cancel", (e) => { e.preventDefault(); closeAdd(); });
  $("up-test").addEventListener("change", (e) => previewTest(e.target.files[0]));
  $("up-groups").addEventListener("input", renderChips);

  $("add-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    if (up.busy) return;
    $("up-error").hidden = true;
    const files = { test: $("up-test").files[0], train: $("up-train").files[0], valid: $("up-valid").files[0], model: $("up-model").files[0] };
    const name = $("up-name").value.trim(), kws = parseKeywords($("up-groups").value), thr = parseFloat($("up-threshold").value);
    if (!NAME_RE.test(name)) return showUpError("Name must start with a letter and use only letters, digits, “-” or “_” (2–40 characters).");
    if (!files.test) return showUpError("Choose the dataset file.");
    if (!up.attrs.length) return showUpError("The dataset file has format problems — see the message under it.");
    if (!files.model) return showUpError("Choose the trained model (.pt).");
    if (!$("up-sens").value) return showUpError("Choose the sensitive attribute.");
    if (!kws.length) return showUpError("Type at least one group keyword (e.g. “microsoft, sony”).");
    if (kws.length > state.cfg.upload.max_groups) return showUpError(`At most ${state.cfg.upload.max_groups} groups.`);
    if (!(thr >= 0.01 && thr <= 0.99)) return showUpError("Threshold must be between 0.01 and 0.99.");
    for (const [kind, f] of Object.entries(files)) {
      if (f && f.size > state.cfg.upload.max_bytes[kind]) return showUpError(`${f.name} is too large (limit ${mb(state.cfg.upload.max_bytes[kind])}).`);
    }

    up.busy = true; $("up-submit").disabled = true;
    const box = $("up-progress"); box.hidden = false;
    const labels = { test: "Dataset", train: "Train", valid: "Validation", model: "Model" };
    const order = ["test", "train", "valid", "model"].filter((k) => files[k]);
    box.innerHTML = order.map((k) => `<div class="up-row" id="row-${k}"><span>${labels[k]} · ${esc(files[k].name)}</span><span class="bar"><i></i></span><span class="st">waiting</span></div>`).join("");
    const row = (k) => ({ el: $("row-" + k), bar: $("row-" + k).querySelector("i"), st: $("row-" + k).querySelector(".st") });
    let current = null;
    try {
      up.token = (await postJson("/api/datasets/uploads", {})).token;
      for (const kind of order) {
        current = kind; const r = row(kind);
        r.st.textContent = "0%";
        const res = await putFile(up.token, kind, files[kind], (l, t) => {
          r.bar.style.width = (l / t * 100).toFixed(1) + "%";
          r.st.textContent = l >= t ? "checking…" : Math.round(l / t * 100) + "%";
        });
        r.el.classList.add("done"); r.bar.style.width = "100%";
        r.st.textContent = res.lines ? `✓ ${res.lines.toLocaleString("en-US")} pairs` : "✓ done";
      }
      current = null;
      const meta = await postJson(`/api/datasets/uploads/${up.token}/commit`, {
        name, lm: $("up-lm").value, threshold: thr, sensitive_attribute: $("up-sens").value, groups: kws,
      });
      up.token = null; up.busy = false;
      dlg.close();
      await reloadDatasets(meta.name);
    } catch (err) {
      if (current) row(current).el.classList.add("fail");
      showUpError(err.message);
      if (up.token) fetch(`/api/datasets/uploads/${up.token}`, { method: "DELETE" }).catch(() => {});
      up.token = null; up.busy = false; $("up-submit").disabled = false;
    }
  });

  if (location.hash === "#add-dataset") setTimeout(() => $("add-dataset-btn").click(), 300);

  loadConfig().then(() => {
    const m = /^#run=([\w-]+)$/.exec(location.hash);
    if (m && !state.runId) attach(m[1]);
  }).then(refreshHistory).catch((e) => {
    $("empty-state").insertAdjacentHTML("beforeend", `<p class="form-error">Could not load the configuration: ${esc(e)}</p>`);
  });
})();
