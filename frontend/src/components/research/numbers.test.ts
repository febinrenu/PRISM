import { describe, expect, it } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { numbersNote } from "./InspectPanel";
import UnsupportedNumbers from "@/components/ui/UnsupportedNumbers";

describe("number checks", () => {
  it("says which numbers are not in the words an effect cites", () => {
    expect(numbersNote(undefined)).toBeNull();
    expect(numbersNote({ status: "unchecked", fields: [] })).toBeNull();
    expect(numbersNote({ status: "verified", fields: [] })).toEqual({ tone: "ok", text: "every number is in its quote" });
    expect(numbersNote({ status: "provision", fields: [{ field: "rate", value: 0.2, found: "provision" }] }))
      .toEqual({ tone: "warn", text: "in the provision but not in its quote: rate 20%" });
    expect(numbersNote({ status: "unsupported", fields: [{ field: "upper", value: 999999999, found: "missing" }, { field: "rate", value: 0.3, found: "quote" }] })?.tone)
      .toBe("bad");
    expect(numbersNote({ status: "unsupported", fields: [{ field: "upper", value: 999999999, found: "missing" }] })?.text)
      .toBe("not in the statute: upper ₹99,99,99,999");
  });

  it("asks for review when a model reading states a number the clause lacks", () => {
    expect(renderToStaticMarkup(createElement(UnsupportedNumbers, { numbers: [] }))).toBe("");
    const html = renderToStaticMarkup(createElement(UnsupportedNumbers, { numbers: ["fifty crore rupees"] }));
    expect(html).toContain("Needs review: fifty crore rupees is not in the clause");
  });
});
