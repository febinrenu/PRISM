#!/usr/bin/env node
/**
 * Screenshot routes with the installed Chrome (puppeteer-core, no download).
 *
 *   node scripts/shoot.mjs [--base http://localhost:3000] [--out shots]
 *        [--routes /,/research] [--widths 390,1440] [--reduced] [--nowebgl]
 *        [--scroll 0,0.25,0.5]   (fractions of page height, for long pages)
 *
 * Also prints console errors and failed requests per page.
 */
import { mkdirSync } from "node:fs";
import { join } from "node:path";
import puppeteer from "puppeteer-core";

const arg = (k, d) => {
  const i = process.argv.indexOf(`--${k}`);
  return i > -1 ? process.argv[i + 1] : d;
};
const flag = (k) => process.argv.includes(`--${k}`);

const BASE = arg("base", "http://localhost:3000");
const OUT = arg("out", "shots");
const CHROME = process.env.CHROME_PATH || "C:/Program Files/Google/Chrome/Application/chrome.exe";
const ROUTES = arg(
  "routes",
  "/,/start,/research,/statutes,/chat,/corpus,/compare,/dashboard,/annotate,/api-docs,/login,/analyze/demo_income_tax_2025,/provenance/demo_income_tax_2025,/simulate/demo_income_tax_2025,/does-not-exist"
).split(",");
const WIDTHS = arg("widths", "390,1440").split(",").map(Number);
const SCROLL = arg("scroll", "0").split(",").map(Number);
const WAIT = Number(arg("wait", "2500"));
// --story "text:0.5,curve:0.8": scroll to a point inside each act of the landing story.
const STORY = arg("story", "");

mkdirSync(OUT, { recursive: true });
const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: true,
  args: flag("nowebgl") ? ["--disable-webgl", "--disable-3d-apis"] : ["--use-angle=default", "--enable-unsafe-swiftshader"],
});

for (const route of ROUTES) {
  for (const w of WIDTHS) {
    const page = await browser.newPage();
    const errors = [];
    page.on("console", (m) => m.type() === "error" && errors.push(m.text().slice(0, 200)));
    page.on("pageerror", (e) => errors.push(`pageerror: ${String(e).slice(0, 200)}`));
    page.on("requestfailed", (r) => errors.push(`failed: ${r.url().slice(0, 120)}`));
    await page.setViewport({ width: w, height: w < 600 ? 844 : 900, deviceScaleFactor: 1 });
    if (flag("reduced")) await page.emulateMediaFeatures([{ name: "prefers-reduced-motion", value: "reduce" }]);
    try {
      await page.goto(BASE + route, { waitUntil: "networkidle2", timeout: 60000 });
    } catch (e) {
      errors.push(`goto: ${e.message}`);
    }
    await new Promise((r) => setTimeout(r, WAIT));
    for (const spec of STORY ? STORY.split(",") : []) {
      const [id, at] = spec.split(":");
      await page.evaluate(
        (id, at) => {
          const el = document.getElementById(id);
          if (!el) return;
          const top = el.getBoundingClientRect().top + window.scrollY;
          const span = Math.max(1, el.offsetHeight - window.innerHeight);
          window.scrollTo(0, top + span * Number(at));
        },
        id,
        at
      );
      await new Promise((r) => setTimeout(r, Number(arg("settle", "2200"))));
      const name = `story_${id}_${at}_${w}${flag("reduced") ? "_rm" : ""}${flag("nowebgl") ? "_t0" : ""}.png`;
      await page.screenshot({ path: join(OUT, name) });
      console.log(`${name}${errors.length ? `  ERR ${errors.length}: ${errors.slice(0, 3).join(" | ")}` : ""}`);
    }
    if (STORY) {
      await page.close();
      continue;
    }
    for (const f of SCROLL) {
      if (f > 0) {
        await page.evaluate((frac) => window.scrollTo(0, (document.documentElement.scrollHeight - innerHeight) * frac), f);
        await new Promise((r) => setTimeout(r, 1400));
      }
      const name = `${route.replace(/[^a-z0-9]+/gi, "_") || "root"}_${w}${flag("reduced") ? "_rm" : ""}${flag("nowebgl") ? "_t0" : ""}${f ? `_s${f}` : ""}.png`;
      await page.screenshot({ path: join(OUT, name) });
      console.log(`${name}${errors.length ? `  ERR ${errors.length}: ${errors.slice(0, 3).join(" | ")}` : ""}`);
    }
    await page.close();
  }
}
await browser.close();
