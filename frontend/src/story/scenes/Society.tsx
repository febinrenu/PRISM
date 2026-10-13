"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { useFrame, useThree } from "@react-three/fiber";
import { tokens } from "@/design/tokens";
import { fetchStory, story, type Population } from "../data";
import { particleBudget } from "../engine/tier";
import { lerp, presence, progress, smooth, state } from "../engine/store";
import { C, disposeObject, labelSprite, rng } from "./kit";

const XW = 11;
// Log-income axis spanning where the returns actually are (about the 1st to
// the 99.5th percentile); the long top tail is pinned to the right edge.
let LO = Math.log10(250000);
let HI = Math.log10(5000000);
const xOf = (income: number) => Math.min(XW / 2 + 0.6, ((Math.log10(Math.max(income, 10 ** LO)) - LO) / (HI - LO)) * XW - XW / 2);
function setAxis(rows: Population["rows"]) {
  const total = rows.reduce((s, r) => s + r[1], 0);
  let cum = 0;
  let lo = rows[0][0];
  let hi = rows[rows.length - 1][0];
  for (const r of rows) {
    cum += r[1];
    if (cum / total < 0.002) lo = r[0];
    if (cum / total < 0.995) hi = r[0];
  }
  LO = Math.log10(Math.max(lo, 100000));
  HI = Math.log10(Math.max(hi, lo * 4));
}

const vertex = /* glsl */ `
uniform float uTime;
uniform float uSettle;
uniform float uGain;
uniform float uDiff;
uniform float uSize;
uniform vec3 uBase;
uniform vec3 uGainColor;
uniform vec3 uDiffColor;
attribute vec3 aCloud;
attribute vec3 aDune;
attribute float aGain;
attribute float aDiff;
attribute float aSeed;
varying vec3 vColor;
varying float vA;
void main() {
  vec3 cloud = aCloud;
  float a = uTime * 0.12 + aSeed * 0.4;
  cloud.xz = mat2(cos(a), -sin(a), sin(a), cos(a)) * cloud.xz;
  cloud.y += sin(uTime * 0.6 + aSeed * 30.0) * 0.08;
  float st = clamp((uSettle - aSeed * 0.35) / 0.65, 0.0, 1.0);
  st = st * st * (3.0 - 2.0 * st);
  vec3 p = mix(cloud, aDune, st);
  float lift = aDiff * uDiff;
  p.y += lift * (0.35 + 0.08 * sin(uTime * 2.0 + aSeed * 20.0));
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  gl_Position = projectionMatrix * mv;
  gl_PointSize = uSize * (1.0 + lift * 1.1) * (10.0 / -mv.z);
  vec3 col = mix(uBase, uGainColor, aGain * uGain);
  vColor = mix(col, uDiffColor, lift);
  vA = 0.55 + 0.45 * lift;
}
`;

const fragment = /* glsl */ `
uniform float uOpacity;
varying vec3 vColor;
varying float vA;
void main() {
  float d = length(gl_PointCoord - 0.5);
  float a = smoothstep(0.5, 0.15, d);
  gl_FragColor = vec4(vColor, a * vA * uOpacity);
}
`;

/** Act 4: the simulated population settling into its income distribution. */
export default function Society({ act }: { act: number }) {
  const { size } = useThree();
  const group = useRef<THREE.Group>(null);
  const decor = useRef<THREE.Group>(null);
  const [pop, setPop] = useState<Population | null>(null);

  useEffect(() => {
    let live = true;
    fetchStory<Population>("population").then((p) => live && setPop(p)).catch(() => {});
    return () => {
      live = false;
    };
  }, []);

  const geo = useMemo(() => {
    if (!pop) return null;
    setAxis(pop.rows);
    const r = rng(42);
    const budget = particleBudget(state.tier);
    const total = pop.rows.reduce((s, x) => s + x[1], 0);
    const reps: number[] = [];
    pop.rows.forEach((row, i) => {
      const exact = (row[1] / total) * budget;
      let k = Math.floor(exact);
      if (r() < exact - k) k++;
      for (let j = 0; j < k; j++) reps.push(i);
    });
    const n = reps.length;
    const BINS = 150;
    const counts = new Int32Array(BINS);
    const bin = (x: number) => Math.min(BINS - 1, Math.max(0, Math.floor(((x + XW / 2) / XW) * BINS)));
    reps.forEach((i) => counts[bin(xOf(pop.rows[i][0]))]++);
    const maxC = Math.max(...Array.from(counts));
    const dy = 3.6 / maxC;
    const fill = new Int32Array(BINS);
    const cloud = new Float32Array(n * 3);
    const dune = new Float32Array(n * 3);
    const gain = new Float32Array(n);
    const diff = new Float32Array(n);
    const seed = new Float32Array(n);
    reps.forEach((i, k) => {
      const [income, , , before, expert, sys] = pop.rows[i];
      const u = r() * Math.PI * 2;
      const v = Math.acos(2 * r() - 1);
      const rad = 4.2 * Math.cbrt(r());
      cloud.set([rad * Math.sin(v) * Math.cos(u), rad * Math.cos(v) * 0.6, rad * Math.sin(v) * Math.sin(u)], k * 3);
      const x = xOf(income);
      const b = bin(x);
      const h = fill[b]++;
      dune.set([x + (r() - 0.5) * (XW / BINS) * 1.6, -2.3 + h * dy + r() * dy * 0.5, (r() - 0.5) * 1.6], k * 3);
      gain[k] = expert < before - 1 ? 1 : 0;
      diff[k] = Math.abs(sys - expert) > 10 ? 1 : 0;
      seed[k] = r();
    });
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(dune, 3));
    g.setAttribute("aCloud", new THREE.BufferAttribute(cloud, 3));
    g.setAttribute("aDune", new THREE.BufferAttribute(dune, 3));
    g.setAttribute("aGain", new THREE.BufferAttribute(gain, 1));
    g.setAttribute("aDiff", new THREE.BufferAttribute(diff, 1));
    g.setAttribute("aSeed", new THREE.BufferAttribute(seed, 1));
    g.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 12);
    return g;
  }, [pop]);

  // Decile boundaries and labels from the snapshot.
  useEffect(() => {
    const D = decor.current;
    if (!D || !pop) return;
    const ds = story.deciles.deciles;
    const lines: number[] = [];
    let prev = -XW / 2;
    ds.forEach((d, i) => {
      const x = i < ds.length - 1 ? xOf(d.income_upper) : XW / 2;
      if (i < ds.length - 1) lines.push(x, -2.4, 0.9, x, 2.4, 0.9);
      const lab = labelSprite(`D${d.decile}`, { height: 0.17, color: tokens.paper[400] });
      lab.position.set((prev + x) / 2, -2.75, 0.9);
      D.add(lab);
      prev = x;
    });
    const lg = new THREE.BufferGeometry();
    lg.setAttribute("position", new THREE.Float32BufferAttribute(lines, 3));
    const ls = new THREE.LineSegments(
      lg,
      new THREE.LineBasicMaterial({ color: C.paper, transparent: true, opacity: 0, depthWrite: false })
    );
    ls.name = "deciles";
    D.add(ls);
    for (const [label, inc] of [
      ["₹5L", 500000],
      ["₹10L", 1000000],
      ["₹25L", 2500000],
    ] as const) {
      const s = labelSprite(label, { height: 0.16, color: tokens.paper[300] });
      s.position.set(xOf(inc), -3.1, 0.9);
      D.add(s);
    }
    return () => {
      D.children.slice().forEach((c) => {
        disposeObject(c);
        D.remove(c);
      });
    };
  }, [pop]);

  useEffect(() => () => geo?.dispose(), [geo]);

  const uniforms = useMemo(
    () => ({
      uTime: { value: 0 },
      uSettle: { value: 0 },
      uGain: { value: 0 },
      uDiff: { value: 0 },
      uSize: { value: 1 },
      uOpacity: { value: 1 },
      uBase: { value: C.paperDim.clone().multiplyScalar(0.8) },
      uGainColor: { value: new THREE.Color(tokens.hue.blue.text) },
      uDiffColor: { value: C.signalHot.clone() },
    }),
    []
  );

  useFrame((_, dt) => {
    const vis = presence(act);
    if (!group.current) return;
    group.current.visible = vis > 0.001;
    if (!group.current.visible) return;
    const p = progress(act);
    const u = uniforms;
    u.uTime.value += dt;
    u.uSettle.value = smooth(0.12, 0.42, p) * 1.35;
    u.uGain.value = smooth(0.46, 0.6, p);
    u.uDiff.value = smooth(0.68, 0.82, p);
    u.uOpacity.value = vis;
    u.uSize.value = (size.height / 900) * (state.tier >= 3 ? 3.2 : state.tier === 2 ? 4 : 5);
    if (decor.current) {
      const dec = smooth(0.42, 0.55, p) * vis;
      decor.current.children.forEach((c) => {
        const m = (c as THREE.Mesh).material as THREE.Material & { opacity: number };
        m.opacity = c.name === "deciles" ? dec * 0.22 : dec * 0.85;
      });
    }
    if (state.active === act) {
      const aspect = size.width / size.height;
      const fit = Math.max(1, 1.45 / aspect);
      const settle = smooth(0.12, 0.45, p);
      // Wide screens: the copy is on the left, so look a little left of the dune.
      const sx = aspect >= 0.9 ? -3.2 : 0;
      state.camera.position = [lerp(2.5, sx + 0.4, settle), lerp(2.6, 0.6, settle), lerp(13.5, 11.5, settle) * fit];
      state.camera.target = [sx * settle, lerp(0, 0.2, settle), 0];
      state.camera.fov = 35;
    }
  });

  return (
    <group ref={group}>
      {geo && (
        <points geometry={geo} frustumCulled={false}>
          <shaderMaterial
            vertexShader={vertex}
            fragmentShader={fragment}
            uniforms={uniforms}
            transparent
            depthWrite={false}
            toneMapped={false}
          />
        </points>
      )}
      <group ref={decor} />
    </group>
  );
}
