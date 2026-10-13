#!/usr/bin/env node
/**
 * Design-system checks that ESLint does not cover:
 *  - no text below 12px (Tailwind arbitrary sizes, fontSize props);
 *  - no raw colour literals outside the token file and the WebGL story;
 *  - three / @react-three / gsap imported only inside src/story and
 *    src/components/three, so app bundles stay light;
 *  - no classes from the retired theme.
 * Exit 1 on any finding.
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";

const ROOT = new URL("../src/", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const files = [];
(function walk(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p);
    else if (/\.(tsx?|css)$/.test(name)) files.push(p);
  }
})(ROOT);

const rel = (p) => relative(ROOT, p).split(sep).join("/");
const colourAllowed = (r) =>
  r.startsWith("design/") || r.startsWith("story/") || r.startsWith("components/three/") ||
  r === "app/global-error.tsx" || r === "app/layout.tsx" || r.endsWith(".css") || r.startsWith("app/opengraph");
const heavyAllowed = (r) => r.startsWith("story/") || r.startsWith("components/three/");

const rules = [
  { name: "text below 12px", re: /text-\[(?:[0-9]|1[01])(?:\.\d+)?px\]/g, applies: () => true },
  { name: "fontSize below 12", re: /fontSize[:=]\s*\{?\s*["']?(?:[0-9]|1[01])(?:\.\d+)?(?:px)?["']?\s*\}?(?![0-9])/g, applies: () => true },
  { name: "raw colour literal", re: /["'`]#[0-9a-fA-F]{3,8}["'`]|rgba?\(\s*(?!0\s*,\s*0\s*,\s*0\s*,)\d/g, applies: (r) => !colourAllowed(r) && !r.endsWith(".css") },
  { name: "heavy import outside story", re: /from\s+["'](?:three|three\/[^"']*|@react-three\/[^"']*|gsap(?:\/[^"']*)?|@gsap\/react|lenis(?:\/[^"']*)?)["']/g, applies: (r) => !heavyAllowed(r) },
  { name: "retired theme class", re: /font-manrope|font-playfair|prism-gradient|bg-prism-gradient/g, applies: () => true },
];

let count = 0;
for (const f of files) {
  const r = rel(f);
  const lines = readFileSync(f, "utf8").split("\n");
  lines.forEach((line, i) => {
    for (const rule of rules) {
      if (!rule.applies(r)) continue;
      rule.re.lastIndex = 0;
      const m = rule.re.exec(line);
      if (m) {
        count++;
        console.log(`src/${r}:${i + 1}  ${rule.name}  ${m[0]}`);
      }
    }
  });
}
if (count) {
  console.log(`\n${count} design finding(s).`);
  process.exit(1);
}
console.log(`lint:design clean (${files.length} files).`);
