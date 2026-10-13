"use client";

import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { useFrame, useThree } from "@react-three/fiber";
import { tokens } from "@/design/tokens";
import { ERROR_LABEL, story } from "../data";
import { clamp, lerp, presence, progress, smooth, state } from "../engine/store";
import { C, disposeObject, labelSprite } from "./kit";

const COL = 0.78;
const ROW = 0.3;
const MAXH = 3.4;

/** Act 6: every injected error as a column; height and heat = how often it flipped a conclusion. */
export default function FaultField({ act }: { act: number }) {
  const { size } = useThree();
  const group = useRef<THREE.Group>(null);
  const mesh = useRef<THREE.InstancedMesh>(null);
  const labels = useRef<THREE.Group>(null);
  const grid = useRef<THREE.GridHelper>(null);
  const kinds = story.injection.kinds;

  const layout = useMemo(() => {
    const items: { x: number; z: number; h: number; flip: number; col: number }[] = [];
    kinds.forEach((k, ci) => {
      const rows = story.injection.rows.filter((r) => r.error === k.error);
      rows.sort((a, b) => b.flip_rate - a.flip_rate);
      rows.forEach((r, ri) => {
        items.push({
          x: (ci - (kinds.length - 1) / 2) * COL,
          z: -ri * ROW,
          h: 0.04 + r.flip_rate * MAXH,
          flip: r.flip_rate,
          col: ci,
        });
      });
    });
    return items;
  }, [kinds]);

  const geo = useMemo(() => {
    const g = new THREE.BoxGeometry(0.2, 1, 0.2);
    g.translate(0, 0.5, 0);
    return g;
  }, []);
  const mat = useMemo(
    () => new THREE.MeshBasicMaterial({ transparent: true, toneMapped: false, vertexColors: false }),
    []
  );

  useEffect(() => {
    const m = mesh.current;
    if (!m) return;
    const c = new THREE.Color();
    layout.forEach((it, i) => {
      if (it.flip > 0) c.copy(C.graphite).lerp(C.signalHot, 0.25 + 0.75 * Math.min(1, it.flip / 0.65));
      else c.copy(C.paperDim).multiplyScalar(0.42);
      m.setColorAt(i, c);
    });
    if (m.instanceColor) m.instanceColor.needsUpdate = true;
  }, [layout]);

  useEffect(() => {
    const L = labels.current;
    if (!L) return;
    kinds.forEach((k, ci) => {
      const l = labelSprite(ERROR_LABEL[k.error] ?? k.error, {
        height: 0.13,
        color: k.max_flip_rate > 0 ? tokens.paper[200] : tokens.paper[400],
        font: "sans",
      });
      l.center.set(1, 0.5);
      l.material.rotation = Math.PI / 4;
      l.position.set((ci - (kinds.length - 1) / 2) * COL + 0.1, -0.15, 0.45);
      L.add(l);
    });
    return () => {
      L.children.slice().forEach((c) => {
        disposeObject(c);
        L.remove(c);
      });
    };
  }, [kinds]);

  useEffect(() => () => {
    geo.dispose();
    mat.dispose();
  }, [geo, mat]);

  const m4 = useMemo(() => new THREE.Matrix4(), []);
  const pos = useMemo(() => new THREE.Vector3(), []);
  const scl = useMemo(() => new THREE.Vector3(), []);
  const quat = useMemo(() => new THREE.Quaternion(), []);

  useFrame(({ clock }) => {
    const vis = presence(act);
    if (!group.current || !mesh.current) return;
    group.current.visible = vis > 0.001;
    if (!group.current.visible) return;
    const p = progress(act);
    mat.opacity = vis;
    if (grid.current) {
      const gm = grid.current.material as THREE.Material;
      gm.transparent = true;
      gm.opacity = vis * 0.5;
    }
    const t = clock.elapsedTime;
    layout.forEach((it, i) => {
      const start = 0.12 + (it.col / kinds.length) * 0.45;
      const g = clamp((p - start) / 0.16);
      const e = 1 - Math.pow(1 - g, 3);
      const flicker = it.flip > 0 ? 1 + 0.03 * Math.sin(t * 4 + i) : 1;
      pos.set(it.x, 0, it.z);
      scl.set(1, Math.max(0.001, it.h * e * flicker), 1);
      m4.compose(pos, quat, scl);
      mesh.current!.setMatrixAt(i, m4);
    });
    mesh.current.instanceMatrix.needsUpdate = true;
    if (labels.current) labels.current.children.forEach((c) => ((c as THREE.Sprite).material.opacity = vis * smooth(0.1, 0.3, p)));
    if (state.active === act) {
      const aspect = size.width / size.height;
      const fit = Math.max(1, 1.4 / aspect);
      const a = lerp(-0.5, 0.35, smooth(0, 1, p)) + Math.sin(t * 0.12) * 0.06;
      const r = 10.5 * fit;
      const sx = aspect >= 0.9 ? -3.6 : 0;
      state.camera.position = [sx + Math.sin(a) * r, 4.6, Math.cos(a) * r - 1.5];
      state.camera.target = [sx, 0.9, -1.6];
      state.camera.fov = 36;
    }
  });

  return (
    <group ref={group}>
      <instancedMesh ref={mesh} args={[geo, mat, layout.length]} frustumCulled={false} />
      <gridHelper ref={grid} args={[12, 24, tokens.ink[600], tokens.ink[700]]} position={[0, 0, -2.6]} />
      <group ref={labels} />
    </group>
  );
}
