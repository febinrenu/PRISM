import { describe, expect, it } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ReadingNotice, { pageRanges } from "./ReadingNotice";

const base = { pages: 12, text: 12, decoded: 0, ocr: 0, unreadable: 0, ocr_pages: [], unreadable_pages: [], ocr_confidence: null, ocr_available: null };

describe("reading notice", () => {
  it("says nothing when every page came from the text layer", () => {
    expect(renderToStaticMarkup(createElement(ReadingNotice, { reading: base }))).toBe("");
    expect(renderToStaticMarkup(createElement(ReadingNotice, { reading: undefined }))).toBe("");
  });

  it("names OCR pages as ranges, with the confidence, as a warning", () => {
    const html = renderToStaticMarkup(createElement(ReadingNotice, {
      reading: { ...base, text: 8, ocr: 4, ocr_pages: [3, 5, 6, 7], ocr_confidence: 0.973, ocr_available: true },
    }));
    expect(html).toContain("4 pages were read by OCR (p. 3, 5–7, mean confidence 97%)");
    expect(html).toContain("bg-status-warning");
  });

  it("says when OCR is missing on the server", () => {
    const html = renderToStaticMarkup(createElement(ReadingNotice, {
      reading: { ...base, text: 11, unreadable: 1, unreadable_pages: [2], ocr_available: false },
    }));
    expect(html).toContain("1 page has no usable text (p. 2) and OCR is not installed on the server");
  });

  it("collapses runs of pages", () => {
    expect(pageRanges([9, 1, 2, 3, 5, 9])).toBe("p. 1–3, 5, 9");
  });
});
