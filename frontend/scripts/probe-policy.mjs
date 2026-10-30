#!/usr/bin/env node
/**
 * Drives the Statute mode of the policy sandbox in a real browser and saves screenshots.
 *   node scripts/probe-policy.mjs [--base http://localhost:3000] [--out <dir>]
 */
import puppeteer from "puppeteer-core";
import { mkdirSync } from "node:fs";

const arg = (k, d) => {
  const i = process.argv.indexOf(`--${k}`);
  return i > -1 ? process.argv[i + 1] : d;
};
const BASE = arg("base", "http://localhost:3000");
const OUT = arg("out", ".");
mkdirSync(OUT, { recursive: true });
const browser = await puppeteer.launch({
  executablePath: process.env.CHROME_PATH || "C:/Program Files/Google/Chrome/Application/chrome.exe",
  headless: true,
  args: ["--use-angle=default", "--enable-unsafe-swiftshader"],
});
const page = await browser.newPage();
await page.setViewport({ width: 1440, height: 1000 });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e).slice(0, 200)));
page.on("console", (m) => m.type() === "error" && !/favicon|_rsc|404/.test(m.text()) && errors.push(m.text().slice(0, 200)));

const waitText = (re, timeout = 30000) =>
  page.waitForFunction((src) => new RegExp(src, "i").test(document.body.innerText), { timeout }, re.source);
const clickText = async (selector, re) => {
  const ok = await page.evaluate(
    (selector, src) => {
      const el = Array.from(document.querySelectorAll(selector)).find((e) => new RegExp(src, "i").test(e.textContent || ""));
      if (!el) return false;
      el.scrollIntoView({ block: "center" });
      el.click();
      return true;
    },
    selector,
    re.source
  );
  if (!ok) throw new Error(`no ${selector} matching ${re}`);
};

await page.goto(`${BASE}/simulate/demo_income_tax_2025`, { waitUntil: "networkidle2" });
await waitText(/Pricing the baseline|No change|Revenue effect/);
await waitText(/Revenue effect, per year/);
await page.screenshot({ path: `${OUT}/policy-baseline.png`, fullPage: false });
console.log("baseline:", (await page.evaluate(() => document.body.innerText)).match(/Baseline:[^\n]+/)?.[0]);

await clickText("button", /Make income up to/);
await waitText(/pay less|pay more/, 20000);
await waitText(/Across the assumptions the data cannot fix/, 30000);
await page.screenshot({ path: `${OUT}/policy-scenario.png`, fullPage: true });
const txt = await page.evaluate(() => document.body.innerText);
console.log("revenue card:", txt.match(/Revenue effect, per year\s+([^\n]+)\n([^\n]+)/)?.slice(1, 3));
console.log("attribution shown:", /What drove the revenue change/.test(txt), " tornado:", /Which assumption matters/.test(txt));

await clickText("button", /How far to trust it|The model against published/);
await waitText(/Simulated ÷ reported/, 30000);
await page.screenshot({ path: `${OUT}/policy-validation.png`, fullPage: true });

await clickText("button", /Clause dynamics/);
await waitText(/Try the rules on a synthetic society/);
console.log("dynamics mode ok; seed field:", await page.$('input[aria-label="Random seed"]') !== null);
console.log("console errors:", errors.length ? errors : "none");
await browser.close();
