#!/usr/bin/env node
/**
 * The landing story may only print numbers that come from the snapshot
 * (src/content/story.core.json, written by `python -m cli story-export`).
 * This scans the story's copy (JSX text and prose string literals in
 * src/story/acts.tsx and figures.tsx) for digits that are not identifiers:
 * years, assessment years, section numbers, clause labels.
 */
import { readFileSync } from "node:fs";

const FILES = ["src/story/acts.tsx", "src/story/figures.tsx"];
const ALLOWED = [
  /\b(?:19|20)\d{2}(?:-\d{2})?\b/g, // years and assessment years: 2025, 2022-23
  /\b(?:section|sections|s\.)\s?\d+[A-Z]*\b/gi, // section 156, s.87A
  /\bNo\.\s?\d\b/g, // Finance (No. 2) Act
  /\(\d+\)/g, // clause labels like (1)
];
const TAILWIND = /(?:^|\s)(?:[a-z]+:)*-?(?:bg|text|px|py|pt|pb|mt|mb|ml|mr|mx|my|gap|h|w|max-w|min-w|inset|top|left|right|bottom|grid|col|rounded|border|tracking|leading|opacity|z|translate|duration|from|via|to)-/;

let bad = 0;
for (const f of FILES) {
  const src = readFileSync(new URL(`../${f}`, import.meta.url), "utf8");
  const lines = src.split("\n");
  lines.forEach((line, i) => {
    if (/^\s*(import|\/\/|\*|\/\*)/.test(line)) return;
    const candidates = [];
    // JSX text between tags on this line
    for (const m of line.matchAll(/>([^<>{}]+)</g)) if (!/[=&?[\]]/.test(m[1])) candidates.push(m[1]);
    // a line that is only JSX text
    if (!/[<>{}=;()"'`[\]?:&|]/.test(line) && /[a-z]{3}/i.test(line)) candidates.push(line);
    // prose string literals (have a space and a letter, are not class lists)
    for (const m of line.matchAll(/"([^"]*[a-z][^"]* [^"]*)"|`([^`]*[a-z][^`]* [^`]*)`/gi)) {
      const s = (m[1] ?? m[2] ?? "").replace(/\$\{[^}]*\}/g, "");
      if (/[={}]/.test(s)) continue;
      if (!TAILWIND.test(s) && !/className|href|viewBox|d=/.test(line.slice(0, m.index))) candidates.push(s);
    }
    for (let c of candidates) {
      for (const re of ALLOWED) c = c.replace(re, "");
      const hit = c.match(/\d[\d,.]*/);
      if (hit) {
        bad++;
        console.log(`${f}:${i + 1}  number typed into story copy: "${hit[0]}" in "${c.trim().slice(0, 80)}"`);
      }
    }
  });
}
if (bad) {
  console.log(`\n${bad} literal(s): read them from the story snapshot instead.`);
  process.exit(1);
}
console.log("story copy: every number comes from the snapshot.");
