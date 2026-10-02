/**
 * Simulation impact report → PDF (html2canvas snapshot composed in jsPDF).
 * Decorative layers (orbs, noise) are excluded — html2canvas renders large
 * blur filters poorly and they bloat the raster.
 */
import html2canvas from "html2canvas";
import { jsPDF } from "jspdf";
import { tokens } from "@/lib/tokens";

export async function exportSimulationReport(node: HTMLElement, docId: string): Promise<void> {
  const canvas = await html2canvas(node, {
    backgroundColor: tokens.bg.base,
    scale: 2,
    logging: false,
    ignoreElements: (el) =>
      el.classList?.contains("noise-overlay") ||
      el.classList?.contains("gradient-orb-1") ||
      el.classList?.contains("gradient-orb-2") ||
      el.classList?.contains("gradient-orb-3"),
  });

  const pdf = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });
  const pageWidth = pdf.internal.pageSize.getWidth();
  const pageHeight = pdf.internal.pageSize.getHeight();
  const margin = 8;

  const imgWidth = pageWidth - margin * 2;
  const imgHeight = (canvas.height / canvas.width) * imgWidth;

  // Slice the tall canvas across as many A4 pages as needed.
  const usableHeight = pageHeight - margin * 2;
  let rendered = 0;
  let pageIndex = 0;
  while (rendered < imgHeight) {
    if (pageIndex > 0) pdf.addPage();
    pdf.setFillColor(6, 17, 13); // tokens.bg.base
    pdf.rect(0, 0, pageWidth, pageHeight, "F");
    pdf.addImage(
      canvas.toDataURL("image/jpeg", 0.92),
      "JPEG",
      margin,
      margin - rendered,
      imgWidth,
      imgHeight
    );
    rendered += usableHeight;
    pageIndex += 1;
  }

  pdf.save(`prism_impact_report_${docId.slice(0, 12)}.pdf`);
}
