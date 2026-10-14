import * as THREE from "three";
import type { FormId } from "../engine/config";
import { HOLDS } from "../engine/config";

type V = [number, number, number];
interface Pose {
  p: V;
  t: V;
  fov: number;
}

/** Where the camera sits while each form holds: entering pose, leaving pose. */
const POSES: Record<FormId, [Pose, Pose]> = {
  flow: [
    { p: [0, 0.2, 12.5], t: [0, 0, 0], fov: 34 },
    { p: [0.9, 0.55, 10.2], t: [0.7, 0, 0], fov: 34 },
  ],
  skyline: [
    { p: [0, 1.6, 17.5], t: [0, 0.8, 0], fov: 36 },
    { p: [-2.4, 4.2, 15.2], t: [0, 1.6, 0], fov: 34 },
  ],
  page: [
    { p: [0.5, 0.6, 9.4], t: [0, 0.2, 2], fov: 34 },
    { p: [-0.3, 0.3, 8.6], t: [0, 0.15, 2], fov: 34 },
  ],
  tree: [
    { p: [0, 8.5, 16.5], t: [0, -0.6, 0], fov: 38 },
    { p: [5.5, 6.2, 14.5], t: [0, -0.8, 0], fov: 38 },
  ],
  entities: [
    { p: [0, 0.6, 9.8], t: [0, 0.7, 0.4], fov: 36 },
    { p: [-0.5, 0.4, 9.1], t: [-0.1, 0.6, 0.4], fov: 36 },
  ],
  threads: [
    { p: [1.8, 1.2, 9.8], t: [0, 0.5, 0.6], fov: 36 },
    { p: [-1.2, 0.9, 9.2], t: [0, 0.5, 0.6], fov: 36 },
  ],
  graph: [
    { p: [0, 2.2, 19.5], t: [0, 0, 0], fov: 38 },
    { p: [10.5, 3.4, 15.5], t: [0, -0.3, 0], fov: 38 },
  ],
  population: [
    { p: [0, 0.9, 13.5], t: [0, 0.2, 0], fov: 36 },
    { p: [-2.4, 0.7, 12.6], t: [0, 0.1, 0], fov: 36 },
  ],
  curve: [
    { p: [0, 0.5, 12.4], t: [0.3, 0.3, 0], fov: 36 },
    { p: [0.6, 0.35, 11.4], t: [0.5, 0.3, 0], fov: 36 },
  ],
  ask: [
    { p: [0.4, 0.6, 10.6], t: [0.6, 0.4, 0.3], fov: 36 },
    { p: [0.2, 0.4, 9.8], t: [0.6, 0.3, 0.3], fov: 36 },
  ],
  focus: [
    { p: [0, 0.35, 9.6], t: [0, 0.2, 1.5], fov: 34 },
    { p: [0.2, 0.2, 8.9], t: [0, 0.15, 1.5], fov: 34 },
  ],
  torn: [
    { p: [0, 0.5, 12.2], t: [0.3, 0.2, 0], fov: 36 },
    { p: [1.8, 0.5, 10.4], t: [1.6, 0.3, 0], fov: 36 },
  ],
  verdict: [
    { p: [0, 0.5, 15.6], t: [0, 0.1, 0], fov: 36 },
    { p: [0, 0.4, 14.4], t: [0, 0.1, 0], fov: 36 },
  ],
  faults: [
    { p: [-9, 0.8, 13.5], t: [0, 0.4, 0], fov: 36 },
    { p: [-2.5, 0.9, 14.5], t: [0, 0.4, 0], fov: 36 },
  ],
  limits: [
    { p: [0, 0.2, 14], t: [0, 0, 0], fov: 38 },
    { p: [0, 0.6, 12.6], t: [0, 0, 0], fov: 38 },
  ],
  gather: [
    { p: [0, 0.3, 9.6], t: [0, 0, 0], fov: 34 },
    { p: [0, 0.3, 8.6], t: [0, 0, 0], fov: 34 },
  ],
  exit: [
    { p: [1.2, 0.35, 11.2], t: [1.4, 0, 0], fov: 34 },
    { p: [3.2, 0.7, 12.8], t: [2.4, 0, 0], fov: 34 },
  ],
};

const poses = HOLDS.flatMap(([f]) => POSES[f]);
const posCurve = new THREE.CatmullRomCurve3(
  poses.map((x) => new THREE.Vector3(...x.p)),
  false,
  "centripetal"
);
const tgtCurve = new THREE.CatmullRomCurve3(
  poses.map((x) => new THREE.Vector3(...x.t)),
  false,
  "centripetal"
);

/** Camera pose at rail parameter `cam` (keyframe index space). */
export function railAt(cam: number, pos: THREE.Vector3, target: THREE.Vector3): number {
  const n = poses.length - 1;
  const u = Math.min(n, Math.max(0, cam)) / n;
  posCurve.getPoint(u, pos);
  tgtCurve.getPoint(u, target);
  const i = Math.min(n - 1, Math.floor(cam));
  const f = Math.min(1, Math.max(0, cam - i));
  return poses[i].fov + (poses[Math.min(n, i + 1)].fov - poses[i].fov) * f;
}
