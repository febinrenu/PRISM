"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { gsap } from "gsap";
import type { ComponentProps, MouseEvent } from "react";

/**
 * A link out of the story: a vermilion edge and an ink curtain sweep up
 * before the app route loads. Modified clicks and reduced motion navigate
 * normally.
 */
export default function CurtainLink({ href, onClick, ...rest }: ComponentProps<typeof Link> & { href: string }) {
  const router = useRouter();
  const go = (e: MouseEvent<HTMLAnchorElement>) => {
    onClick?.(e);
    if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const curtain = document.getElementById("story-curtain");
    if (!curtain) return;
    e.preventDefault();
    router.prefetch(href);
    gsap
      .timeline({ onComplete: () => router.push(href) })
      .set(curtain, { display: "block", yPercent: 100 })
      .to(curtain, { yPercent: 0, duration: 0.55, ease: "expo.inOut" });
  };
  return <Link href={href} onClick={go} {...rest} />;
}
