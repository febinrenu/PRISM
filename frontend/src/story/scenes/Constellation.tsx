"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { useFrame, useThree } from "@react-three/fiber";
import { tokens } from "@/design/tokens";
import { fetchStory, type Constellation as ConstellationData } from "../data";
import { lerp, presence, progress, smooth, state } from "../engine/store";
import { C, disposeObject, labelSprite } from "./kit";

const RING = 6.2;
const GOLDEN = 2.39996;

const vertex = /* glsl */ `
uniform float uSize;
uniform float uTime;
uniform float uThread;
attribute float aSize;
attribute float aThread;
attribute float aSeed;
varying float vThread;
varying float vA;
void main() {
  vec3 p = position;
  p.y += sin(uTime * 0.4 + aSeed * 40.0) * 0.03;
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  gl_Position = projectionMatrix * mv;
  float t = aThread * uThread;
  gl_PointSize = uSize * aSize * (1.0 + t * 0.8) * (10.0 / -mv.z);
  vThread = t;
  vA = smoothstep(40.0, 3.0, -mv.z);
}
`;

const fragment = /* glsl */ `
uniform vec3 uPaper;
uniform vec3 uHot;
uniform float uOpacity;
varying float vThread;
varying float vA;
void main() {
  float d = length(gl_PointCoord - 0.5);
  float a = smoothstep(0.5, 0.1, d);
  vec3 col = mix(uPaper, uHot, vThread);
  gl_FragColor = vec4(col, a * vA * uOpacity * mix(0.75, 1.0, vThread));
}
`;

/** Act 7: the 2025 Act as a constellation; the camera follows the rebate's thread. */
export default function Constellation({ act }: { act: number }) {
  const { size } = useThree();
  const group = useRef<THREE.Group>(null);
  const labels = useRef<THREE.Group>(null);
  const [data, setData] = useState<ConstellationData | null>(null);

  useEffect(() => {
    let live = true;
    fetchStory<ConstellationData>("constellation").then((d) => live && setData(d)).catch(() => {});
    return () => {
      live = false;
    };
  }, []);

  const built = useMemo(() => {
    if (!data) return null;
    const N = data.nodes.length;
    const pos = new Float32Array(N * 3);
    const sz = new Float32Array(N);
    const th = new Float32Array(N);
    const seed = new Float32Array(N);
    const chapters = data.nodes.map((n, i) => (n.k === "chapter" ? i : -1)).filter((i) => i >= 0);
    const outer = data.nodes.map((n, i) => ((n.k === "schedule" || n.k === "part") && n.p < 0 ? i : -1)).filter((i) => i >= 0);
    const childCount = new Map<number, number>();
    const thread = new Set<number>(data.thread);
    // A node is on the thread if it is a thread section or descends from one.
    data.nodes.forEach((n, i) => {
      if (n.p >= 0 && thread.has(n.p)) thread.add(i);
    });

    data.nodes.forEach((n, i) => {
      seed[i] = ((i * 2654435761) % 1000) / 1000;
      th[i] = thread.has(i) ? 1 : 0;
      const ci = chapters.indexOf(i);
      const oi = outer.indexOf(i);
      if (ci >= 0) {
        const a = (ci / chapters.length) * Math.PI * 2;
        pos.set([Math.cos(a) * RING, 0, Math.sin(a) * RING], i * 3);
        sz[i] = 9;
        return;
      }
      if (oi >= 0) {
        const a = (oi / Math.max(1, outer.length)) * Math.PI * 2 + 0.1;
        pos.set([Math.cos(a) * RING * 1.45, -0.8, Math.sin(a) * RING * 1.45], i * 3);
        sz[i] = 6;
        return;
      }
      const k = childCount.get(n.p) ?? 0;
      childCount.set(n.p, k + 1);
      const isSection = n.k === "section";
      sz[i] = isSection ? 3.6 : 2.2;
      if (n.p < 0) {
        // Sections before the first recovered chapter sit at the centre.
        const r = 0.25 * Math.sqrt(k + 1);
        pos.set([Math.cos(k * GOLDEN) * r, Math.sin(k * 1.3) * 0.3, Math.sin(k * GOLDEN) * r], i * 3);
        return;
      }
      const px = pos[n.p * 3];
      const py = pos[n.p * 3 + 1];
      const pz = pos[n.p * 3 + 2];
      const out = new THREE.Vector3(px, 0, pz).normalize();
      if (out.lengthSq() < 0.5) out.set(1, 0, 0);
      const side = new THREE.Vector3(-out.z, 0, out.x);
      const r = (isSection ? 0.2 : 0.07) * Math.sqrt(k + 1);
      const ang = k * GOLDEN;
      const lift = isSection ? 0.55 : 0.25;
      pos.set(
        [
          px + out.x * (0.35 + r * 0.6) + side.x * Math.cos(ang) * r,
          py + Math.sin(ang) * r * lift,
          pz + out.z * (0.35 + r * 0.6) + side.z * Math.cos(ang) * r,
        ],
        i * 3
      );
    });

    const lines: number[] = [];
    const hot: number[] = [];
    data.nodes.forEach((n, i) => {
      if (n.p < 0) return;
      const seg = [pos[n.p * 3], pos[n.p * 3 + 1], pos[n.p * 3 + 2], pos[i * 3], pos[i * 3 + 1], pos[i * 3 + 2]];
      (thread.has(i) ? hot : lines).push(...seg);
    });
    const pg = new THREE.BufferGeometry();
    pg.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    pg.setAttribute("aSize", new THREE.BufferAttribute(sz, 1));
    pg.setAttribute("aThread", new THREE.BufferAttribute(th, 1));
    pg.setAttribute("aSeed", new THREE.BufferAttribute(seed, 1));
    const lg = new THREE.BufferGeometry();
    lg.setAttribute("position", new THREE.Float32BufferAttribute(lines, 3));
    const hg = new THREE.BufferGeometry();
    hg.setAttribute("position", new THREE.Float32BufferAttribute(hot, 3));
    const focus = data.thread[0];
    return {
      points: pg,
      lines: new THREE.LineSegments(lg, new THREE.LineBasicMaterial({ color: C.paper, transparent: true, opacity: 0, depthWrite: false })),
      hot: new THREE.LineSegments(
        hg,
        new THREE.LineBasicMaterial({ color: C.signalHot, transparent: true, opacity: 0, depthWrite: false, toneMapped: false })
      ),
      focus: new THREE.Vector3(pos[focus * 3], pos[focus * 3 + 1], pos[focus * 3 + 2]),
      chapters: chapters.map((i) => ({ i, label: data.nodes[i].l, at: new THREE.Vector3(pos[i * 3], pos[i * 3 + 1], pos[i * 3 + 2]) })),
      threadSections: data.thread.map((i) => ({
        label: `s.${data.nodes[i].l} · ${data.nodes[i].h.split(" ").slice(0, 3).join(" ")}`,
        at: new THREE.Vector3(pos[i * 3], pos[i * 3 + 1], pos[i * 3 + 2]),
      })),
    };
  }, [data]);

  useEffect(() => {
    const L = labels.current;
    if (!L || !built) return;
    built.chapters.forEach((c) => {
      const s = labelSprite(`Ch. ${c.label}`, { height: 0.2, color: tokens.paper[300] });
      s.position.copy(c.at).add(new THREE.Vector3(0, 0.38, 0));
      L.add(s);
    });
    built.threadSections.forEach((t) => {
      const s = labelSprite(t.label, {
        height: 0.075,
        color: tokens.signal[300],
        font: "sans",
      });
      s.center.set(0, 0.5);
      s.position.copy(t.at).add(new THREE.Vector3(0.12, 0.12, 0));
      s.name = "thread";
      L.add(s);
    });
    return () => {
      L.children.slice().forEach((c) => {
        disposeObject(c);
        L.remove(c);
      });
    };
  }, [built]);

  useEffect(
    () => () => {
      if (!built) return;
      built.points.dispose();
      disposeObject(built.lines);
      disposeObject(built.hot);
    },
    [built]
  );

  const uniforms = useMemo(
    () => ({
      uSize: { value: 1 },
      uTime: { value: 0 },
      uThread: { value: 0 },
      uPaper: { value: C.paper.clone() },
      uHot: { value: C.signalHot.clone() },
      uOpacity: { value: 1 },
    }),
    []
  );

  useFrame((_, dt) => {
    const vis = presence(act);
    if (!group.current) return;
    group.current.visible = vis > 0.001 && !!built;
    if (!group.current.visible || !built) return;
    const p = progress(act);
    const u = uniforms;
    u.uTime.value += dt;
    u.uSize.value = (size.height / 900) * 2.4;
    u.uOpacity.value = vis;
    const thread = smooth(0.35, 0.55, p);
    u.uThread.value = thread;
    (built.lines.material as THREE.LineBasicMaterial).opacity = vis * 0.13;
    (built.hot.material as THREE.LineBasicMaterial).opacity = vis * thread;
    group.current.rotation.y = lerp(0.6, 0, smooth(0, 0.5, p)) + u.uTime.value * 0.01 * (1 - thread);
    labels.current?.children.forEach((c) => {
      const sp = c as THREE.Sprite;
      sp.material.opacity = vis * (c.name === "thread" ? thread : 0.85 * (1 - smooth(0.5, 0.7, p)));
    });
    if (state.active === act) {
      const aspect = size.width / size.height;
      const fit = Math.max(1, 1.3 / aspect);
      const fly = smooth(0.45, 0.92, p);
      const f = built.focus.clone().applyEuler(group.current.rotation);
      const out = f.clone().setY(0).normalize();
      const wide = aspect >= 0.9;
      // Seen from outside the ring, slightly above; on wide screens the
      // target sits to the left of the node so it lands right of the copy.
      const side = new THREE.Vector3(-out.z, 0, out.x);
      const pos = f.clone().addScaledVector(out, 2.9).add(new THREE.Vector3(0, 1.2, 0));
      const tgt = f.clone().addScaledVector(side, wide ? 0.9 : 0);
      const ox = wide ? -3.2 : 0;
      state.camera.position = [lerp(ox, pos.x, fly), lerp(11.5, pos.y, fly), lerp(12 * fit, pos.z, fly)];
      state.camera.target = [lerp(ox, tgt.x, fly), lerp(-0.6, tgt.y, fly), lerp(0, tgt.z, fly)];
      state.camera.fov = lerp(42, 40, fly);
    }
  });

  return (
    <group ref={group}>
      {built && (
        <>
          <primitive object={built.lines} />
          <primitive object={built.hot} />
          <points geometry={built.points} frustumCulled={false}>
            <shaderMaterial
              vertexShader={vertex}
              fragmentShader={fragment}
              uniforms={uniforms}
              transparent
              depthWrite={false}
              toneMapped={false}
            />
          </points>
        </>
      )}
      <group ref={labels} />
    </group>
  );
}
