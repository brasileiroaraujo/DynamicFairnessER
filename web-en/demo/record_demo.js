// Step 2 — drive the real UI in headless Chrome and record it (Node 22+, built-in WebSocket).
//
//   node record_demo.js            (server must be running; default http://127.0.0.1:5052)
//
// Reads build/narration.json (scene durations + caption timings), performs each scene's
// actions while the narration time elapses, captures frames with the DevTools screencast,
// and writes build/frames/*.jpg + build/timeline.json for assemble.py.
// A REAL run is started (Amazon-Google, X-TREATS+LEMON, 3 increments); waits are recorded
// as fast-forward segments that assemble.py speeds up.
const { spawn } = require("child_process");
const fs = require("fs"), os = require("os"), path = require("path");

const BASE = process.env.XT_URL || "http://127.0.0.1:5052";
const CHROME = process.env.CHROME || "C:/Program Files/Google/Chrome/Application/chrome.exe";
const VERSION = process.env.DEMO_VERSION || "v1";  // v1 → build/ ; vN → build/vN/
const BUILD = VERSION === "v1" ? path.join(__dirname, "build") : path.join(__dirname, "build", VERSION);
const FRAMES = path.join(BUILD, "frames");
const FPS = 15;
const VIEW = { width: 1600, height: 900, scale: 1.2 };  // → 1920×1080 frames
const narration = JSON.parse(fs.readFileSync(path.join(BUILD, "narration.json"), "utf8"));
const SC = Object.fromEntries(narration.scenes.map((s) => [s.id, s]));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const t0 = Date.now(); const now = () => (Date.now() - t0) / 1000;
const timeline = { scenes: [], ff: [], fps: FPS, frames: [] };

// Overlay injected into the page: captions, fast-forward badge, animated cursor, title card.
const OVERLAY = String.raw`(() => {
  if (window.__demo) return;
  const css = document.createElement('style');
  css.textContent = ` + "`" + String.raw`
    #demo-cap { position: fixed; left: 50%; bottom: 34px; transform: translateX(-50%); z-index: 99999; max-width: 1080px;
      padding: 12px 22px; border-radius: 14px; background: rgba(8, 12, 26, .86); color: #f1f5ff; font: 500 21px/1.42 "Segoe UI Variable Text","Segoe UI",sans-serif;
      text-align: center; box-shadow: 0 10px 30px rgba(0,0,0,.35); opacity: 0; transition: opacity .25s; pointer-events: none; backdrop-filter: blur(4px); }
    #demo-cap.on { opacity: 1; }
    #demo-ff { position: fixed; top: 92px; left: 50%; transform: translateX(-50%); z-index: 99999; padding: 8px 16px; border-radius: 999px;
      background: #4f46e5; color: #fff; font: 600 15px "Segoe UI",sans-serif; box-shadow: 0 8px 24px rgba(79,70,229,.45); opacity: 0; transition: opacity .25s; pointer-events: none; }
    #demo-ff.on { opacity: 1; }
    #demo-cur { position: fixed; left: 0; top: 0; width: 22px; height: 22px; margin: -11px 0 0 -11px; border-radius: 50%; z-index: 100000; pointer-events: none;
      background: rgba(79,70,229,.25); border: 2px solid #4f46e5; box-shadow: 0 0 0 4px rgba(255,255,255,.7); transition: left .7s cubic-bezier(.4,0,.2,1), top .7s cubic-bezier(.4,0,.2,1), transform .15s; opacity: 0; }
    #demo-cur.on { opacity: 1; } #demo-cur.press { transform: scale(.7); }
    #demo-card { position: fixed; inset: 0; z-index: 100001; display: grid; place-items: center; pointer-events: none; opacity: 0; transition: opacity .6s;
      background: radial-gradient(900px 400px at 30% 20%, rgba(129,140,248,.35), transparent 70%), linear-gradient(160deg, #131c36, #060a14); color: #e7ebf5; text-align: center; font-family: "Segoe UI Variable Display","Segoe UI",sans-serif; }
    #demo-card.on { opacity: 1; }
    #demo-card h1 { font-size: 64px; letter-spacing: .08em; margin: 0 0 10px; } #demo-card h1 span { color: #a5b4fc; }
    #demo-card p { font-size: 22px; color: #9aa6c2; margin: 0; } #demo-card small { display: block; margin-top: 26px; font-size: 16px; color: #7c89a8; letter-spacing: .12em; text-transform: uppercase; }
  ` + "`" + String.raw`;
  document.head.appendChild(css);
  const mk = (id) => { const d = document.createElement('div'); d.id = id; document.body.appendChild(d); return d; };
  const cap = mk('demo-cap'), ff = mk('demo-ff'), cur = mk('demo-cur'), card = mk('demo-card');
  window.__demo = {
    caption(t) { if (t) { cap.textContent = t; cap.classList.add('on'); } else cap.classList.remove('on'); },
    ff(t) { if (t) { ff.textContent = t; ff.classList.add('on'); } else ff.classList.remove('on'); },
    card(html) { if (html) { card.innerHTML = html; card.classList.add('on'); } else card.classList.remove('on'); },
    point(sel, dx = 0, dy = 0) {
      const el = document.querySelector(sel); if (!el) return false;
      const r = el.getBoundingClientRect(); cur.classList.add('on');
      cur.style.left = (r.left + r.width / 2 + dx) + 'px'; cur.style.top = (r.top + r.height / 2 + dy) + 'px'; return true;
    },
    press() { cur.classList.add('press'); setTimeout(() => cur.classList.remove('press'), 180); },
    hideCursor() { cur.classList.remove('on'); },
    reveal(sel) { const el = document.querySelector(sel); if (!el) return false; el.scrollIntoView({ behavior: 'smooth', block: 'center' }); return true; },
    scrollTo(sel, block = 'start', offset = -90) {
      const el = document.querySelector(sel); if (!el) return false;
      const y = el.getBoundingClientRect().top + window.scrollY + offset;
      window.scrollTo({ top: block === 'top' ? 0 : y, behavior: 'smooth' }); return true;
    },
  };
})()`;

let chromeProc = null;
(async () => {
  fs.rmSync(FRAMES, { recursive: true, force: true }); fs.mkdirSync(FRAMES, { recursive: true });
  const cfg = await (await fetch(BASE + "/api/config")).json();
  if (cfg.active_run) throw new Error("Another run is active (" + cfg.active_run + "); wait for it to finish.");

  const profile = fs.mkdtempSync(path.join(os.tmpdir(), "xt-demo-"));
  const chrome = chromeProc = spawn(CHROME, ["--headless=new", "--disable-gpu", "--hide-scrollbars", "--remote-debugging-port=9340",
    "--user-data-dir=" + profile, "--force-color-profile=srgb", "about:blank"], { stdio: "ignore" });
  await sleep(3000);
  const page = (await (await fetch("http://127.0.0.1:9340/json")).json()).find((t) => t.type === "page");
  const ws = new WebSocket(page.webSocketDebuggerUrl); await new Promise((r) => (ws.onopen = r));
  let id = 0; const pend = new Map(); let latest = null, lastWritten = null; const jsErrors = [];
  const send = (method, params = {}) => new Promise((res) => { const i = ++id; pend.set(i, res); ws.send(JSON.stringify({ id: i, method, params })); });
  ws.onmessage = (m) => {
    const d = JSON.parse(m.data);
    if (d.id && pend.has(d.id)) { pend.get(d.id)(d); pend.delete(d.id); return; }
    if (d.method === "Page.screencastFrame") { latest = { data: d.params.data, t: now() }; send("Page.screencastFrameAck", { sessionId: d.params.sessionId }); }
    if (d.method === "Runtime.exceptionThrown") jsErrors.push(d.params.exceptionDetails.exception?.description);
  };
  const js = async (expr) => { const r = await send("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true });
    if (r.result.exceptionDetails) throw new Error(expr + " → " + JSON.stringify(r.result.exceptionDetails.exception?.description)); return r.result.result.value; };
  const until = async (expr, ms = 240000) => { const s = Date.now(); while (Date.now() - s < ms) { if (await js(expr)) return; await sleep(300); } throw new Error("timeout: " + expr); };
  const D = (call) => js("window.__demo." + call);

  await send("Runtime.enable"); await send("Page.enable");
  await send("Emulation.setDeviceMetricsOverride", { width: VIEW.width, height: VIEW.height, deviceScaleFactor: VIEW.scale, mobile: false });
  await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: "light" }, { name: "prefers-reduced-motion", value: "no-preference" }] });
  await send("Page.navigate", { url: BASE + "/" });
  await until("document.querySelectorAll('input[name=dataset]').length >= 4", 20000);
  await js("localStorage.removeItem('xtreats-theme'); document.documentElement.removeAttribute('data-theme')");
  await js(OVERLAY);
  await sleep(500);

  // frame writer: fixed-rate sampling of the latest screencast frame
  await send("Page.startScreencast", { format: "jpeg", quality: 82, maxWidth: 1920, maxHeight: 1080, everyNthFrame: 1 });
  let n = 0;
  const writer = setInterval(() => {
    if (!latest || latest === lastWritten) return;
    const file = String(n++).padStart(6, "0") + ".jpg";
    fs.writeFileSync(path.join(FRAMES, file), Buffer.from(latest.data, "base64"));
    timeline.frames.push({ file, t: latest.t }); lastWritten = latest;
  }, 1000 / FPS);

  function splitCaption(c) {  // long sentences → readable chunks, timed proportionally
    if (c.text.length <= 105) return [c];
    const parts = c.text.split(/(?<=[,:;])\s+/); const chunks = []; let buf = "";
    for (const p of parts) { if (buf && (buf + " " + p).length > 95) { chunks.push(buf); buf = p; } else buf = buf ? buf + " " + p : p; }
    if (buf) chunks.push(buf);
    const total = chunks.reduce((a, s) => a + s.length, 0); let t = c.start;
    return chunks.map((s) => { const d = (c.end - c.start) * s.length / total; const o = { start: t, end: t + d, text: s }; t += d; return o; });
  }

  const GAP = VERSION === "v1" ? 450 : 300;
  let sceneT0 = 0, sceneCaps = [];
  // wait until the k-th narration sentence of the current scene starts (+ dt seconds)
  const atCap = async (k, dt = 0) => { const t = sceneT0 + ((sceneCaps[k] || {}).start || 0) * 1000 + dt * 1000; const w = t - Date.now(); if (w > 0) await sleep(w); };
  async function scene(sid, actions) {
    const s = SC[sid]; const start = now(); sceneT0 = Date.now(); sceneCaps = s.captions;
    timeline.scenes.push({ id: sid, start, duration: s.duration });
    const caps = s.captions.flatMap(splitCaption);
    const timers = caps.map((c) => setTimeout(() => D("caption(" + JSON.stringify(c.text) + ")").catch(() => {}), c.start * 1000));
    await Promise.all([actions ? actions() : null, sleep(s.duration * 1000)]);
    timers.forEach(clearTimeout);
    await D("caption('')"); await sleep(GAP);
    console.log("scene %s done at %ss", sid, now().toFixed(1));
  }

  async function fastForward(label, condition, speed) {
    const start = now(); await D("ff(" + JSON.stringify("⏩  " + label + "  ·  " + speed + "× speed") + ")");
    await until(condition); await sleep(600);
    await D("ff('')"); await sleep(400);
    timeline.ff.push({ start, end: now(), speed });
    console.log("fast-forward %s: %ss real", label, (now() - start).toFixed(1));
  }

  const click = async (sel, wait = 900) => { await D(`point(${JSON.stringify(sel)})`); await sleep(wait); await D("press()"); await js(`document.querySelector(${JSON.stringify(sel)}).click()`); await sleep(350); };
  const point = async (sel, wait = 1200) => { await D(`point(${JSON.stringify(sel)})`); await sleep(wait); };

  if (VERSION === "v1") {
  // ───────────── the tour ─────────────
  await D(`card('<div><h1>X<span>-</span>TREATS</h1><p>Explainable &amp; Fairness-Aware Entity Resolution Over Streaming Data</p><small>Guided tour</small></div>')`);
  await sleep(3200); await D("card('')"); await sleep(700);

  await scene("intro", async () => { await sleep(4000); await point("#hero-title"); await sleep(4000); await point(".pipeline"); });
  await scene("pipeline", async () => {
    const order = [1, 2, 3, 4, 5]; await sleep(1500);
    for (const i of order) { await point(`.pipeline li:nth-child(${i})`, 300); await sleep(i === 3 || i === 4 ? 4200 : 2600); }
  });
  await scene("footer", async () => { await D("hideCursor()"); await D("scrollTo('.site-footer', 'start', -260)"); await sleep(2600); await point(".logo-row"); await sleep(4500); await point(".cites"); });
  await scene("dataset", async () => {
    await D("scrollTo('body', 'top')"); await sleep(1500);
    await click("input[name=dataset][value='Amazon-Google'] + .face"); await sleep(3500);
    await point("#add-dataset-btn");
  });
  await scene("explain", async () => {
    await js("{ const t=document.getElementById('explain-toggle'); if(!t.checked){t.click()} }");
    await point(".switch .slider"); await sleep(2500);
    await click("input[name=method][value='1'] + span");
  });
  await scene("stream", async () => {
    await click("input[name=pairs-preset][value='200'] + span"); await sleep(1500);
    await point("#tau"); await js("{ const t=document.getElementById('tau'); t.value=15; t.dispatchEvent(new Event('input')) }"); await sleep(2500);
    await click(".advanced summary"); await sleep(800);
    await point("#max-increments"); await js("document.getElementById('max-increments').value=3");
    await js("document.getElementById('simulate').checked=false");
  });
  await scene("start", async () => { await click("#start-btn", 1100); });

  await fastForward("Loading the model and processing the first increment", "document.querySelectorAll('#feed details.inc').length >= 1", 6);
  await scene("first", async () => {
    await D("scrollTo('body', 'top')"); await point("#progress", 2500); await sleep(3500); await point("#kpis", 1500);
  });
  await scene("topk", async () => {
    await D("hideCursor()"); await D("scrollTo('#feed .topk', 'start', -150)"); await sleep(3500); await point("#feed .topk tbody tr:first-child td:nth-child(7)");
  });
  await scene("attrs", async () => { await D("hideCursor()"); await D("scrollTo('#feed .explain-note', 'start', -120)"); await sleep(3000); await point("#feed .attrs"); });

  await fastForward("Processing the remaining increments", "document.getElementById('state-pill').textContent.includes('Finished')", 6);
  await scene("charts", async () => { await D("hideCursor()"); await D("scrollTo('#charts', 'start', -150)"); await sleep(4000); await point("#charts .chart:nth-child(4)"); });
  await scene("upload", async () => {
    await D("scrollTo('body', 'top')"); await sleep(1200);
    await click("#add-dataset-btn"); await sleep(4000);
    await D("hideCursor()");
  });
  await js("document.getElementById('add-dialog').close()"); await sleep(600);
  await scene("outro", async () => { await sleep(4200); await D(`card('<div><h1>X<span>-</span>TREATS</h1><p>Accurate · Fair · Explainable — one micro-batch at a time</p><small>DATALAB · IFPB · Tampere University</small></div>')`); });
  await sleep(1800);


  } else {
  // ───────────── tour v2 (no institutions scene; Advanced, time breakdown, table, history) ─────────────
  const FF = 10;
  await D(`card('<div><h1>X<span>-</span>TREATS</h1><p>Explainable &amp; Fairness-Aware Entity Resolution Over Streaming Data</p><small>Guided tour</small></div>')`);
  await sleep(2800); await D("card('')"); await sleep(500);

  await scene("intro", async () => { await atCap(0, 3.5); await point("#hero-title"); await atCap(1); await point(".pipeline"); });
  await scene("pipeline", async () => {
    await atCap(0, 1.2); await point(".pipeline li:nth-child(1)", 300);
    await atCap(1); await point(".pipeline li:nth-child(2)", 300);
    await atCap(2); await point(".pipeline li:nth-child(3)", 300);
    await atCap(3); await point(".pipeline li:nth-child(4)", 300);
    await atCap(3, 4.2); await point(".pipeline li:nth-child(5)", 300);
  });
  await scene("dataset", async () => {
    await D("hideCursor()"); await atCap(1, 0.3);
    await click("input[name=dataset][value='Amazon-Google'] + .face");
    await atCap(4); await point("#add-dataset-btn");
  });
  await scene("explain", async () => {
    await js("{ const t=document.getElementById('explain-toggle'); if(!t.checked){t.click()} }");
    await D("reveal('.switch')"); await point(".switch .slider", 600);
    await atCap(1); await click("input[name=method][value='1'] + span");
    await atCap(2); await point("#algorithm-hint", 300);
  });
  await scene("stream", async () => {
    await D("reveal('#pairs-presets')"); await atCap(0, 1.6); await click("input[name=pairs-preset][value='200'] + span", 600);
    await atCap(0, 4.6); await point("#tau", 500); await js("{ const t=document.getElementById('tau'); t.value=15; t.dispatchEvent(new Event('input')) }");
    await atCap(1); await D("reveal('#run-form fieldset:nth-of-type(3) .hint')"); await point("#run-form fieldset:nth-of-type(3) .hint", 300);
  });
  await scene("advanced", async () => {
    await D("reveal('.advanced')"); await atCap(0, 0.6); await click(".advanced summary", 700);
    await D("reveal('#start-btn')");
    await atCap(1); await point("#k", 300);
    await atCap(2); await point("#max-increments", 300);
    await atCap(3); await point("#simulate", 300); await js("document.getElementById('simulate').checked=false");
    await atCap(4, 0.6); await point("#max-increments", 600);
    await js("{ const m=document.getElementById('max-increments'); m.focus(); m.value=3; }"); await sleep(600); await js("document.activeElement.blur()");
  });
  await scene("start", async () => { await D("reveal('#start-btn')"); await click("#start-btn", 1100); });

  await fastForward("Loading the model and processing the first increment", "document.querySelectorAll('#feed details.inc').length >= 1", FF);
  await scene("first", async () => {
    await D("scrollTo('body', 'top')"); await atCap(1); await point("#progress", 300);
    await atCap(2); await point("#kpis", 300);
  });
  await scene("timebar", async () => {
    await D("hideCursor()"); await D("scrollTo('#feed .timebar', 'start', -220)"); await sleep(1500);
    await point("#feed .timebar", 300); await atCap(0, 5.5); await point("#feed .timelegend", 300);
  });
  await scene("topk", async () => {
    await D("hideCursor()"); await D("scrollTo('#feed .topk', 'start', -150)"); await sleep(3500); await point("#feed .topk tbody tr:first-child td:nth-child(5)"); await sleep(2600); await point("#feed .topk tbody tr:first-child td:nth-child(7)");
  });
  await scene("attrs", async () => { await D("hideCursor()"); await D("scrollTo('#feed .explain-note', 'start', -120)"); await atCap(1); await point("#feed .attrs"); });

  await fastForward("Processing the remaining increments", "document.getElementById('state-pill').textContent.includes('Finished')", FF);
  await scene("charts", async () => { await D("hideCursor()"); await D("scrollTo('#charts', 'start', -150)"); await sleep(4000); await point("#charts .chart:nth-child(2)"); await sleep(2200); await point("#charts .chart:nth-child(4)"); });
  await scene("table", async () => {
    await D("scrollTo('.table-view', 'start', -380)"); await sleep(700);
    await click(".table-view summary", 600); await sleep(400); await point("#metrics-table tbody", 300);
  });
  await scene("history", async () => {
    await D("hideCursor()"); await D("scrollTo('body', 'top')"); await D("reveal('.history')"); await sleep(1400);
    await point(".history-list li:first-child button", 300);
  });
  await scene("upload", async () => {
    await D("reveal('#add-dataset-btn')"); await sleep(900);
    await click("#add-dataset-btn"); await D("hideCursor()");
    await atCap(1); await point(".format-help summary", 300); await sleep(2500); await point("#up-test", 300);
  });
  await js("document.getElementById('add-dialog').close()"); await sleep(400);
  await scene("outro", async () => { await D("hideCursor()"); await atCap(0, 4.0); await D(`card('<div><h1>X<span>-</span>TREATS</h1><p>Accurate · Fair · Explainable — one micro-batch at a time</p></div>')`); });
  await sleep(1500);
  }

  clearInterval(writer); await send("Page.stopScreencast");
  timeline.end = now();
  const runs = await (await fetch(BASE + "/api/runs")).json();
  timeline.run_id = runs.length ? runs[0].id : null;
  fs.writeFileSync(path.join(BUILD, "timeline.json"), JSON.stringify(timeline, null, 1));
  console.log("frames:", timeline.frames.length, "· duration (real):", timeline.end.toFixed(1), "s · run:", timeline.run_id, "· JS errors:", jsErrors.length ? jsErrors : "none");
  ws.close(); chrome.kill();
  try { fs.rmSync(profile, { recursive: true, force: true }); } catch (e) { /* ignore */ }
  process.exit(0);
})().catch((e) => { console.error("ERROR", e); if (chromeProc) chromeProc.kill(); process.exit(2); });
