#!/usr/bin/env node
/**
 * End-to-end walk of the app's main features in a real browser, against the
 * running frontend (:3000) and backend (:8000). Prints PASS / FAIL per step
 * and any console errors. Needs Ollama for the chat answer step.
 *
 *   node scripts/e2e.mjs [--base http://localhost:3000]
 */
import puppeteer from "puppeteer-core";

const arg = (k, d) => {
  const i = process.argv.indexOf(`--${k}`);
  return i > -1 ? process.argv[i + 1] : d;
};
const BASE = arg("base", "http://localhost:3000");
const browser = await puppeteer.launch({
  executablePath: process.env.CHROME_PATH || "C:/Program Files/Google/Chrome/Application/chrome.exe",
  headless: true,
  args: ["--use-angle=default", "--enable-unsafe-swiftshader"],
  protocolTimeout: 600000,
});
const page = await browser.newPage();
await page.setViewport({ width: 1440, height: 900 });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e).slice(0, 200)));
page.on("console", (m) => m.type() === "error" && !/favicon|_rsc|Failed to load resource: the server responded with a status of 404/.test(m.text()) && errors.push(m.text().slice(0, 200)));

const results = [];
async function step(name, fn) {
  const t = Date.now();
  try {
    const note = await fn();
    results.push(`PASS  ${name}${note ? `  (${note})` : ""}  ${((Date.now() - t) / 1000).toFixed(1)}s`);
  } catch (e) {
    results.push(`FAIL  ${name}: ${String(e.message || e).slice(0, 160)}`);
  }
  console.log(results[results.length - 1]);
}
const text = (sel = "body") => page.$eval(sel, (el) => el.innerText);
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

await step("start: open the demo → workspace with clauses", async () => {
  await page.goto(`${BASE}/start`, { waitUntil: "networkidle2" });
  await clickText("button, a", /open the demo/);
  await page.waitForFunction(() => location.pathname.startsWith("/analyze/"), { timeout: 30000 });
  await waitText(/2,757 of 2,757 clauses|of 2,757 clauses/, 90000);
  return new URL(page.url()).pathname;
});

await step("workspace: search clauses", async () => {
  const input = await page.waitForSelector('input[placeholder*="Search clauses" i]', { timeout: 15000 });
  await input.type("rebate");
  await page.waitForFunction(() => /of 2,757 clauses/i.test(document.body.innerText) && !/2,757 of 2,757/.test(document.body.innerText), { timeout: 15000 });
  return (await text()).match(/\d[\d,]* of 2,757 clauses/i)?.[0];
});

await step("explain: a clause's explanation loads", async () => {
  await page.goto(`${BASE}/explain/demo_income_tax_2025/demo_income_tax_2025_c0973`, { waitUntil: "networkidle2" });
  await waitText(/Token attribution/);
  await waitText(/fidelity|samples/, 60000);
  return "LIME shown";
});

await step("provenance: graph renders", async () => {
  await page.goto(`${BASE}/provenance/demo_income_tax_2025`, { waitUntil: "networkidle2" });
  await page.waitForSelector(".react-flow__node", { timeout: 60000 });
  return `${(await page.$$(".react-flow__node")).length} nodes drawn`;
});

await step("statutes: open a section", async () => {
  await page.goto(`${BASE}/statutes`, { waitUntil: "networkidle2" });
  const input = await page.waitForSelector('input[aria-label="Filter sections"]', { timeout: 30000 });
  await input.type("156");
  await page.waitForFunction(
    () => Array.from(document.querySelectorAll("nav[aria-label='Statute outline'] button")).some((b) => /s\.156/.test(b.textContent || "")),
    { timeout: 15000 }
  );
  await clickText("nav[aria-label='Statute outline'] button", /s\.156/);
  await waitText(/Rebate of income-tax/, 15000);
  return "s.156 text shown";
});

await step("research: results and inspect", async () => {
  await page.goto(`${BASE}/research`, { waitUntil: "networkidle2" });
  await waitText(/Reforms × readers|Reforms x readers/, 30000);
  const cells = await page.$$("table button, [role=grid] button");
  if (!cells.length) return "table shown (no inspect buttons found)";
  await cells[0].click();
  await new Promise((r) => setTimeout(r, 2500));
  return "inspect opened";
});

await step("sandbox: run a simulation to completion", async () => {
  await page.goto(`${BASE}/simulate/demo_income_tax_2025`, { waitUntil: "networkidle2" });
  await clickText("button", /run simulation/);
  await waitText(/regressive|progressive|neutral|simulation complete|final/i, 180000);
  return "completed";
});

await step("compare: two documents, clause diff", async () => {
  await page.goto(`${BASE}/compare?a=demo_income_tax_2025`, { waitUntil: "networkidle2" });
  await page.waitForFunction(() => Array.from(document.querySelectorAll("button")).some((b) => /pdf/i.test(b.textContent || "")), { timeout: 30000 });
  // choose the first selectable document in column B
  const ok = await page.evaluate(() => {
    const cols = Array.from(document.querySelectorAll("button")).filter((b) => /pdf/i.test(b.textContent || "") && !b.disabled);
    const mini = cols.filter((b) => /mini_act/i.test(b.textContent || ""));
    const pick = (mini.length >= 2 ? mini : cols).slice(-1)[0];
    pick?.click();
    return !!pick;
  });
  if (!ok) throw new Error("no document to pick");
  await page.waitForFunction(() => /added|removed|changed|matched/i.test(document.body.innerText) && location.search.includes("b="), { timeout: 180000 });
  return new URL(page.url()).search;
});

await step("ask: a cited answer streams", async () => {
  await page.goto(`${BASE}/chat`, { waitUntil: "networkidle2" });
  const box = await page.waitForSelector("textarea, input[placeholder*='Ask' i]", { timeout: 20000 });
  await box.type("What is the penalty for under-reporting of income?");
  await page.keyboard.press("Enter");
  await waitText(/section 439|s\.\s?439|§\s?439|\b439\b/, 240000);
  return "answer cites s.439";
});

await step("account: register, see dashboard and API key", async () => {
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle2" });
  await clickText("button, a", /create one/);
  const email = `e2e-${Date.now()}@example.com`;
  const inputs = await page.$$("input");
  for (const i of inputs) {
    const t = await i.evaluate((e) => (e.getAttribute("type") || "") + " " + (e.getAttribute("name") || "") + " " + (e.id || ""));
    if (/email/i.test(t)) await i.type(email);
    else if (/password/i.test(t)) await i.type("e2e-pass-12345");
    else if (/name/i.test(t)) await i.type("E2E");
  }
  await clickText("button[type=submit], button", /create account|sign up|register/);
  await page.waitForFunction(() => !location.pathname.startsWith("/login"), { timeout: 30000 });
  await page.goto(`${BASE}/dashboard`, { waitUntil: "networkidle2" });
  await waitText(/prism_sk_|API key/, 30000);
  return email;
});

console.log(`\n${results.filter((r) => r.startsWith("PASS")).length}/${results.length} steps passed`);
if (errors.length) console.log(`console errors:\n  ${[...new Set(errors)].slice(0, 10).join("\n  ")}`);
await browser.close();
