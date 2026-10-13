"use client";

import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { useFrame, useThree } from "@react-three/fiber";
import { tokens } from "@/design/tokens";
import { inr, story } from "../data";
import { lerp, presence, progress, smooth, state } from "../engine/store";
import { C, disposeObject, fontStack, rng, wrap } from "./kit";

const PW = 3.2;
const PH = 4.4;
const TEX_W = 1024;
const TEX_H = Math.round((TEX_W * PH) / PW);

interface Anchor {
  x: number;
  y: number;
}

/** Character ranges of the focus provision the story points at. */
function spans(text: string) {
  const find = (s: string, from = 0) => {
    const i = text.indexOf(s, from);
    return i < 0 ? null : ([i, i + s.length] as [number, number]);
  };
  const quoted = story.focus.effects.find((e) => e.span)?.span ?? null;
  const twelve = find("twelve hundred thousand rupees");
  const sixty = find("sixty thousand rupees");
  const cb = text.indexOf("in clause (b)");
  const missed: [number, number] | null = cb >= 0 ? [cb, text.indexOf(";", cb) + 1 || text.length] : null;
  const section = find("section 87A");
  return { quoted, twelve, sixty, missed, section };
}

function provisionTexture() {
  const text = story.focus.text;
  const sp = spans(text);
  const c = document.createElement("canvas");
  c.width = TEX_W;
  c.height = TEX_H;
  const ctx = c.getContext("2d")!;
  ctx.fillStyle = tokens.paper[100];
  ctx.fillRect(0, 0, TEX_W, TEX_H);
  // paper ruling and margin
  ctx.strokeStyle = "rgba(12,13,14,0.06)";
  ctx.lineWidth = 1;
  for (let y = 120; y < TEX_H; y += 46) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(TEX_W, y);
    ctx.stroke();
  }
  ctx.strokeStyle = "rgba(184,50,15,0.25)";
  ctx.beginPath();
  ctx.moveTo(64, 0);
  ctx.lineTo(64, TEX_H);
  ctx.stroke();

  const mono = fontStack("--font-geist-mono");
  const serif = fontStack("--font-serif");
  ctx.fillStyle = "rgba(12,13,14,0.55)";
  ctx.font = `500 22px ${mono}`;
  ctx.fillText(`THE FINANCE ACT, 2025  ·  ${story.focus.provision.replace("/", " · ")}`, 92, 70);

  const size = 31;
  const lh = 46;
  ctx.font = `400 ${size}px ${serif}`;
  const lines = wrap(ctx, text, TEX_W - 92 - 70);
  const anchors: Record<string, Anchor> = {};
  const within = (r: [number, number] | null, a: number, b: number) => !!r && a < r[1] && b > r[0];
  const toLocal = (cx: number, cy: number): Anchor => ({ x: (cx / TEX_W - 0.5) * PW, y: (0.5 - cy / TEX_H) * PH });

  lines.forEach((ln, li) => {
    const y = 140 + li * lh;
    if (y > TEX_H - 40) return;
    for (const w of ln.words) {
      const x = 92 + w.x;
      const ww = ctx.measureText(w.w).width;
      const missed = within(sp.missed, w.start, w.end);
      const read = within(sp.quoted, w.start, w.end);
      if (missed) {
        ctx.fillStyle = "rgba(255,79,31,0.20)";
        ctx.fillRect(x - 3, y - size * 0.82, ww + 9, size * 1.12);
      } else if (read) {
        ctx.fillStyle = "rgba(47,98,200,0.13)";
        ctx.fillRect(x - 3, y - size * 0.82, ww + 9, size * 1.12);
      }
      ctx.fillStyle = missed ? tokens.signal.ink : tokens.ink[900];
      ctx.fillText(w.w, x, y);
      const mark = (k: string, r: [number, number] | null) => {
        if (r && !anchors[k] && w.start >= r[0] && w.start < r[1]) anchors[k] = toLocal(x + ww / 2, y - size * 0.3);
      };
      mark("section", sp.section);
      mark("twelve", sp.twelve);
      mark("sixty", sp.sixty);
      mark("missed", sp.missed);
    }
  });
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 8;
  return { tex, anchors };
}

function plateTexture(title: string, sub: string, seed: number) {
  const W = 512;
  const H = Math.round((W * PH) / PW);
  const c = document.createElement("canvas");
  c.width = W;
  c.height = H;
  const ctx = c.getContext("2d")!;
  const r = rng(seed);
  ctx.fillStyle = tokens.paper[200];
  ctx.fillRect(0, 0, W, H);
  ctx.strokeStyle = "rgba(12,13,14,0.07)";
  for (let y = 150; y < H; y += 24) {
    ctx.beginPath();
    ctx.moveTo(30, y);
    ctx.lineTo(W - 30 - r() * 120, y);
    ctx.stroke();
  }
  ctx.fillStyle = tokens.ink[900];
  ctx.font = `400 30px ${fontStack("--font-serif")}`;
  const lines = wrap(ctx, title, W - 60);
  lines.slice(0, 3).forEach((ln, i) => ctx.fillText(ln.words.map((w) => w.w).join(" "), 30, 56 + i * 34));
  ctx.fillStyle = "rgba(12,13,14,0.55)";
  ctx.font = `500 15px ${fontStack("--font-geist-mono")}`;
  ctx.fillText(sub.toUpperCase(), 30, 56 + Math.min(3, lines.length) * 34 + 8);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

function tagTexture(label: string, value: string, ok: boolean, note?: string) {
  const W = 640;
  const H = 200;
  const c = document.createElement("canvas");
  c.width = W;
  c.height = H;
  const ctx = c.getContext("2d")!;
  ctx.fillStyle = ok ? tokens.ink[800] : "#1d1210";
  ctx.fillRect(0, 0, W, H);
  ctx.strokeStyle = ok ? "rgba(241,237,228,0.22)" : "rgba(255,79,31,0.75)";
  ctx.lineWidth = 3;
  ctx.strokeRect(1.5, 1.5, W - 3, H - 3);
  ctx.fillStyle = "rgba(241,237,228,0.6)";
  ctx.font = `500 26px ${fontStack("--font-geist-mono")}`;
  ctx.fillText(label.toUpperCase(), 34, 58);
  ctx.fillStyle = ok ? tokens.paper[100] : tokens.signal[300];
  ctx.font = `400 64px ${fontStack("--font-serif")}`;
  ctx.fillText(value, 34, 136);
  ctx.font = `600 40px ${fontStack("--font-geist-sans")}`;
  ctx.fillStyle = ok ? tokens.status.success : tokens.signal[500];
  ctx.fillText(ok ? "✓" : "✕", W - 70, 60);
  if (note) {
    ctx.fillStyle = "rgba(241,237,228,0.55)";
    ctx.font = `400 24px ${fontStack("--font-geist-sans")}`;
    ctx.fillText(note, 34, 178);
  }
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  return tex;
}

const THREAD_POINTS = 48;

/** Acts 1–2: the statute book, then one provision being read into fields. */
export default function StatuteStack({ acts }: { acts: [number, number] }) {
  const { size } = useThree();
  const group = useRef<THREE.Group>(null);
  const plates = useRef<THREE.Mesh[]>([]);
  const tags = useRef<THREE.Mesh[]>([]);
  const threads = useRef<THREE.Line[]>([]);
  const sparks = useRef<THREE.Points>(null);

  const statutes = story.corpus.statutes;
  const focus = useMemo(() => provisionTexture(), []);
  const plateTex = useMemo(
    () => statutes.map((s, i) => plateTexture(s.title, `${s.sections} sections · ${s.chapters} chapters`, i + 3)),
    [statutes]
  );
  const ex = story.focus.extracted;
  const law = story.focus.expert;
  const tagDefs = useMemo(
    () => [
      { anchor: "section", tex: tagTexture("What it changes", "Rebate, s.87A", true) },
      { anchor: "twelve", tex: tagTexture("Income limit", `₹${inr(ex.max_income)}`, ex.max_income === law.max_income) },
      { anchor: "sixty", tex: tagTexture("Maximum rebate", `₹${inr(ex.max_rebate)}`, ex.max_rebate === law.max_rebate) },
      {
        anchor: "missed",
        tex: tagTexture(
          "Marginal relief",
          String(ex.marginal_relief),
          ex.marginal_relief === law.marginal_relief,
          `The law: ${String(law.marginal_relief)}`
        ),
      },
    ],
    [ex, law]
  );

  const threadObjs = useMemo(
    () =>
      tagDefs.map((d) => {
        const broken = d.anchor === "missed" && !(ex.marginal_relief === law.marginal_relief);
        const g = new THREE.BufferGeometry();
        g.setAttribute("position", new THREE.BufferAttribute(new Float32Array(THREAD_POINTS * 3), 3));
        const line = new THREE.Line(
          g,
          new THREE.LineBasicMaterial({
            color: broken ? C.signalHot : C.paper,
            transparent: true,
            opacity: 0,
            toneMapped: false,
            depthWrite: false,
          })
        );
        line.frustumCulled = false;
        return line;
      }),
    [tagDefs, ex, law]
  );
  useEffect(() => {
    threads.current = threadObjs;
  }, [threadObjs]);

  const sparkGeo = useMemo(() => {
    const r = rng(5);
    const n = 70;
    const pos = new Float32Array(n * 3);
    const seed = new Float32Array(n * 3);
    for (let i = 0; i < n * 3; i++) seed[i] = r() - 0.5;
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    g.setAttribute("aSeed", new THREE.BufferAttribute(seed, 3));
    return g;
  }, []);

  useEffect(() => {
    const g = group.current;
    return () => {
      if (g) disposeObject(g);
      focus.tex.dispose();
    };
  }, [focus]);

  const tmp = useMemo(() => new THREE.Vector3(), []);
  const tmp2 = useMemo(() => new THREE.Vector3(), []);

  useFrame(({ clock }) => {
    const [a1, a2] = acts;
    const vis = Math.max(presence(a1), presence(a2));
    if (!group.current) return;
    group.current.visible = vis > 0.001;
    if (!group.current.visible) return;
    const p = progress(a1);
    const q = progress(a2);
    const t = clock.elapsedTime;
    const aspect = size.width / size.height;
    const narrow = aspect < 0.9;
    const N = plates.current.length;
    const fan = smooth(0.08, 0.45, p);
    const lift = smooth(0.5, 0.92, p);
    const aside = smooth(0.02, 0.35, q);

    // Composition: the copy owns the left column on wide screens, so the
    // lifted provision and its fields share the space to its right.
    const camZ = 9 * Math.max(1, 1.55 / aspect);
    const halfH = Math.tan((35 / 2) * (Math.PI / 180)) * (camZ - 1.9);
    const halfW = halfH * aspect;
    const colPx = Math.min(620, size.width * 0.44) + 64;
    const left = narrow ? -halfW : -halfW + (colPx / size.width) * 2 * halfW + 0.25;
    const region = halfW - 0.3 - left;
    const s1 = narrow ? Math.min(0.62, (2 * halfW * 0.86) / PW) : Math.min(0.84, region / (PW + 0.2), (1.7 * halfH) / PH);
    const s2 = narrow ? Math.min(1.2, (halfW * 0.9) / PW) : Math.min(0.66, (region - 0.4) / (PW + 1.9 * 1.05), (1.6 * halfH) / PH);
    const lx = narrow ? 0 : left + region / 2;
    const ly = narrow ? 0.1 : 0.1;
    const ax = narrow ? -halfW * 0.5 - 0.05 : left + (PW * s2) / 2;
    const ay = narrow ? 0.2 : 0.1;
    const st = narrow ? Math.min(2, (halfW * 0.88) / 1.9) : s2 * 1.05;
    const tagX = narrow ? halfW * 0.5 : ax + (PW * s2) / 2 + 0.45 + 0.95 * st;

    plates.current.forEach((m, i) => {
      if (!m) return;
      const isFocus = i === N - 1;
      const k = i - (N - 1) / 2;
      const ang = k * 0.17;
      // stacked → fanned arc
      let x = lerp(0, Math.sin(ang) * 6.2, fan);
      let y = lerp(-i * 0.015, -Math.abs(k) * 0.08, fan);
      let z = lerp(-i * 0.05, -Math.cos(ang) * 2.2 + 0.4, fan);
      let ry = lerp(0, -ang * 0.9, fan);
      let rz = lerp(Math.sin(i * 12.9) * 0.03, 0, fan);
      let sc = 0.82;
      let o = 1;
      if (isFocus) {
        x = lerp(x, lerp(lx, ax, aside), lift);
        y = lerp(y, lerp(ly, ay, aside), lift);
        z = lerp(z, 1.9, lift);
        ry = lerp(ry, narrow ? 0 : lerp(-0.12, 0.14, aside), lift);
        rz = lerp(rz, 0, lift);
        sc = lerp(0.82, lerp(s1, s2, aside), lift);
        y += Math.sin(t * 0.7) * 0.03;
      } else {
        z = lerp(z, -3.6 - Math.abs(k) * 0.3, lift);
        o = lerp(1, 0.3, lift) * (1 - aside * 0.75);
      }
      m.position.set(x, y, z);
      m.rotation.set(0, ry, rz);
      m.scale.setScalar(sc);
      (m.material as THREE.MeshBasicMaterial).opacity = o * vis;
    });

    const fp = plates.current[N - 1];
    // tags and threads (act 2)
    tagDefs.forEach((def, i) => {
      const tag = tags.current[i];
      const line = threads.current[i];
      if (!tag || !line || !fp) return;
      const appear = smooth(0.08 + i * 0.1, 0.24 + i * 0.1, q);
      const gapY = 0.72 * st;
      const ty = ay + (1.5 - i) * gapY;
      tag.position.set(tagX + (1 - appear) * 0.4, ty, 1.6);
      tag.scale.setScalar(st);
      (tag.material as THREE.MeshBasicMaterial).opacity = appear * vis;
      const a = focus.anchors[def.anchor];
      const pos = line.geometry.getAttribute("position") as THREE.BufferAttribute;
      if (a) {
        tmp.set(a.x, a.y, 0.01);
        fp.localToWorld(tmp);
        tmp2.set(tag.position.x - 0.95 * tag.scale.x, tag.position.y, tag.position.z);
        for (let k = 0; k < THREAD_POINTS; k++) {
          const u = k / (THREAD_POINTS - 1);
          const bx = lerp(tmp.x, tmp2.x, u);
          const by = lerp(tmp.y, tmp2.y, u) + Math.sin(u * Math.PI) * 0.25;
          const bz = lerp(tmp.z, tmp2.z, u) + Math.sin(u * Math.PI) * 0.35;
          pos.setXYZ(k, bx, by, bz);
        }
        pos.needsUpdate = true;
      }
      const draw = smooth(0.14 + i * 0.1, 0.4 + i * 0.1, q);
      const broken = def.anchor === "missed" && !(ex.marginal_relief === law.marginal_relief);
      const n = Math.floor(draw * THREAD_POINTS * (broken ? 0.55 : 1));
      line.geometry.setDrawRange(0, n);
      (line.material as THREE.LineBasicMaterial).opacity = vis * (broken ? 1 : 0.55);
      if (broken && sparks.current) {
        const sp = sparks.current.geometry.getAttribute("position") as THREE.BufferAttribute;
        const seed = sparks.current.geometry.getAttribute("aSeed") as THREE.BufferAttribute;
        const end = Math.max(1, n - 1);
        const ex0 = pos.getX(end);
        const ey0 = pos.getY(end);
        const ez0 = pos.getZ(end);
        const burst = smooth(0.62, 0.8, q);
        for (let k = 0; k < sp.count; k++) {
          const ph = (t * 0.5 + seed.getX(k) + 0.5) % 1;
          sp.setXYZ(
            k,
            ex0 + seed.getX(k) * 0.9 * ph * burst + ph * 0.25,
            ey0 + seed.getY(k) * 0.9 * ph * burst - ph * ph * 0.6 * burst,
            ez0 + seed.getZ(k) * 0.6 * ph * burst
          );
        }
        sp.needsUpdate = true;
        (sparks.current.material as THREE.PointsMaterial).opacity = burst * vis;
      }
    });

    if (state.active === a1 || state.active === a2) {
      state.camera.position = [0, 0, camZ];
      state.camera.target = [0, 0, 0];
      state.camera.fov = 35;
    }
  });

  return (
    <group ref={group}>
      {statutes.map((s, i) => (
        <mesh key={s.key} ref={(m) => void (plates.current[i] = m!)} renderOrder={i}>
          <planeGeometry args={[PW, PH]} />
          <meshBasicMaterial map={plateTex[i]} transparent toneMapped={false} side={THREE.DoubleSide} />
        </mesh>
      ))}
      <mesh ref={(m) => void (plates.current[statutes.length] = m!)} renderOrder={50}>
        <planeGeometry args={[PW, PH]} />
        <meshBasicMaterial map={focus.tex} transparent toneMapped={false} side={THREE.DoubleSide} />
      </mesh>
      {tagDefs.map((d, i) => (
        <mesh key={d.anchor} ref={(m) => void (tags.current[i] = m!)} renderOrder={60}>
          <planeGeometry args={[1.9, 0.6]} />
          <meshBasicMaterial map={d.tex} transparent opacity={0} toneMapped={false} />
        </mesh>
      ))}
      {threadObjs.map((o) => (
        <primitive key={o.uuid} object={o} />
      ))}
      <points ref={sparks} geometry={sparkGeo} frustumCulled={false}>
        <pointsMaterial
          color={C.signalHot}
          size={0.045}
          transparent
          opacity={0}
          depthWrite={false}
          toneMapped={false}
          blending={THREE.AdditiveBlending}
        />
      </points>
    </group>
  );
}
