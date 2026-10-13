import type { Metadata } from "next";
import StoryRoot from "@/story/StoryRoot";

export const metadata: Metadata = {
  title: { absolute: "PRISM: does a machine read the law the way the law reads?" },
};

export default function StoryPage() {
  return (
    <>
      <noscript>
        <style>{"[data-at]{opacity:1!important;transform:none!important;filter:none!important}"}</style>
      </noscript>
      <StoryRoot />
    </>
  );
}
