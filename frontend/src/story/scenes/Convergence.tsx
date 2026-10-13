"use client";

import { useMemo, useRef } from "react";
import * as THREE from "three";
import { useFrame, useThree } from "@react-three/fiber";
import { particleBudget } from "../engine/tier";
import { presence, progress, smooth, state } from "../engine/store";
import { C, rng } from "./kit";

const vertex = /* glsl */ `
uniform float uTime;
uniform float uGather;
uniform float uSize;
attribute vec3 aFrom;
attribute float aHot;
attribute float aSeed;
varying float vHot;
varying float vA;
void main() {
  float g = clamp((uGather - aSeed * 0.35) / 0.65, 0.0, 1.0);
  g = 1.0 - pow(1.0 - g, 3.0);
  vec3 from = aFrom;
  float a = uTime * 0.08 + aSeed;
  from.xz = mat2(cos(a), -sin(a), sin(a), cos(a)) * from.xz;
  vec3 p = mix(from, position, g);
  p += vec3(sin(uTime * 1.3 + aSeed * 50.0), cos(uTime * 1.1 + aSeed * 31.0), 0.0) * 0.025 * g;
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  gl_Position = projectionMatrix * mv;
  gl_PointSize = uSize * (1.0 + aHot * 0.9) * (10.0 / -mv.z);
  vHot = aHot;
  vA = mix(0.35, 1.0, g);
}
`;

const fragment = /* glsl */ `
uniform vec3 uPaper;
uniform vec3 uHot;
uniform float uOpacity;
varying float vHot;
varying float vA;
void main() {
  float d = length(gl_PointCoord - 0.5);
  float a = smoothstep(0.5, 0.1, d);
  gl_FragColor = vec4(mix(uPaper, uHot, vHot), a * vA * uOpacity);
}
`;

/** Finale: everything gathers into the mark: plain text in, one checkable signal out. */
export default function Convergence({ act }: { act: number }) {
  const { size } = useThree();
  const group = useRef<THREE.Group>(null);

  const geo = useMemo(() => {
    const r = rng(77);
    const n = Math.max(3000, Math.round(particleBudget(state.tier) / 3));
    // The mark (see PrismMark): triangle, incoming ray, faint chord, outgoing signal.
    const S = 0.16;
    const P = (x: number, y: number) => new THREE.Vector2((x - 16) * S, (16 - y) * S);
    const segs: { a: THREE.Vector2; b: THREE.Vector2; w: number; hot: number }[] = [
      { a: P(16, 4.5), b: P(28.5, 26.5), w: 1, hot: 0 },
      { a: P(28.5, 26.5), b: P(3.5, 26.5), w: 1, hot: 0 },
      { a: P(3.5, 26.5), b: P(16, 4.5), w: 1, hot: 0 },
      { a: P(-9, 21.9), b: P(10.4, 16.4), w: 0.8, hot: 0 },
      { a: P(10.4, 16.4), b: P(21.2, 17.6), w: 0.3, hot: 0 },
      { a: P(21.2, 17.6), b: P(42, 27.3), w: 1.1, hot: 1 },
    ];
    const lens = segs.map((s) => s.a.distanceTo(s.b) * s.w);
    const total = lens.reduce((a, b) => a + b, 0);
    const pos = new Float32Array(n * 3);
    const from = new Float32Array(n * 3);
    const hot = new Float32Array(n);
    const seed = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      let pick = r() * total;
      let k = 0;
      while (pick > lens[k] && k < segs.length - 1) pick -= lens[k++];
      const s = segs[k];
      const t = r();
      const jitter = (r() - 0.5) * 0.05;
      pos.set([s.a.x + (s.b.x - s.a.x) * t + jitter, s.a.y + (s.b.y - s.a.y) * t + jitter, (r() - 0.5) * 0.12], i * 3);
      const u = r() * Math.PI * 2;
      const v = Math.acos(2 * r() - 1);
      const rad = 6 + r() * 6;
      from.set([rad * Math.sin(v) * Math.cos(u), rad * Math.cos(v) * 0.7, rad * Math.sin(v) * Math.sin(u)], i * 3);
      hot[i] = s.hot;
      seed[i] = r();
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    g.setAttribute("aFrom", new THREE.BufferAttribute(from, 3));
    g.setAttribute("aHot", new THREE.BufferAttribute(hot, 1));
    g.setAttribute("aSeed", new THREE.BufferAttribute(seed, 1));
    return g;
  }, []);

  const uniforms = useMemo(
    () => ({
      uTime: { value: 0 },
      uGather: { value: 0 },
      uSize: { value: 1 },
      uPaper: { value: C.paper.clone() },
      uHot: { value: C.signalHot.clone() },
      uOpacity: { value: 1 },
    }),
    []
  );

  useFrame((_, dt) => {
    const vis = presence(act);
    if (!group.current) return;
    group.current.visible = vis > 0.001;
    if (!group.current.visible) return;
    const p = progress(act);
    uniforms.uTime.value += dt;
    uniforms.uGather.value = smooth(0.0, 0.55, p) * 1.35;
    uniforms.uSize.value = (size.height / 900) * 2.3;
    uniforms.uOpacity.value = vis;
    if (state.active === act) {
      const aspect = size.width / size.height;
      const fit = Math.max(1, 1.2 / aspect);
      const wide = aspect >= 0.9;
      const sx = wide ? -2.6 : 0.6;
      const sy = wide ? 0.4 : -0.6;
      state.camera.position = [sx, sy + (1 - smooth(0, 0.6, p)) * 2, (wide ? 11 : 10) * fit];
      state.camera.target = [sx, sy + 0.3, 0];
      state.camera.fov = 35;
    }
  });

  return (
    <group ref={group} position={[0, 1.1, 0]}>
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
    </group>
  );
}
