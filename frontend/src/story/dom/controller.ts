/**
 * Drives the DOM side of the story from the scroll position: beats in and
 * out (masked word rises, staggered fades, counting figures), the marquee,
 * and the active chapter. Hysteresis keeps a beat from toggling while the
 * reader rests on its edge.
 */
import { gsap } from "gsap";
import { SplitText } from "gsap/SplitText";
import { ACTS, actProgress, type ActId } from "../engine/config";

gsap.registerPlugin(SplitText);

export const marquees = new Set<HTMLElement>();

interface Item {
  act: ActId;
  from: number;
  to: number;
  el: HTMLElement;
  tl: gsap.core.Timeline | null;
  on: boolean;
  counts: HTMLElement[];
}

const NUM = /^-?[\d,]*\.?\d+$/;

function countUp(el: HTMLElement) {
  const final = el.dataset.count ?? "";
  if (!NUM.test(final)) return;
  const target = Number(final.replace(/,/g, ""));
  const decimals = (final.split(".")[1] ?? "").length;
  const indian = /^\d{1,2}(,\d{2})+,\d{3}$/.test(final);
  const grouped = final.includes(",");
  const fmt = (v: number) =>
    grouped
      ? v.toLocaleString(indian ? "en-IN" : "en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
      : v.toFixed(decimals);
  const o = { v: 0 };
  gsap.killTweensOf(o);
  gsap.to(o, {
    v: target,
    duration: 1.4,
    ease: "expo.out",
    onUpdate: () => {
      el.textContent = fmt(o.v);
    },
    onComplete: () => {
      el.textContent = final;
    },
  });
}

export function createController(root: HTMLElement, onBeat?: (k: number) => void) {
  const items: Item[] = [];
  const splits: SplitText[] = [];
  for (const act of Array.from(root.querySelectorAll<HTMLElement>("[data-act]"))) {
    const id = act.dataset.act as ActId;
    for (const el of Array.from(act.querySelectorAll<HTMLElement>("[data-beat]"))) {
      const heads = Array.from(el.querySelectorAll<HTMLElement>("[data-split]"));
      const split = heads.length ? SplitText.create(heads, { type: "words", mask: "words", wordsClass: "split-word" }) : null;
      if (split) splits.push(split);
      const rises = el.querySelectorAll("[data-rise]");
      const tl = gsap.timeline({ paused: true });
      tl.set(el, { autoAlpha: 1 }, 0);
      if (split) tl.fromTo(split.words, { yPercent: 118 }, { yPercent: 0, duration: 1.05, ease: "expo.out", stagger: 0.03 }, 0);
      if (rises.length) tl.fromTo(rises, { y: 28, autoAlpha: 0 }, { y: 0, autoAlpha: 1, duration: 0.95, ease: "expo.out", stagger: 0.065 }, 0.14);
      gsap.set(el, { autoAlpha: 0 });
      items.push({
        act: id,
        from: Number(el.dataset.from),
        to: Number(el.dataset.to),
        el,
        tl,
        on: false,
        counts: Array.from(el.querySelectorAll<HTMLElement>("[data-count]")),
      });
    }
  }

  let marqueeX = 0;
  const update = (y: number, dt: number, velocity: number) => {
    for (const it of items) {
      const q = actProgress(it.act, y);
      const m = 0.006;
      const on = it.on ? q >= it.from - m && q < it.to + m : q >= it.from && q < it.to;
      if (on === it.on) continue;
      it.on = on;
      it.el.toggleAttribute("data-on", on);
      if (!it.tl) continue;
      if (on) {
        onBeat?.(items.indexOf(it));
        it.tl.timeScale(1).play();
        it.counts.forEach(countUp);
      } else {
        it.tl.timeScale(1.9).reverse();
      }
    }
    marqueeX += dt * (40 + Math.min(900, Math.abs(velocity) * 260));
    marquees.forEach((el) => {
      if (!el.isConnected) {
        marquees.delete(el);
        return;
      }
      const half = el.scrollWidth / 2 || 1;
      el.style.transform = `translate3d(${-(marqueeX % half)}px,0,0)`;
    });
  };

  const destroy = () => {
    items.forEach((it) => it.tl?.kill());
    splits.forEach((s) => s.revert());
  };

  return { update, destroy };
}

/** Index of the act whose stage holds the middle of the viewport. */
export function activeAct(y: number) {
  let start = 0;
  for (let i = 0; i < ACTS.length; i++) {
    if (y + 50 < start + ACTS[i].len) return i;
    start += ACTS[i].len;
  }
  return ACTS.length - 1;
}
