#!/usr/bin/env node
/**
 * Drives the Ask page in a real browser: an exact section, a follow-up that needs the earlier
 * turn, and a question the corpus cannot answer. Saves a screenshot.
 *   node scripts/probe-chat.mjs [--base http://localhost:3000] [--out <dir>]
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
  protocolTimeout: 600000,
});
const page = await browser.newPage();
await page.setViewport({ width: 1440, height: 1000 });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e).slice(0, 200)));
page.on("console", (m) => m.type() === "error" && !/favicon|_rsc|404/.test(m.text()) && errors.push(m.text().slice(0, 200)));

const body = () => page.evaluate(() => document.body.innerText);
const waitText = (re, timeout = 240000) =>
  page.waitForFunction((src) => new RegExp(src, "i").test(document.body.innerText), { timeout }, re.source);

async function ask(q, doneRe) {
  const t = Date.now();
  await page.click('textarea[aria-label="Your question"]');
  await page.keyboard.type(q);
  await page.keyboard.press("Enter");
  await waitText(doneRe);
  // the stream is finished when the stop button is gone
  await page.waitForFunction(() => !document.querySelector('button[aria-label="Stop"]'), { timeout: 240000 });
  console.log(`\nQ: ${q}  (${((Date.now() - t) / 1000).toFixed(1)}s)`);
}

await page.goto(`${BASE}/chat`, { waitUntil: "networkidle2" });
await waitText(/passages/);
console.log("corpus:", (await body()).match(/[\d,]+ passages/)?.[0]);

await ask("What is the rebate under section 156 of the Income-tax Act, 2025?", /exact section match|Checked against|No figure or quotation|statements? (conflicts?|carry)/);
let t = await body();
console.log("  exact match:", /exact section match/.test(t), "| verification line:", t.match(/(Checked against the sources[^\n]*|No figure or quotation[^\n]*|\d+ statements? conflicts?[^\n]*)/)?.[0]);
await page.screenshot({ path: `${OUT}/chat-section.png` });

await ask("And for senior citizens?", /Understood as/);
t = await body();
console.log("  understood as:", t.match(/Understood as:[^\n]+/)?.[0]);

await ask("How do I register a trademark in India?", /Not in the corpus/);
t = await body();
console.log("  abstained:", /Not in the corpus/.test(t), "| reason:", t.match(/Not found in the loaded corpus\.[^\n]+/)?.[0]?.slice(0, 160));
await page.screenshot({ path: `${OUT}/chat-abstain.png` });
console.log("console errors:", errors.length ? errors : "none");
await browser.close();
