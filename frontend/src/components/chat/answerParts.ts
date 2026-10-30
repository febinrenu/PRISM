// An answer split into plain text, [Source N] markers and flagged figures.

export type AnswerPart =
  | { kind: "text"; value: string }
  | { kind: "cite"; value: string; nums: number[] }
  | { kind: "flag"; value: string };

// A [Source N] marker (named groups: the whole marker, and the numbers inside it).
const CITE = String.raw`\[\s*Sources?\s+(?<nums>[\d,\s]+)\]`;

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** `unsupported` are the amounts and rates the verifier could not find in the cited text. A flagged
 *  figure matches as a whole number: "5%" is not found inside "15%" or "₹25,000". */
export function splitAnswer(text: string, unsupported: string[] = []): AnswerPart[] {
  const flagged = unsupported.filter(Boolean).map(escapeRegExp);
  const flag = flagged.length ? `|(?<![\\d.,])(?<flag>${flagged.join("|")})(?![\\d])` : "";
  const re = new RegExp(`${CITE}${flag}`, "gi");
  const out: AnswerPart[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    if (m[0] === "") {
      re.lastIndex++;
      continue;
    }
    if (m.index > last) out.push({ kind: "text", value: text.slice(last, m.index) });
    if (m.groups?.nums !== undefined) {
      const nums = m.groups.nums
        .split(/[,\s]+/)
        .filter((x) => /^\d+$/.test(x))
        .map(Number);
      out.push({ kind: "cite", value: m[0], nums });
    } else {
      out.push({ kind: "flag", value: m[0] });
    }
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push({ kind: "text", value: text.slice(last) });
  return out;
}
