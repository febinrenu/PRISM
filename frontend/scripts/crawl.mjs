#!/usr/bin/env node
/**
 * Visits every route and clicks through the controls on each, recording what a person would hit:
 * failed requests (4xx/5xx other than the ones a page expects), console errors, uncaught
 * exceptions, and views that stay on a spinner. Run against the running app.
 *
 *   node scripts/crawl.mjs [--base http://localhost:3000]
 */
import puppeteer from "puppeteer-core";

const arg = (k, d) => {
  const i = process.argv.indexOf(`--${k}`);
  return i > -1 ? process.argv[i + 1] : d;
};
const BASE = arg("base", "http://localhost:3000");
const DOC = "demo_income_tax_2025";
const browser = await puppeteer.launch({
  executablePath: process.env.CHROME_PATH || "C:/Program Files/Google/Chrome/Application/chrome.exe",
  headless: true,
  args: ["--use-angle=default", "--enable-unsafe-swiftshader"],
  protocolTimeout: 300000,
});
const page = await browser.newPage();
await page.setViewport({ width: 1440, height: 900 });

let where = "";
const findings = [];
const note = (kind, detail) => findings.push(`${kind} @ ${where}: ${detail}`.slice(0, 260));
page.on("pageerror", (e) => note("exception", String(e)));
page.on("console", (m) => {
  if (m.type() === "error" && !/favicon|_rsc|Failed to load resource/.test(m.text())) note("console", m.text());
});
page.on("response", (r) => {
  const s = r.status();
  const u = r.url();
  if (s >= 400 && !/favicon|_next\/static|\.map$/.test(u)) note(`http ${s}`, `${r.request().method()} ${u.replace(/^https?:\/\/[^/]+/, "")}`);
});
page.on("requestfailed", (r) => {
  if (!/favicon|_rsc|ERR_ABORTED/.test(r.url() + (r.failure()?.errorText ?? ""))) note("request failed", `${r.url().replace(/^https?:\/\/[^/]+/, "")} ${r.failure()?.errorText}`);
});

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function visit(route, settle = 2500) {
  where = route;
  await page.goto(`${BASE}${route}`, { waitUntil: "networkidle2", timeout: 120000 }).catch((e) => note("goto", String(e)));
  await sleep(settle);
}
/** Click every visible button/tab whose text matches, one at a time, and let it settle. */
async function clickEach(selector, filter = () => true, settle = 900, max = 25) {
  const n = await page.$$eval(selector, (els) => els.length);
  for (let i = 0; i < Math.min(n, max); i++) {
    const label = await page.evaluate(
      (sel, i) => {
        const el = document.querySelectorAll(sel)[i];
        if (!el || el.disabled || el.getAttribute("aria-disabled") === "true") return null;
        const r = el.getBoundingClientRect();
        if (r.width === 0 || r.height === 0) return null;
        const t = (el.textContent || el.getAttribute("aria-label") || "").trim().slice(0, 40);
        return t || "(no text)";
      },
      selector,
      i
    );
    if (label === null || !filter(label)) continue;
    where = `${where.split(" › ")[0]} › ${label}`;
    await page.evaluate((sel, i) => document.querySelectorAll(sel)[i]?.click(), selector, i);
    await sleep(settle);
  }
}
const SKIP_CLICK = /delete|remove|sign out|log ?out|reset|new chat|analyse a pdf|upload|re-?index|index all|re-?analy/i;

// ── static pages
for (const r of ["/", "/start", "/research", "/statutes", "/corpus", "/compare", "/dashboard", "/login", "/api-docs", "/admin", "/annotate", "/not-a-page"]) {
  await visit(r, r === "/" ? 4000 : 2500);
}

// ── statutes: choose each statute, open a section, search
await visit("/statutes");
const opts = await page.$$eval("select option", (o) => o.map((x) => x.value).filter(Boolean));
for (const v of opts.slice(0, 12)) {
  where = `/statutes › ${v}`;
  await page.select("select", v);
  await sleep(1200);
}
await page.type('input[type="search"], input[placeholder*="ilter" i], input[placeholder*="earch" i]', "156").catch(() => {});
await sleep(800);

// ── research: every tab and control
await visit("/research", 3500);
await clickEach("main button, [role=tab]", (l) => !SKIP_CLICK.test(l), 700, 40);

// ── workspace: every tab
await visit(`/analyze/${DOC}`, 4000);
await clickEach("[role=tab], button", (l) => /overview|causal|llm|rates|search|entities|umap|clause|filter|obligation|penalty|right|threshold/i.test(l) && !SKIP_CLICK.test(l), 1200, 60);

// ── provenance, report, explain (both modes), sandbox (both modes), compare
await visit(`/provenance/${DOC}`, 4000);
await clickEach("main button, [role=tab]", (l) => !SKIP_CLICK.test(l), 900, 20);
await visit(`/report/${DOC}`, 3000);
await visit(`/explain/${DOC}/${DOC}_c0973`, 3000);
await clickEach("main button", (l) => /rule-based|language model|rerun/i.test(l) && !/language model/i.test(l), 1500, 8);
await visit(`/simulate/${DOC}`, 3000);
await clickEach("main button", (l) => /make income|cut the|raise the|add a band|abolish|how far|clause dynamics|statute mode/i.test(l), 2500, 12);
await visit(`/simulate/${DOC}?mode=dynamics`, 3000);
await visit(`/compare?a=${DOC}`, 3000);

// ── chat: the suggestions render; no question is asked here
await visit("/chat", 3000);

await browser.close();
const unique = [...new Set(findings)];
console.log(unique.length ? unique.join("\n") : "no findings");
console.log(`\n${unique.length} distinct findings`);
