"use client";

import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { useFrame, useThree } from "@react-three/fiber";
import { tokens } from "@/design/tokens";
import { reformLabel, story } from "../data";
import { clamp, presence, progress, smooth, state } from "../engine/store";
import { C, disposeObject, labelSprite } from "./kit";

const CW = 1.18;
const RH = 0.6;
const TW = 1.04;
const TH = 0.46;

const vertex = /* glsl */ `
attribute vec3 aBack;
attribute float aKind;
attribute float aErr;
varying vec2 vUv;
varying vec3 vBack;
varying float vKind;
varying float vErr;
void main() {
  vUv = uv;
  vBack = aBack;
  vKind = aKind;
  vErr = aErr;
  gl_Position = projectionMatrix * modelViewMatrix * instanceMatrix * vec4(position, 1.0);
}
`;

const fragment = /* glsl */ `
uniform float uOpacity;
uniform vec3 uFront;
uniform vec3 uHot;
uniform float uTime;
varying vec2 vUv;
varying vec3 vBack;
varying float vKind;
varying float vErr;
void main() {
  float ex = min(vUv.x, 1.0 - vUv.x) * ${(TW / TH).toFixed(3)};
  float ey = min(vUv.y, 1.0 - vUv.y);
  float border = 1.0 - smoothstep(0.0, 0.05, min(ex, ey));
  vec3 col;
  if (gl_FrontFacing) {
    col = uFront + border * 0.1;
  } else {
    col = vBack;
    if (vKind > 0.5) {
      float h = step(0.55, fract((vUv.x * ${(TW / TH).toFixed(3)} + vUv.y) * 6.0));
      col = mix(vBack, vBack * 1.9, h * 0.6);
    }
    float pulse = 0.75 + 0.25 * sin(uTime * 3.0);
    col = mix(col, uHot * pulse, clamp(border * 2.0, 0.0, 1.0) * vErr);
  }
  gl_FragColor = vec4(col, uOpacity);
}
`;

/** Act 5: ten reforms × six readers. Each tile turns over to its verdict. */
export default function VerdictBoard({ act }: { act: number }) {
  const { size } = useThree();
  const group = useRef<THREE.Group>(null);
  const mesh = useRef<THREE.InstancedMesh>(null);
  const labels = useRef<THREE.Group>(null);
  const { reforms, systems, cells } = story.matrix;
  const R = reforms.length;
  const S = systems.length;
  const maxErr = Math.max(1, ...cells.map((c) => c.revenue_error_crore ?? 0));

  const geo = useMemo(() => {
    const g = new THREE.PlaneGeometry(TW, TH);
    const back = new Float32Array(R * S * 3);
    const kind = new Float32Array(R * S);
    const err = new Float32Array(R * S);
    reforms.forEach((rf, r) => {
      systems.forEach((sy, s) => {
        const i = r * S + s;
        const c = cells.find((x) => x.set === rf.id && x.system === sy.id);
        const assembled = c?.status === "assembled";
        const flipped = (c?.flips ?? 0) > 0;
        const col = flipped ? C.signalHot : assembled ? C.paper.clone().multiplyScalar(0.86) : C.graphite.clone().multiplyScalar(0.9);
        back.set([col.r, col.g, col.b], i * 3);
        kind[i] = assembled ? 0 : 1;
        err[i] = assembled ? Math.min(1, Math.sqrt((c?.revenue_error_crore ?? 0) / maxErr)) : 0;
      });
    });
    g.setAttribute("aBack", new THREE.InstancedBufferAttribute(back, 3));
    g.setAttribute("aKind", new THREE.InstancedBufferAttribute(kind, 1));
    g.setAttribute("aErr", new THREE.InstancedBufferAttribute(err, 1));
    return g;
  }, [R, S, reforms, systems, cells, maxErr]);

  useEffect(() => {
    const L = labels.current;
    if (!L) return;
    systems.forEach((sy, s) => {
      const l = labelSprite(sy.label, { height: 0.17, color: tokens.paper[200], font: "sans" });
      l.position.set((s - (S - 1) / 2) * CW, (R / 2) * RH + 0.28, 0);
      L.add(l);
    });
    reforms.forEach((rf, r) => {
      const l = labelSprite(reformLabel(rf.id), { height: 0.15, color: tokens.paper[300], font: "sans" });
      l.center.set(1, 0.5);
      l.position.set(-(S / 2) * CW - 0.1, ((R - 1) / 2 - r) * RH, 0);
      L.add(l);
    });
    const g = group.current;
    return () => {
      L.children.slice().forEach((c) => {
        disposeObject(c);
        L.remove(c);
      });
      if (g) disposeObject(g);
    };
  }, [R, S, reforms, systems]);

  const uniforms = useMemo(
    () => ({
      uOpacity: { value: 1 },
      uFront: { value: new THREE.Color(tokens.ink[750]) },
      uHot: { value: C.signalHot.clone() },
      uTime: { value: 0 },
    }),
    []
  );
  const m4 = useMemo(() => new THREE.Matrix4(), []);
  const q = useMemo(() => new THREE.Quaternion(), []);
  const e = useMemo(() => new THREE.Euler(), []);
  const v = useMemo(() => new THREE.Vector3(), []);
  const one = useMemo(() => new THREE.Vector3(1, 1, 1), []);

  useFrame(({ clock }) => {
    const vis = presence(act);
    if (!group.current || !mesh.current) return;
    group.current.visible = vis > 0.001;
    if (!group.current.visible) return;
    const p = progress(act);
    uniforms.uOpacity.value = vis;
    uniforms.uTime.value = clock.elapsedTime;
    for (let r = 0; r < R; r++) {
      for (let s = 0; s < S; s++) {
        const i = r * S + s;
        // Flip column by column, row by row, as the reader scrolls.
        const start = 0.1 + (s * R + r) * (0.55 / (R * S));
        const f = clamp((p - start) / 0.09);
        const ease = f * f * (3 - 2 * f);
        e.set(ease * Math.PI, 0, 0);
        q.setFromEuler(e);
        v.set((s - (S - 1) / 2) * CW, ((R - 1) / 2 - r) * RH, Math.sin(ease * Math.PI) * 0.35);
        m4.compose(v, q, one);
        mesh.current.setMatrixAt(i, m4);
      }
    }
    mesh.current.instanceMatrix.needsUpdate = true;
    if (labels.current) labels.current.children.forEach((c) => ((c as THREE.Sprite).material.opacity = vis));
    if (state.active === act) {
      const aspect = size.width / size.height;
      const wide = aspect >= 0.9;
      const drift = smooth(0, 1, p);
      // Wide: the board sits left of the copy. Narrow: it fills the width above it.
      const z = wide ? Math.max(16.5, 26 / aspect) : 14.5 / Math.max(0.45, aspect);
      // Keep the board (row labels included) inside the left ~58% of the frame.
      const sx = wide ? -6.6 + z * Math.tan((19 * Math.PI) / 180) * aspect : 0;
      state.camera.position = [sx + Math.sin(clock.elapsedTime * 0.1) * 0.5, 0.6 - drift * 0.4, z - drift * 0.8];
      state.camera.target = [sx, 0.1, 0];
      state.camera.fov = 38;
    }
  });

  return (
    <group ref={group} rotation={[-0.12, 0, 0]}>
      <instancedMesh ref={mesh} args={[geo, undefined, R * S]} frustumCulled={false}>
        <shaderMaterial
          vertexShader={vertex}
          fragmentShader={fragment}
          uniforms={uniforms}
          side={THREE.DoubleSide}
          transparent
          toneMapped={false}
        />
      </instancedMesh>
      <group ref={labels} />
    </group>
  );
}
