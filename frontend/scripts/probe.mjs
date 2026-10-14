#!/usr/bin/env node
/** Open the story in Chrome; print console output, renderer and scene state (debugging aid). */
import puppeteer from "puppeteer-core";
const url = process.argv[2] || "http://localhost:3000/?debug=1";
const gpu = process.argv.includes("--gpu");
const browser = await puppeteer.launch({
  executablePath: process.env.CHROME_PATH || "C:/Program Files/Google/Chrome/Application/chrome.exe",
  headless: true,
  args: gpu ? ["--use-angle=d3d11", "--enable-gpu", "--ignore-gpu-blocklist"] : ["--use-angle=default", "--enable-unsafe-swiftshader"],
});
const page = await browser.newPage();
await page.setViewport({ width: 1440, height: 900 });
page.on("console", (m) => console.log(`[${m.type()}]`, m.text().slice(0, 1500)));
page.on("pageerror", (e) => console.log("[pageerror]", String(e).slice(0, 1500)));
await page.goto(url, { waitUntil: "networkidle2", timeout: 120000 });
await new Promise((r) => setTimeout(r, Number(process.env.WAIT || 12000)));
const info = await page.evaluate(() => {
  const p = window.__prism;
  const gl = p?.loop.gl;
  const objs = [];
  p?.loop.scene?.traverse((o) => objs.push(`${o.type}:${o.visible ? 1 : 0}`));
  return {
    tier: document.querySelector(".story-root")?.getAttribute("data-tier"),
    hasRender: !!p?.loop.render,
    director: p && { form: p.state.director.form, exposure: p.state.director.exposure, prism: p.state.director.prism, cam: p.state.director.cam },
    cam: p?.loop.camera && p.loop.camera.position.toArray().map((x) => x.toFixed(2)),
    programs: gl?.info.programs?.length,
    calls: gl?.info.render.calls,
    points: gl?.info.render.points,
    objs: objs.join(" "),
    count: p?.state.count,
    time: p?.state.time,
  };
});
console.log(JSON.stringify(info, null, 1));
await browser.close();
