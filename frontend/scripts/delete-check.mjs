#!/usr/bin/env node
/**
 * Browser check of document deletion, against the running frontend (:3000)
 * and backend (:8000): a throwaway user uploads two PDFs, deletes one from
 * the workspace and one from the dashboard, and the server forgets both.
 *
 *   node scripts/delete-check.mjs <pdf> [--base http://localhost:3000] [--api http://127.0.0.1:8000]
 */
import { readFileSync } from "node:fs";
import puppeteer from "puppeteer-core";

const arg = (k, d) => {
  const i = process.argv.indexOf(`--${k}`);
  return i > -1 ? process.argv[i + 1] : d;
};
const BASE = arg("base", "http://localhost:3000");
const API = arg("api", "http://127.0.0.1:8000");
const pdf = readFileSync(process.argv[2]);

const email = `delete-check-${Date.now()}@example.com`;
const reg = await fetch(`${API}/api/auth/register`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ email, name: "Delete check", password: "delete-check-pw" }),
}).then((r) => r.json());
const auth = { Authorization: `Bearer ${reg.token}` };

async function upload(name) {
  const form = new FormData();
  form.append("file", new Blob([pdf], { type: "application/pdf" }), name);
  const { doc_id } = await fetch(`${API}/api/upload`, { method: "POST", headers: auth, body: form }).then((r) => r.json());
  // read the analysis stream to its end so the document is complete
  const res = await fetch(`${API}/api/analyze/${doc_id}`, { headers: auth });
  await res.text();
  return doc_id;
}
const status = (id) => fetch(`${API}/api/documents/${id}`, { headers: auth }).then((r) => r.status);

const ws = await upload("delete-from-workspace.pdf");
const dash = await upload("delete-from-dashboard.pdf");

const browser = await puppeteer.launch({
  executablePath: process.env.CHROME_PATH || "C:/Program Files/Google/Chrome/Application/chrome.exe",
  headless: true,
});
const page = await browser.newPage();
await page.setViewport({ width: 1440, height: 900 });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e).slice(0, 200)));
page.on("console", (m) => m.type() === "error" && !/favicon|_rsc|status of 404/.test(m.text()) && errors.push(m.text().slice(0, 200)));
await page.goto(`${BASE}/start`);
await page.evaluate((t) => localStorage.setItem("prism_token", t), reg.token);

let ok = true;
const check = (name, cond, detail = "") => {
  ok &&= !!cond;
  console.log(`${cond ? "PASS" : "FAIL"}  ${name}  ${detail}`);
};
const clickByText = (sel, re) =>
  page.waitForFunction(
    (s, src) => {
      const el = [...document.querySelectorAll(s)].find((b) => new RegExp(src).test(b.textContent || ""));
      if (el) el.click();
      return !!el;
    },
    { timeout: 30000 },
    sel,
    re.source
  );

// 1. the workspace: Delete, confirm, back to /start
check("both documents exist", (await status(ws)) === 200 && (await status(dash)) === 200);
await page.goto(`${BASE}/analyze/${ws}`);
await page.waitForSelector(`[aria-label^="Delete "]`, { timeout: 60000 });
await page.click(`[aria-label^="Delete "]`);
await page.waitForSelector(`[aria-label="Confirm deletion"]`);
await clickByText(`[aria-label="Confirm deletion"] button`, /^Delete$/);
await page.waitForFunction(() => location.pathname === "/start", { timeout: 30000 });
check("workspace delete returns to /start", true, page.url());
check("server forgot the workspace document", (await status(ws)) === 404);

// 2. the dashboard: the row's bin, confirm, the row goes
await page.goto(`${BASE}/dashboard`);
const bin = `[aria-label="Delete delete-from-dashboard.pdf"]`;
await page.waitForSelector(bin, { timeout: 60000 });
check("deleted document is not listed", !(await page.$(`[aria-label="Delete delete-from-workspace.pdf"]`)));
await page.click(bin);
await clickByText(`[aria-label="Confirm deletion"] button`, /^Delete$/);
await page.waitForFunction((s) => !document.querySelector(s), { timeout: 30000 }, bin);
check("dashboard row removed", true);
check("server forgot the dashboard document", (await status(dash)) === 404);
await page.reload();
await page.waitForFunction(() => /Uploaded documents/.test(document.body.innerText), { timeout: 30000 });
check("still gone after a reload", !(await page.$(bin)));

// 3. the shared demo offers no delete
await page.goto(`${BASE}/analyze/demo_income_tax_2025`);
await page.waitForFunction(() => /Re-analyse|clauses/.test(document.body.innerText), { timeout: 60000 });
check("the demo has no delete button", !(await page.$(`[aria-label^="Delete "]`)));

check("no console errors", errors.length === 0, errors.join(" | "));
await browser.close();
console.log(ok ? "ALL PASS" : "SOME FAILED");
process.exit(ok ? 0 : 1);
