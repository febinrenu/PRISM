#!/usr/bin/env node
/** Hover the pointer across the verdict board and the fault columns; save what the hover card shows (debugging aid). */
import puppeteer from "puppeteer-core";
const out = process.argv[2] || "shots";
const browser = await puppeteer.launch({
  executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe",
  headless: true,
  args: ["--use-angle=d3d11", "--enable-gpu", "--ignore-gpu-blocklist"],
});
const page = await browser.newPage();
await page.setViewport({ width: 1440, height: 900 });
await page.goto("http://localhost:3000/?debug=1&freeze=1", { waitUntil: "networkidle2" });
await page.waitForFunction(() => !document.querySelector(".story-preloader") && window.__prism?.loop.gl, { timeout: 120000 });
for (const [id, at] of [["verdict", 0.6], ["faults", 0.6], ["read", 0.92]]) {
  await page.evaluate((id, at) => {
    const el = document.getElementById(id);
    window.scrollTo(0, el.getBoundingClientRect().top + window.scrollY + (el.offsetHeight - innerHeight) * at);
  }, id, at);
  await new Promise((r) => setTimeout(r, 3000));
  let found = null;
  for (let y = 120; y < 860 && !found; y += 24) {
    for (let x = 40; x < 1400 && !found; x += 24) {
      await page.mouse.move(x, y);
      await new Promise((r) => setTimeout(r, 20));
      const t = await page.evaluate(() => {
        const c = document.querySelector(".story-card");
        return c && c.style.opacity === "1" ? c.innerText : null;
      });
      if (t) found = { x, y, t };
    }
  }
  console.log(id, found ? `at ${found.x},${found.y}: ${found.t.replace(/\n/g, " | ")}` : "no card");
  if (found) await page.screenshot({ path: `${out}/hover_${id}.png` });
}
await browser.close();
