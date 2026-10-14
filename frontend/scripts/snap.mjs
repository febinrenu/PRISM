#!/usr/bin/env node
/** Screenshot one URL with the real GPU after a wait (debugging aid): node scripts/snap.mjs URL OUT [scrollVh] */
import puppeteer from "puppeteer-core";
const [url, out, vh] = process.argv.slice(2);
const browser = await puppeteer.launch({
  executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe",
  headless: true,
  args: ["--use-angle=d3d11", "--enable-gpu", "--ignore-gpu-blocklist"],
});
const page = await browser.newPage();
await page.setViewport({ width: 1440, height: 900 });
page.on("console", (m) => m.type() !== "info" && m.type() !== "log" && console.log(`[${m.type()}]`, m.text().slice(0, 800)));
page.on("pageerror", (e) => console.log("[pageerror]", String(e).slice(0, 800)));
await page.goto(url, { waitUntil: "networkidle2", timeout: 120000 });
await new Promise((r) => setTimeout(r, 11000));
if (vh) {
  await page.evaluate((v) => window.scrollTo(0, (Number(v) * window.innerHeight) / 100), vh);
  await new Promise((r) => setTimeout(r, 3500));
}
await page.screenshot({ path: out });
await browser.close();
