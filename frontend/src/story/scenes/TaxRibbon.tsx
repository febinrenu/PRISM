"use client";

import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { useFrame, useThree } from "@react-three/fiber";
import { tokens } from "@/design/tokens";
import { story } from "../data";
import { lerp, presence, progress, smooth, state } from "../engine/store";
import { C, disposeObject, labelSprite } from "./kit";

const WIDTH = 12;
const HEIGHT = 4.2;
const DEPTH = 0.55;

const ribbonVertex = /* glsl */ `
attribute float aX;
varying float vX;
varying vec2 vUv;
void main() {
  vX = aX;
  vUv = uv;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

const ribbonFragment = /* glsl */ `
uniform vec3 uColor;
uniform float uDraw;
uniform float uOpacity;
uniform float uTicks;
varying float vX;
varying vec2 vUv;
void main() {
  if (vX > uDraw) discard;
  float edge = smoothstep(0.0, 0.06, vUv.y) * smoothstep(1.0, 0.94, vUv.y);
  float tick = 1.0 - smoothstep(0.0, 0.0025, abs(fract(vX * uTicks) - 0.5) - 0.497);
  float rim = smoothstep(0.92, 1.0, vUv.y) + smoothstep(0.08, 0.0, vUv.y);
  float head = smoothstep(uDraw - 0.012, uDraw, vX);
  vec3 col = uColor * (0.34 + 0.22 * rim) + tick * 0.12 + head * 0.6;
  gl_FragColor = vec4(col, (0.55 * edge + 0.35 * rim + tick * 0.2) * uOpacity);
}
`;

/** Act 3: tax on a salary as a ribbon; the misread clause tears it. */
export default function TaxRibbon({ act }: { act: number }) {
  const { size } = useThree();
  const group = useRef<THREE.Group>(null);
  const ribbonMat = useRef<THREE.ShaderMaterial>(null);
  const tearMat = useRef<THREE.MeshBasicMaterial>(null);
  const labels = useRef<THREE.Group>(null);

  const { salary, series, largest_gap } = story.curve;
  const tmax = Math.max(...series.expert, ...series.system, ...series.before);
  const smax = salary[salary.length - 1];
  const X = (s: number) => (s / smax) * WIDTH - WIDTH / 2;
  const Y = (t: number) => (t / tmax) * HEIGHT - HEIGHT / 2 + 0.2;

  const geo = useMemo(() => {
    const n = salary.length;
    const pos = new Float32Array(n * 2 * 3);
    const uv = new Float32Array(n * 2 * 2);
    const ax = new Float32Array(n * 2);
    const idx: number[] = [];
    for (let i = 0; i < n; i++) {
      const x = X(salary[i]);
      const y = Y(series.expert[i]);
      for (let k = 0; k < 2; k++) {
        const j = i * 2 + k;
        pos.set([x, y, k === 0 ? -DEPTH / 2 : DEPTH / 2], j * 3);
        uv.set([i / (n - 1), k], j * 2);
        ax[j] = i / (n - 1);
      }
      if (i < n - 1) {
        const a = i * 2;
        idx.push(a, a + 1, a + 2, a + 1, a + 3, a + 2);
      }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    g.setAttribute("uv", new THREE.BufferAttribute(uv, 2));
    g.setAttribute("aX", new THREE.BufferAttribute(ax, 1));
    g.setIndex(idx);

    const line = (vals: number[], z: number) => {
      const p = new Float32Array(vals.length * 3);
      vals.forEach((v, i) => p.set([X(salary[i]), Y(v), z], i * 3));
      const lg = new THREE.BufferGeometry();
      lg.setAttribute("position", new THREE.BufferAttribute(p, 3));
      return lg;
    };

    // The tear: vertical quads between the law and the misreading.
    const tp: number[] = [];
    const tIdx: number[] = [];
    let v = 0;
    for (let i = 0; i < n - 1; i++) {
      const d0 = series.system[i] - series.expert[i];
      const d1 = series.system[i + 1] - series.expert[i + 1];
      if (d0 <= 0 && d1 <= 0) continue;
      const x0 = X(salary[i]);
      const x1 = X(salary[i + 1]);
      tp.push(x0, Y(series.expert[i]), DEPTH / 2 + 0.01, x0, Y(series.system[i]), DEPTH / 2 + 0.01);
      tp.push(x1, Y(series.expert[i + 1]), DEPTH / 2 + 0.01, x1, Y(series.system[i + 1]), DEPTH / 2 + 0.01);
      tIdx.push(v, v + 1, v + 2, v + 1, v + 3, v + 2);
      v += 4;
    }
    const tg = new THREE.BufferGeometry();
    tg.setAttribute("position", new THREE.Float32BufferAttribute(tp, 3));
    tg.setIndex(tIdx);

    const before = new THREE.Line(
      line(series.before, -DEPTH / 2 - 0.25),
      new THREE.LineDashedMaterial({ color: C.paperDim, dashSize: 0.08, gapSize: 0.08, transparent: true, opacity: 0 })
    );
    before.computeLineDistances();
    before.frustumCulled = false;
    const system = new THREE.Line(
      line(series.system, DEPTH / 2 + 0.02),
      new THREE.LineBasicMaterial({ color: C.signalHot, transparent: true, opacity: 0, toneMapped: false })
    );
    system.frustumCulled = false;
    return { ribbon: g, system, before, tear: tg };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const L = labels.current;
    if (!L) return;
    for (const lakhs of [5, 10, 15, 20, 25]) {
      const s = labelSprite(`₹${lakhs}L`, { height: 0.16, color: tokens.paper[300] });
      s.position.set(X(lakhs * 100000), -HEIGHT / 2 - 0.35, DEPTH / 2);
      L.add(s);
    }
    const tag = labelSprite("salary →", { height: 0.18, color: tokens.paper[400] });
    tag.position.set(WIDTH / 2 + 0.4, -HEIGHT / 2 - 0.35, DEPTH / 2);
    L.add(tag);
    const g = group.current;
    return () => {
      L.children.slice().forEach((c) => {
        disposeObject(c);
        L.remove(c);
      });
      if (g) disposeObject(g);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const uniforms = useMemo(
    () => ({
      uColor: { value: C.paper.clone() },
      uDraw: { value: 0 },
      uOpacity: { value: 1 },
      uTicks: { value: smax / 100000 },
    }),
    [smax]
  );

  const gx = X(largest_gap.salary);
  const gy = (Y(largest_gap.expert) + Y(largest_gap.system)) / 2;

  useFrame(({ clock }) => {
    const vis = presence(act);
    if (!group.current) return;
    group.current.visible = vis > 0.001;
    if (!group.current.visible) return;
    const p = progress(act);
    uniforms.uDraw.value = smooth(0.0, 0.32, p) * 1.001;
    uniforms.uOpacity.value = vis;
    const tear = smooth(0.3, 0.5, p);
    const pulse = 0.75 + 0.25 * Math.sin(clock.elapsedTime * 2.4);
    if (tearMat.current) tearMat.current.opacity = tear * vis * 0.55 * pulse;
    (geo.system.material as THREE.LineBasicMaterial).opacity = tear * vis;
    (geo.before.material as THREE.LineDashedMaterial).opacity = smooth(0.12, 0.3, p) * vis * 0.45;
    const zoomed = smooth(0.42, 0.7, p);
    if (labels.current) labels.current.children.forEach((c) => ((c as THREE.Sprite).material.opacity = vis * 0.9 * (1 - zoomed)));

    if (state.active === act) {
      const aspect = size.width / size.height;
      const fit = Math.max(1, 1.5 / aspect);
      const zoom = smooth(0.42, 0.95, p);
      const orbit = Math.sin(clock.elapsedTime * 0.15) * 0.25;
      const wide = aspect >= 0.9;
      // On wide screens the copy is on the left: keep the tear right of centre.
      const shift = wide ? 1.15 : 0;
      state.camera.position = [
        lerp(wide ? -1.6 : 0.4, gx - shift + 1.4 + orbit, zoom),
        lerp(0.9, gy + 0.9, zoom),
        lerp(13.5 * fit, 5.6 * fit, zoom),
      ];
      state.camera.target = [lerp(wide ? -2.2 : 0, gx - shift, zoom), lerp(0.1, gy, zoom), lerp(0, 0.2, zoom)];
      state.camera.fov = 35;
    }
  });

  return (
    <group ref={group}>
      <mesh geometry={geo.ribbon} frustumCulled={false}>
        <shaderMaterial
          ref={ribbonMat}
          vertexShader={ribbonVertex}
          fragmentShader={ribbonFragment}
          uniforms={uniforms}
          transparent
          side={THREE.DoubleSide}
          depthWrite={false}
        />
      </mesh>
      <primitive object={geo.before} />
      <primitive object={geo.system} />
      <mesh geometry={geo.tear} frustumCulled={false}>
        <meshBasicMaterial
          ref={tearMat}
          color={C.signalHot}
          transparent
          opacity={0}
          side={THREE.DoubleSide}
          toneMapped={false}
          depthWrite={false}
          blending={THREE.AdditiveBlending}
        />
      </mesh>
      <group ref={labels} />
    </group>
  );
}
