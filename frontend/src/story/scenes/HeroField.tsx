"use client";

import { useMemo, useRef } from "react";
import * as THREE from "three";
import { useFrame, useThree } from "@react-three/fiber";
import { simplex3 } from "../shaders/noise";
import { presence, progress, state } from "../engine/store";
import { C, rng } from "./kit";

const LINES = 72;
const SEGMENTS = 220;
const SIGNAL_LINE = 49;

const vertex = /* glsl */ `
${simplex3}
uniform float uTime;
uniform float uProgress;
uniform vec2 uPointer;
uniform float uPointerOn;
attribute float aU;
attribute float aLine;
attribute float aOff;
attribute float aSignal;
varying float vAlpha;
varying float vSignal;
varying float vDepth;
void main() {
  float x = (aU - 0.5) * 30.0;
  float z = mix(-36.0, 6.0, aLine);
  float calm = 1.0 - uProgress * 0.8;
  float n = snoise(vec3(x * 0.075, z * 0.11, uTime * 0.11));
  float n2 = snoise(vec3(x * 0.23 + 3.0, z * 0.27, uTime * 0.19)) * 0.28;
  float y = (n + n2) * 1.15 * calm;
  float d = distance(vec2(x, z), uPointer);
  y += uPointerOn * 0.55 * exp(-d * d * 0.07) * sin(d * 1.5 - uTime * 3.2);
  // The sheet tilts up into a page as the reader scrolls on.
  y += uProgress * (z + 36.0) * 0.16;
  // The signal line rises out of the sheet.
  y += aSignal * (0.08 + uProgress * 0.9) + aOff;
  vec4 mv = modelViewMatrix * vec4(x, y, z, 1.0);
  gl_Position = projectionMatrix * mv;
  vDepth = -mv.z;
  vAlpha = smoothstep(0.0, 0.14, aU) * smoothstep(1.0, 0.86, aU);
  vSignal = aSignal;
}
`;

const fragment = /* glsl */ `
uniform vec3 uPaper;
uniform vec3 uSignal;
uniform float uOpacity;
uniform float uTime;
varying float vAlpha;
varying float vSignal;
varying float vDepth;
void main() {
  float fog = smoothstep(46.0, 5.0, vDepth);
  vec3 col = mix(uPaper * 0.62, uSignal, vSignal);
  float a = vAlpha * fog * mix(0.5, 1.0, vSignal) * uOpacity;
  gl_FragColor = vec4(col, a);
}
`;

const dustVertex = /* glsl */ `
uniform float uTime;
uniform float uSize;
attribute float aSeed;
varying float vA;
void main() {
  vec3 p = position;
  p.y += sin(uTime * 0.3 + aSeed * 6.28) * 0.35;
  p.x += cos(uTime * 0.17 + aSeed * 12.0) * 0.4;
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  gl_Position = projectionMatrix * mv;
  gl_PointSize = uSize * (0.6 + aSeed) * (12.0 / -mv.z);
  vA = smoothstep(40.0, 4.0, -mv.z) * (0.25 + 0.5 * aSeed);
}
`;

const dustFragment = /* glsl */ `
uniform vec3 uColor;
uniform float uOpacity;
varying float vA;
void main() {
  float d = length(gl_PointCoord - 0.5);
  float a = smoothstep(0.5, 0.0, d) * vA * uOpacity;
  gl_FragColor = vec4(uColor, a);
}
`;

/** Act 0: a sheet of ruled paper breathing in the dark; one line is the signal. */
export default function HeroField({ act }: { act: number }) {
  const { camera, size } = useThree();
  const mat = useRef<THREE.ShaderMaterial>(null);
  const dustMat = useRef<THREE.ShaderMaterial>(null);
  const plane = useMemo(() => new THREE.Plane(new THREE.Vector3(0, 1, 0), 0), []);
  const ray = useMemo(() => new THREE.Raycaster(), []);
  const hit = useMemo(() => new THREE.Vector3(), []);
  const ndc = useMemo(() => new THREE.Vector2(), []);

  const geometry = useMemo(() => {
    const us: number[] = [];
    const ls: number[] = [];
    const offs: number[] = [];
    const sig: number[] = [];
    const push = (line: number, off: number, signal: number) => {
      for (let s = 0; s < SEGMENTS - 1; s++) {
        for (const k of [s, s + 1]) {
          us.push(k / (SEGMENTS - 1));
          ls.push(line / (LINES - 1));
          offs.push(off);
          sig.push(signal);
        }
      }
    };
    for (let l = 0; l < LINES; l++) push(l, 0, 0);
    // The signal line is drawn three times, a hair apart, so it reads thicker.
    for (const off of [0, 0.012, -0.012]) push(SIGNAL_LINE, off, 1);
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(new Float32Array(us.length * 3), 3));
    g.setAttribute("aU", new THREE.Float32BufferAttribute(us, 1));
    g.setAttribute("aLine", new THREE.Float32BufferAttribute(ls, 1));
    g.setAttribute("aOff", new THREE.Float32BufferAttribute(offs, 1));
    g.setAttribute("aSignal", new THREE.Float32BufferAttribute(sig, 1));
    g.boundingSphere = new THREE.Sphere(new THREE.Vector3(0, 0, -15), 60);
    return g;
  }, []);

  const dust = useMemo(() => {
    const r = rng(11);
    const n = state.tier >= 3 ? 2400 : state.tier === 2 ? 1400 : 600;
    const pos = new Float32Array(n * 3);
    const seed = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      pos[i * 3] = (r() - 0.5) * 34;
      pos[i * 3 + 1] = r() * 7 - 0.5;
      pos[i * 3 + 2] = -36 + r() * 42;
      seed[i] = r();
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    g.setAttribute("aSeed", new THREE.BufferAttribute(seed, 1));
    return g;
  }, []);

  const uniforms = useMemo(
    () => ({
      uTime: { value: 0 },
      uProgress: { value: 0 },
      uPointer: { value: new THREE.Vector2(999, 999) },
      uPointerOn: { value: 0 },
      uPaper: { value: C.paper.clone() },
      uSignal: { value: C.signalHot.clone() },
      uOpacity: { value: 1 },
    }),
    []
  );
  const dustUniforms = useMemo(
    () => ({
      uTime: { value: 0 },
      uSize: { value: size.height / 260 },
      uColor: { value: C.paper.clone() },
      uOpacity: { value: 1 },
    }),
    [size.height]
  );

  useFrame((_, dt) => {
    const vis = presence(act);
    const p = progress(act);
    const u = uniforms;
    u.uTime.value += dt;
    u.uProgress.value = p;
    u.uOpacity.value = vis;
    // Pointer ripple: where the cursor meets the sheet.
    ndc.set(state.pointer.x, state.pointer.y);
    ray.setFromCamera(ndc, camera);
    if (ray.ray.intersectPlane(plane, hit)) {
      u.uPointer.value.lerp(new THREE.Vector2(hit.x, hit.z), 0.12);
      u.uPointerOn.value += ((state.tier >= 2 ? 1 : 0) - u.uPointerOn.value) * 0.05;
    }
    dustUniforms.uTime.value = u.uTime.value;
    dustUniforms.uOpacity.value = vis;
    if (state.active === act) {
      state.camera.position = [0, 2.3 + p * 3.2, 9.5 - p * 2.5];
      state.camera.target = [0, -0.4 + p * 2.6, -8];
      state.camera.fov = 38;
    }
    if (mat.current) mat.current.visible = vis > 0.001;
    if (dustMat.current) dustMat.current.visible = vis > 0.001;
  });

  return (
    <group>
      <lineSegments geometry={geometry} frustumCulled={false}>
        <shaderMaterial
          ref={mat}
          vertexShader={vertex}
          fragmentShader={fragment}
          uniforms={uniforms}
          transparent
          depthWrite={false}
          toneMapped={false}
        />
      </lineSegments>
      <points geometry={dust} frustumCulled={false}>
        <shaderMaterial
          ref={dustMat}
          vertexShader={dustVertex}
          fragmentShader={dustFragment}
          uniforms={dustUniforms}
          transparent
          depthWrite={false}
          blending={THREE.AdditiveBlending}
        />
      </points>
    </group>
  );
}
