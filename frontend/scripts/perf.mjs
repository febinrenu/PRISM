#!/usr/bin/env node
/**
 * Story performance and flicker check, with the real GPU.
 *
 *   node scripts/perf.mjs [--base http://localhost:3000] [--tier 2] [--speed 40]
 *
 * Scrolls the whole landing at a constant speed (vh per second) and reports:
 *  - frame time p50 / p95 / max per act, and frames over 33 ms;
 *  - WebGL programs and textures at reveal vs at the end (must not grow:
 *    nothing may compile or upload mid-story);
 *  - a flash check: mean luminance sampled from screenshots; a frame-to-frame
 *    change above 0.1 counts as a flash (WCAG 2.3.1 asks for at most three a second).
 */
import puppeteer from "puppeteer-core";

const arg = (k, d) => {
  const i = process.argv.indexOf(`--${k}`);
  return i > -1 ? process.argv[i + 1] : d;
};
const BASE = arg("base", "http://localhost:3000");
const TIER = arg("tier", "");
const SPEED = Number(arg("speed", "40"));

const browser = await puppeteer.launch({
  executablePath: process.env.CHROME_PATH || "C:/Program Files/Google/Chrome/Application/chrome.exe",
  headless: true,
  // --dgpu asks Chrome for the discrete GPU on hybrid laptops
  args: ["--use-angle=d3d11", "--enable-gpu", "--ignore-gpu-blocklist", ...(process.argv.includes("--dgpu") ? ["--force_high_performance_gpu"] : [])],
  protocolTimeout: 600000,
});
const page = await browser.newPage();
await page.setViewport({ width: 1440, height: 900 });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e).slice(0, 200)));
page.on("console", (m) => m.type() === "error" && errors.push(m.text().slice(0, 200)));
await page.goto(`${BASE}/?debug=1${TIER ? `&tier=${TIER}` : ""}`, { waitUntil: "networkidle2", timeout: 120000 });
await page.waitForFunction(() => !document.querySelector(".story-preloader") && window.__prism?.loop.gl, { timeout: 120000 });
await new Promise((r) => setTimeout(r, 1500));

const info = await page.evaluate(() => {
  const gl = window.__prism.loop.gl;
  const ctx = gl.getContext();
  const ext = ctx.getExtension("WEBGL_debug_renderer_info");
  return {
    renderer: ext ? ctx.getParameter(ext.UNMASKED_RENDERER_WEBGL) : "?",
    tier: document.querySelector(".story-root")?.getAttribute("data-tier"),
    particles: window.__prism.state.count,
    programs: gl.info.programs.length,
    textures: gl.info.memory.textures,
    geometries: gl.info.memory.geometries,
  };
});
console.log(`renderer  ${info.renderer}`);
console.log(`tier ${info.tier}, ${info.particles} particles; at reveal: ${info.programs} programs, ${info.textures} textures, ${info.geometries} geometries`);

// pass 1: frame times while scrolling at a constant speed
const result = await page.evaluate(async (speed) => {
  const vh = window.innerHeight / 100;
  const total = document.documentElement.scrollHeight - window.innerHeight;
  const acts = Array.from(document.querySelectorAll("[data-act]")).map((el) => ({
    id: el.dataset.act,
    top: el.getBoundingClientRect().top + window.scrollY,
  }));
  const frames = [];
  let last = performance.now();
  let y = 0;
  await new Promise((done) => {
    const step = (now) => {
      const dt = now - last;
      last = now;
      y = Math.min(total, y + (speed * vh * dt) / 1000);
      window.scrollTo(0, y);
      let act = acts[0].id;
      for (const a of acts) if (a.top <= y + 1) act = a.id;
      frames.push([act, dt]);
      if (y >= total) done();
      else requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  });
  return frames.slice(2);
}, SPEED);

const byAct = new Map();
for (const [act, dt] of result) {
  if (!byAct.has(act)) byAct.set(act, []);
  byAct.get(act).push(dt);
}
const pct = (a, p) => a[Math.min(a.length - 1, Math.floor(a.length * p))];
console.log("\nact        frames   p50 ms   p95 ms   max ms   >33ms");
let hitches = 0;
for (const [act, list] of byAct) {
  const s = [...list].sort((a, b) => a - b);
  const over = list.filter((x) => x > 33).length;
  hitches += over;
  console.log(
    `${act.padEnd(10)} ${String(list.length).padStart(6)} ${pct(s, 0.5).toFixed(1).padStart(8)} ${pct(s, 0.95).toFixed(1).padStart(8)} ${s[s.length - 1].toFixed(1).padStart(8)} ${String(over).padStart(7)}`
  );
}
const all = result.map((x) => x[1]).sort((a, b) => a - b);
console.log(`all        ${String(all.length).padStart(6)} ${pct(all, 0.5).toFixed(1).padStart(8)} ${pct(all, 0.95).toFixed(1).padStart(8)} ${all[all.length - 1].toFixed(1).padStart(8)} ${String(hitches).padStart(7)}`);

const after = await page.evaluate(() => {
  const gl = window.__prism.loop.gl;
  return { programs: gl.info.programs.length, textures: gl.info.memory.textures, geometries: gl.info.memory.geometries };
});
console.log(`\nat the end: ${after.programs} programs, ${after.textures} textures, ${after.geometries} geometries` +
  (after.programs > info.programs || after.textures > info.textures ? "  <-- GREW (something compiled or uploaded mid-story)" : "  (no growth)"));

// pass 2: luminance from screenshots, scrolling back up
await page.evaluate(() => window.scrollTo(0, 0));
await new Promise((r) => setTimeout(r, 1500));
const total = await page.evaluate(() => document.documentElement.scrollHeight - window.innerHeight);
const lumas = [];
const stepPx = Math.round((SPEED * 9) / 10); // 900px viewport: SPEED vh/s at ~10 samples/s
for (let y = 0; y <= total; y += stepPx) {
  await page.evaluate((v) => window.scrollTo(0, v), y);
  await new Promise((r) => setTimeout(r, 90));
  // the visible viewport only: a clipped capture is taken in document coordinates and can show the top of the page
  const buf = await page.screenshot({ type: "jpeg", quality: 30, captureBeyondViewport: false });
  if (process.env.SAVE) (await import("node:fs")).writeFileSync(`${process.env.SAVE}/lum_${y}.jpg`, buf);
  // decode off the DOM (ImageBitmap + OffscreenCanvas) so measuring barely touches the page
  lumas.push(await page.evaluate(async (b64) => {
    const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
    const bmp = await createImageBitmap(new Blob([bytes], { type: "image/jpeg" }));
    const c = new OffscreenCanvas(bmp.width, bmp.height);
    const x = c.getContext("2d");
    x.drawImage(bmp, 0, 0);
    const d = x.getImageData(0, 0, c.width, c.height).data;
    let s = 0;
    for (let i = 0; i < d.length; i += 4) s += (0.2126 * d[i] + 0.7152 * d[i + 1] + 0.0722 * d[i + 2]) / 255;
    return s / (d.length / 4);
  }, buf.toString("base64")));
}
let flashes = 0;
let maxJump = 0;
for (let i = 1; i < lumas.length; i++) {
  const j = Math.abs(lumas[i] - lumas[i - 1]);
  maxJump = Math.max(maxJump, j);
  if (j > 0.1) flashes++;
  if (j > 0.07) console.log(`  step ${j.toFixed(3)} at ${Math.round((i * stepPx) / 9)} vh`);
}
console.log(`\nluminance: ${lumas.length} samples, mean ${(lumas.reduce((a, b) => a + b, 0) / lumas.length).toFixed(3)}, largest step ${maxJump.toFixed(3)}, flashes (>0.1) ${flashes}`);
if (errors.length) console.log(`\nerrors:\n  ${errors.slice(0, 8).join("\n  ")}`);
await browser.close();
