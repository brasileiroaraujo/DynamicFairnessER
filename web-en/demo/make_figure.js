// Paper figure: one high-resolution screenshot of a finished run (whole console at a glance).
//
//   node make_figure.js [runId]      (server running; default http://127.0.0.1:5051)
//
// Writes figures/x-treats-figure.png (clean, 2x) and figures/regions.json (boxes for annotate.py).
// Figure-only layout tweaks (applied to this screenshot, not to the app): the process console and
// footer are hidden, only the latest increment is expanded and its top-k table shows the first rows.
const { spawn } = require("child_process");
const fs = require("fs"), os = require("os"), path = require("path");

const BASE = process.env.XT_URL || "http://127.0.0.1:5051";
const RUN = process.argv[2] || "20261012-195322-9da5";  // DBLP-GoogleScholar · X-TREATS+LEMON · 6 increments, all within tau
const TOPK_ROWS = Number(process.env.TOPK_ROWS || 6);
const VARIANT = process.env.FIG_VARIANT || "full";  // full: + latest increment (top-k, explanation) · compact: without it
const NAME = VARIANT === "full" ? "x-treats-figure" : "x-treats-figure-" + VARIANT;
const WIDTH = 1440, SCALE = 2.5;  // 1440 = narrowest width with the 5 KPI cards on one row
const OUT = path.join(__dirname, "figures", process.env.FIG_DIR || "");  // FIG_DIR: optional subfolder, e.g. Amazon-Google
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), "xt-fig-"));
  const chrome = spawn(process.env.CHROME || "C:/Program Files/Google/Chrome/Application/chrome.exe",
    ["--headless=new", "--disable-gpu", "--hide-scrollbars", "--remote-debugging-port=9350", "--user-data-dir=" + profile,
     "--force-color-profile=srgb", "about:blank"], { stdio: "ignore" });
  try {
    await sleep(3000);
    const page = (await (await fetch("http://127.0.0.1:9350/json")).json()).find((t) => t.type === "page");
    const ws = new WebSocket(page.webSocketDebuggerUrl); await new Promise((r) => (ws.onopen = r));
    let id = 0; const pend = new Map(); const errs = [];
    ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && pend.has(d.id)) { pend.get(d.id)(d); pend.delete(d.id); }
      if (d.method === "Runtime.exceptionThrown") errs.push(d.params.exceptionDetails.exception?.description); };
    const send = (method, params = {}) => new Promise((res) => { const i = ++id; pend.set(i, res); ws.send(JSON.stringify({ id: i, method, params })); });
    const js = async (e) => { const r = await send("Runtime.evaluate", { expression: e, awaitPromise: true, returnByValue: true });
      if (r.result.exceptionDetails) throw new Error(e.slice(0, 80) + " → " + r.result.exceptionDetails.exception?.description); return r.result.result.value; };
    const until = async (e, ms = 20000) => { const s = Date.now(); while (Date.now() - s < ms) { if (await js(e)) return; await sleep(250); } throw new Error("timeout: " + e); };

    await send("Runtime.enable"); await send("Page.enable");
    await send("Emulation.setDeviceMetricsOverride", { width: WIDTH, height: 1000, deviceScaleFactor: SCALE, mobile: false });
    await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: "light" }, { name: "prefers-reduced-motion", value: "reduce" }] });
    await send("Page.navigate", { url: BASE + "/#run=" + RUN });
    await until("document.getElementById('state-pill') && /Finished/.test(document.getElementById('state-pill').textContent) && document.querySelectorAll('#feed details.inc').length > 0");
    const params = await js(`fetch('/api/runs/${RUN}').then(r => r.json()).then(s => s.params)`);

    // Form mirrors the run being shown; Advanced expanded so every option is visible.
    await js(`(() => {
      const p = ${JSON.stringify(params)};
      const ds = document.querySelector('input[name=dataset][value="' + p.dataset + '"]'); if (ds) ds.checked = true;
      const t = document.getElementById('explain-toggle'); if (t.checked !== (p.algorithm > 0)) t.click();
      if (p.algorithm > 0) { const m = document.querySelector('input[name=method][value="' + p.algorithm + '"]'); if (m) { m.checked = true; m.dispatchEvent(new Event('change', { bubbles: true })); } }
      document.getElementById('pairs').value = p.pairs_per_increment; document.getElementById('pairs').dispatchEvent(new Event('input'));
      const tau = document.getElementById('tau'); tau.value = p.tau; tau.dispatchEvent(new Event('input'));
      document.getElementById('k').value = p.k; document.getElementById('max-increments').value = p.max_increments;
      document.querySelector('.advanced').open = true;
    })()`);

    // Figure-only layout: whole console in one viewport (no sticky/scroll), latest increment open.
    await js(`(() => {
      const css = document.createElement('style');
      css.textContent = \`
        /* Results become grid items of .layout: config | run header + KPIs + charts, then the increment full width */
        .topbar, .sidebar { position: static !important; }
        .sidebar { max-height: none !important; overflow: visible !important; grid-column: 1; grid-row: 1 / span 3; }
        .results, #run-view { display: contents !important; }
        .layout { row-gap: 18px; padding-bottom: 22px; grid-template-rows: auto auto 1fr auto; }
        .card-wrap:has(.tag.custom) { display: none !important; }
        ${VARIANT === 'compact' ? '.panel:has(#feed) { display: none !important; }' : ''}
        .layout > *, #run-view > * { margin: 0 !important; }
        #status-strip { grid-column: 2; grid-row: 1; }
        #kpis { grid-column: 2; grid-row: 2; }
        .panel:has(#charts) { grid-column: 2; grid-row: 3; }
        .panel:has(#feed) { grid-column: 1 / -1; grid-row: 4; }
        .site-footer, .console, .table-view, .history, #empty-state, #error-box, .panel-tools { display: none !important; }
        #feed details.inc:not(:first-child) { display: none !important; }
        #feed details.inc:first-child .body { grid-template-columns: minmax(0, 2fr) minmax(0, 1fr); column-gap: 30px; padding-left: 40px; }
        #feed details.inc:first-child .body > :first-child { grid-column: 1 / -1; }
        #feed details.inc:first-child .topk tbody tr:nth-child(n+${TOPK_ROWS + 1}) { display: none !important; }
        #feed details.inc:first-child .topk td:nth-child(2), #feed details.inc:first-child .topk td:nth-child(3) { max-width: 185px; }
        #feed details.inc:first-child .body > * { min-width: 0; }
        #feed details.inc:first-child .topk { width: 100%; }
        .explain-note { display: none !important; }
        .attr { grid-template-columns: 150px minmax(0, 1fr) 190px !important; }
        .card-wrap .del { display: none !important; }
      \`;
      document.head.appendChild(css);
      document.querySelectorAll('#feed details.inc').forEach((d, i) => { d.open = i === 0; d.classList.remove('fresh'); });
      document.getElementById('tooltip').hidden = true;
    })()`);
    await sleep(800);

    // Fit the viewport to the content, then re-measure after relayout.
    let h = await js("Math.ceil(document.querySelector('.layout').getBoundingClientRect().bottom + 6)");
    await send("Emulation.setDeviceMetricsOverride", { width: WIDTH, height: h, deviceScaleFactor: SCALE, mobile: false });
    await sleep(900);
    h = await js("Math.ceil(document.querySelector('.layout').getBoundingClientRect().bottom + 6)");
    h += h % 2;  // even height → whole pixels at 2.5×
    await send("Emulation.setDeviceMetricsOverride", { width: WIDTH, height: h, deviceScaleFactor: SCALE, mobile: false });
    await sleep(900);

    const regions = await js(`(() => {
      const box = (sel) => { const el = document.querySelector(sel); if (!el) return null; const r = el.getBoundingClientRect(); return { x: r.left, y: r.top, w: r.width, h: r.height }; };
      const feedPanel = document.getElementById('feed').closest('.panel').getBoundingClientRect();
      const body = document.querySelector('#feed details.inc:first-child .body').children;
      const tk = body[1].getBoundingClientRect(), at = body[2].getBoundingClientRect();
      const showFeed = feedPanel.height > 0;
      const pad = (r, p) => ({ x: r.left - p, y: r.top - p, w: r.width + 2 * p, h: r.height + 2 * p });
      return {
        scale: ${SCALE},
        A: box('.config'), B: box('#status-strip'), C: box('#kpis'), D: box('.panel:has(#charts)'),
        E: showFeed ? { x: feedPanel.left, y: feedPanel.top, w: feedPanel.width, h: feedPanel.height } : null,
        F: showFeed ? pad(at, 14) : null,
      };
    })()`);
    fs.writeFileSync(path.join(OUT, NAME + ".regions.json"), JSON.stringify({ run: RUN, params, ...regions }, null, 1));

    const shot = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
    const file = path.join(OUT, NAME + ".png");
    fs.writeFileSync(file, Buffer.from(shot.result.data, "base64"));
    console.log("figure:", file, `(${WIDTH * SCALE}×${h * SCALE}px)`, "· run:", RUN, "· JS errors:", errs.length ? errs : "none");
    ws.close();
  } finally {
    chrome.kill();
    try { fs.rmSync(profile, { recursive: true, force: true }); } catch (e) { /* ignore */ }
  }
})().catch((e) => { console.error("ERROR", e); process.exit(2); });
