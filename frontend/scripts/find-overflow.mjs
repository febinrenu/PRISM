#!/usr/bin/env node
/**
 * Which element makes a page scroll sideways? Hides the children of each level
 * in turn and follows the one whose removal clears the overflow, down to the
 * culprit. Finds what element-by-element probing misses: absolutely placed
 * descendants (an sr-only label) whose containing block is the page, not the
 * scroll box they sit in.
 *
 *   node scripts/find-overflow.mjs /research 390
 */
import puppeteer from "puppeteer-core";
const [route, w] = [process.argv[2], Number(process.argv[3] || 390)];
const browser = await puppeteer.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe", headless: true });
const p = await browser.newPage();
await p.setViewport({ width: w, height: 844 });
await p.goto("http://localhost:3000" + route, { waitUntil: "networkidle2", timeout: 120000 }).catch(() => {});
await new Promise((r) => setTimeout(r, 5000));
const report = await p.evaluate(() => {
  const W = innerWidth;
  const over = () => document.documentElement.scrollWidth - W;
  const out = [`initial overflow ${over()}`];
  const desc = (el) => `${el.tagName.toLowerCase()}${el.id ? "#" + el.id : ""}.${String(el.className).split(/\s+/).slice(0, 5).join(".")}`;
  // walk down: at each level find the child whose removal clears the overflow
  let node = document.body;
  for (let depth = 0; depth < 25 && over() > 0; depth++) {
    let culprit = null;
    for (const c of node.children) {
      const prev = c.style.display;
      c.style.display = "none";
      const cleared = over() <= 0;
      c.style.display = prev;
      if (cleared) { culprit = c; break; }
    }
    if (!culprit) { out.push(`no single child of ${desc(node)} clears it`); break; }
    const r = culprit.getBoundingClientRect();
    const cs = getComputedStyle(culprit);
    out.push(`${"  ".repeat(depth)}${desc(culprit)} [x ${Math.round(r.left)}..${Math.round(r.right)}, w ${Math.round(r.width)}, pos ${cs.position}, ox ${cs.overflowX}, transform ${cs.transform.slice(0, 30)}]`);
    node = culprit;
  }
  return out;
});
console.log(report.join("\n"));
await browser.close();
