import type { Metadata } from "next";
import StoryRoot from "@/story/StoryRoot";

export const metadata: Metadata = {
  title: { absolute: "PRISM: reading tax law, and checking the reading" },
  description:
    "PRISM reads Indian tax statutes clause by clause, ties every number to its words, runs the law on the population it governs, and checks machine readings against the law.",
};

export default function StoryPage() {
  return (
    <>
      <noscript>
        <style>
          {
            ".beat{visibility:visible!important;opacity:1!important}.story-act{height:auto!important}.story-stage{position:relative!important;height:auto!important}.story-preloader{display:none!important}"
          }
        </style>
      </noscript>
      <StoryRoot />
    </>
  );
}
