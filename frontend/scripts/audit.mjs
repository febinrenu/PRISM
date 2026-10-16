#!/usr/bin/env node
/**
 * Layout audit: loads every app page at several viewport sizes (and both
 * themes) and reports what a person would call a visual bug:
 *  - the page scrolls sideways;
 *  - content cut off by a container that hides overflow (not a deliberate
 *    "…" truncation, not a scroll area);
 *  - text that spills out of its box;
 *  - text smaller than the 12px floor;
 *  - buttons and links with no accessible name.
 * On the workspace it also clicks through every analysis tab.
 *
 *   node scripts/audit.mjs [--base http://localhost:3000] [--light] [--widths 1920,1440,1280,1024,768,390]
 */
import puppeteer from "puppeteer-core";

const arg = (k, d) => {
  const i = process.argv.indexOf(`--${k}`);
  return i > -1 ? process.argv[i + 1] : d;
};
const BASE = arg("base", "http://localhost:3000");
const WIDTHS = arg("widths", "1920,1440,1280,1024,768,390").split(",").map(Number);
const ROUTES = arg(
  "routes",
  "/start,/research,/statutes,/chat,/corpus,/compare,/dashboard,/login,/api-docs,/analyze/demo_income_tax_2025,/provenance/demo_income_tax_2025,/simulate/demo_income_tax_2025,/explain/demo_income_tax_2025/demo_income_tax_2025_c0973,/report/demo_income_tax_2025,/does-not-exist"
).split(",");
const LIGHT = process.argv.includes("--light");

const browser = await puppeteer.launch({
  executablePath: process.env.CHROME_PATH || "C:/Program Files/Google/Chrome/Application/chrome.exe",
  headless: true,
  args: ["--use-angle=default", "--enable-unsafe-swiftshader"],
  protocolTimeout: 300000,
});

/** Runs in the page: every finding as {kind, where, detail}. */
function inspect() {
  const out = [];
  const W = window.innerWidth;
  const desc = (el) => {
    const id = el.id ? `#${el.id}` : "";
    const cls = (el.className && typeof el.className === "string" ? el.className : "").split(/\s+/).filter(Boolean).slice(0, 4).join(".");
    const text = (el.textContent || el.getAttribute("aria-label") || "").replace(/\s+/g, " ").trim().slice(0, 50);
    return `${el.tagName.toLowerCase()}${id}${cls ? "." + cls : ""}${text ? ` "${text}"` : ""}`;
  };
  const visible = (el, r) => {
    if (r.width < 2 || r.height < 2) return false;
    const cs = getComputedStyle(el);
    if (cs.visibility === "hidden" || cs.display === "none" || Number(cs.opacity) === 0) return false;
    return r.bottom > 0 && r.top < window.innerHeight * 3 && r.right > 0 && r.left < W;
  };
  if (document.documentElement.scrollWidth > W + 1) out.push({ kind: "page scrolls sideways", where: "document", detail: `${document.documentElement.scrollWidth}px > ${W}px` });
  for (const el of document.querySelectorAll("body *")) {
    if (el.closest("svg,canvas,[aria-hidden=true],.react-flow,.recharts-wrapper,.react-pdf__Page,[data-audit-skip]")) continue;
    const r = el.getBoundingClientRect();
    if (!visible(el, r)) continue;
    const cs = getComputedStyle(el);
    const ox = cs.overflowX;
    const sw = el.scrollWidth;
    const cw = el.clientWidth;
    const ellipsis = cs.textOverflow === "ellipsis" || cs.webkitLineClamp !== "none";
    if ((ox === "hidden" || ox === "clip") && sw > cw + 3 && cw > 0 && !ellipsis) {
      // a clipped child that is itself scrolled or deliberately truncated is fine
      const child = Array.from(el.querySelectorAll("*")).find((c) => {
        const cr = c.getBoundingClientRect();
        return cr.width > 1 && (cr.right > r.right + 3 || cr.left < r.left - 3) && getComputedStyle(c).textOverflow !== "ellipsis";
      });
      if (child) out.push({ kind: "content cut off", where: desc(el), detail: `${desc(child)} extends ${Math.round(Math.max(child.getBoundingClientRect().right - r.right, r.left - child.getBoundingClientRect().left))}px past it` });
    }
    // text spilling out of a box that does not clip
    const hasText = Array.from(el.childNodes).some((n) => n.nodeType === 3 && n.textContent.trim().length > 2);
    if (hasText && ox === "visible" && sw > cw + 4 && cw > 0 && cs.display !== "inline" && !ellipsis) {
      out.push({ kind: "text spills out", where: desc(el), detail: `${sw - cw}px wider than its box` });
    }
    if (hasText && parseFloat(cs.fontSize) < 11.5) out.push({ kind: "text below 12px", where: desc(el), detail: cs.fontSize });
    if ((el.tagName === "BUTTON" || el.tagName === "A") && !(el.textContent || "").trim() && !el.getAttribute("aria-label") && !el.getAttribute("title") && !el.querySelector("img[alt]")) {
      out.push({ kind: "control without a name", where: desc(el), detail: el.outerHTML.slice(0, 80) });
    }
  }
  return out;
}

let total = 0;
const seen = new Map();
async function audit(page, label) {
  const findings = await page.evaluate(inspect);
  for (const f of findings) {
    const key = `${f.kind}|${f.where}`;
    if (!seen.has(key)) seen.set(key, { ...f, at: [] });
    seen.get(key).at.push(label);
    total++;
  }
}

for (const w of WIDTHS) {
  const page = await browser.newPage();
  await page.setViewport({ width: w, height: w < 600 ? 844 : w <= 1024 ? 1024 : 900 });
  if (LIGHT) await page.evaluateOnNewDocument(() => localStorage.setItem("prism-theme", "light"));
  for (const route of ROUTES) {
    try {
      await page.goto(BASE + route, { waitUntil: "networkidle2", timeout: 60000 });
    } catch {
      /* audit what loaded */
    }
    await new Promise((r) => setTimeout(r, 2500));
    await audit(page, `${route} @${w}`);
    if (route.startsWith("/analyze/")) {
      // every analysis tab
      const tabs = await page.$$('[role="tablist"][aria-label="Analysis views"] [role="tab"]');
      for (let i = 0; i < tabs.length; i++) {
        const t = (await page.$$('[role="tablist"][aria-label="Analysis views"] [role="tab"]'))[i];
        const name = await t.evaluate((e) => e.textContent.trim());
        await t.evaluate((e) => e.click());
        await new Promise((r) => setTimeout(r, 1800));
        await audit(page, `${route} tab ${name} @${w}`);
      }
    }
  }
  await page.close();
}
await browser.close();

const rows = [...seen.values()].sort((a, b) => b.at.length - a.at.length);
for (const f of rows) {
  console.log(`[${f.kind}] ${f.where}\n    ${f.detail}\n    at ${f.at.slice(0, 4).join(", ")}${f.at.length > 4 ? ` (+${f.at.length - 4} more)` : ""}`);
}
console.log(`\n${rows.length} distinct findings (${total} occurrences) over ${ROUTES.length} routes × ${WIDTHS.length} widths${LIGHT ? ", light theme" : ""}`);
