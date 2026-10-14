/** Small deterministic helpers shared by the form builders and the scene. */

export function rng(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function gauss(r: () => number) {
  const u = Math.max(1e-9, r());
  const v = r();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

export const clamp = (x: number, a = 0, b = 1) => Math.min(b, Math.max(a, x));
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
export const smooth = (a: number, b: number, x: number) => {
  const t = clamp((x - a) / (b - a));
  return t * t * (3 - 2 * t);
};

/** Wrap text to a column width, keeping explicit line breaks. */
export function wrap(text: string, cols: number): string[] {
  const out: string[] = [];
  for (const para of text.split("\n")) {
    let line = "";
    for (const word of para.split(/\s+/).filter(Boolean)) {
      if (!line) line = word;
      else if (line.length + 1 + word.length <= cols) line += " " + word;
      else {
        out.push(line);
        line = word;
      }
      while (line.length > cols) {
        out.push(line.slice(0, cols));
        line = line.slice(cols);
      }
    }
    out.push(line);
  }
  return out;
}

/** Same as wrap, but returns each character's original offset, row and column. */
export function layout(text: string, cols: number): { ch: string; i: number; row: number; col: number }[] {
  const out: { ch: string; i: number; row: number; col: number }[] = [];
  let row = 0;
  let col = 0;
  let i = 0;
  const words = text.split(/(\s+)/);
  for (const w of words) {
    if (!w) continue;
    if (/^\s+$/.test(w)) {
      for (const c of w) {
        if (c === "\n") {
          row++;
          col = 0;
        } else if (col > 0) col++;
        i++;
      }
      continue;
    }
    if (col > 0 && col + w.length > cols) {
      row++;
      col = 0;
    }
    for (const c of w) {
      if (col >= cols) {
        row++;
        col = 0;
      }
      out.push({ ch: c, i, row, col });
      col++;
      i++;
    }
  }
  return out;
}

/** 30-bit Morton code of a point normalised to the unit cube. */
export function morton(x: number, y: number, z: number) {
  const s = (v: number) => {
    let n = Math.min(1023, Math.max(0, Math.floor(v * 1023)));
    n = (n | (n << 16)) & 0x030000ff;
    n = (n | (n << 8)) & 0x0300f00f;
    n = (n | (n << 4)) & 0x030c30c3;
    n = (n | (n << 2)) & 0x09249249;
    return n;
  };
  return s(x) | (s(y) << 1) | (s(z) << 2);
}
