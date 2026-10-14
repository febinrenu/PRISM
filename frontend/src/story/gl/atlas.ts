/**
 * The glyph atlas: every character the forms draw, rasterised once in the
 * mono face after the fonts have loaded, 16 × 16 cells. Cell 0 is unused
 * (the shader draws a soft dot for glyph 0).
 */
export const GRID = 16;
const CELL = 64;

export interface Atlas {
  canvas: HTMLCanvasElement;
  glyph: (ch: string) => number;
  count: number;
}

function monoFamily(): string {
  const probe = document.createElement("span");
  probe.className = "font-mono";
  probe.style.position = "absolute";
  probe.style.visibility = "hidden";
  document.body.appendChild(probe);
  const fam = getComputedStyle(probe).fontFamily || "monospace";
  probe.remove();
  return fam;
}

export async function buildAtlas(chars: string): Promise<Atlas> {
  const family = monoFamily();
  try {
    await document.fonts.load(`500 ${CELL}px ${family}`, chars);
    await document.fonts.ready;
  } catch {
    /* draw with whatever is available */
  }
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = GRID * CELL;
  const ctx = canvas.getContext("2d")!;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = "#fff";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.font = `500 ${Math.round(CELL * 0.62)}px ${family}`;
  const index = new Map<string, number>();
  const list = Array.from(chars).slice(0, GRID * GRID - 1);
  list.forEach((ch, k) => {
    const i = k + 1;
    index.set(ch, i);
    const cx = (i % GRID) * CELL + CELL / 2;
    const cy = Math.floor(i / GRID) * CELL + CELL / 2;
    ctx.fillText(ch, cx, cy + CELL * 0.04);
  });
  return { canvas, glyph: (ch) => index.get(ch) ?? 0, count: list.length };
}
