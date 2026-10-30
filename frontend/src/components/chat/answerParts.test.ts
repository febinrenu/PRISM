import { describe, expect, it } from "vitest";
import { splitAnswer } from "@/components/chat/answerParts";

const kinds = (text: string, unsupported: string[] = []) =>
  splitAnswer(text, unsupported).map((p) => `${p.kind}:${p.value}`);

describe("splitAnswer", () => {
  it("returns plain text untouched", () => {
    expect(kinds("No markers here.")).toEqual(["text:No markers here."]);
  });

  it("finds citation markers and their numbers", () => {
    const parts = splitAnswer("The fee is ₹5,000 [Source 1]. See also [Sources 2, 3].");
    const cites = parts.filter((p) => p.kind === "cite");
    expect(cites.map((c) => (c.kind === "cite" ? c.nums : []))).toEqual([[1], [2, 3]]);
  });

  it("flags a figure the verifier could not find", () => {
    expect(kinds("The limit is ₹9,99,999 [Source 1].", ["₹9,99,999"])).toEqual([
      "text:The limit is ",
      "flag:₹9,99,999",
      "text: ",
      "cite:[Source 1]",
      "text:.",
    ]);
  });

  it("does not flag a short figure inside a longer one", () => {
    const parts = splitAnswer("A rebate of 15% and 25,000 and 5%.", ["5%"]);
    const flagged = parts.filter((p) => p.kind === "flag");
    expect(flagged).toHaveLength(1);
    // the flagged one is the standalone "5%" at the end, not the tail of "15%"
    expect(parts[parts.length - 2]).toEqual({ kind: "flag", value: "5%" });
    expect(parts.map((p) => p.value).join("")).toBe("A rebate of 15% and 25,000 and 5%.");
  });

  it("does not flag inside a number with separators", () => {
    expect(splitAnswer("The sum is 1,25,000.", ["25,000"]).some((p) => p.kind === "flag")).toBe(false);
    expect(splitAnswer("The sum is ₹12,500 or 12.5%.", ["12.5%"]).filter((p) => p.kind === "flag")).toHaveLength(1);
  });

  it("escapes regex characters in a flagged figure", () => {
    expect(splitAnswer("The rate is 8.33% of wages.", ["8.33%"]).filter((p) => p.kind === "flag")).toHaveLength(1);
    expect(splitAnswer("The rate is 8x33% of wages.", ["8.33%"]).some((p) => p.kind === "flag")).toBe(false);
  });

  it("always reassembles to the original text", () => {
    const text = "[Source 1] ₹5,000 (see [Source 2, 3]) and 5% [Source 9].";
    expect(splitAnswer(text, ["5%", "₹5,000"]).map((p) => p.value).join("")).toBe(text);
  });
});
