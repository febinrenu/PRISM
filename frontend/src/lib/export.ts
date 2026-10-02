/**
 * PNG export helper. html-to-image cannot resolve CSS custom properties in
 * its backgroundColor option, so the token hex is passed explicitly.
 */
import { toPng } from "html-to-image";
import { tokens } from "@/lib/tokens";

export async function exportNodeAsPng(node: HTMLElement, filename: string): Promise<void> {
  const dataUrl = await toPng(node, {
    backgroundColor: tokens.bg.base,
    pixelRatio: 2,
    filter: (el) => {
      // Skip decorative layers that html-to-image renders poorly.
      const cls = (el as HTMLElement).classList;
      if (!cls) return true;
      return !cls.contains("noise-overlay") && !cls.contains("gradient-orb-1")
        && !cls.contains("gradient-orb-2") && !cls.contains("gradient-orb-3");
    },
  });
  const link = document.createElement("a");
  link.download = filename;
  link.href = dataUrl;
  link.click();
}
