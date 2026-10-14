"use client";

import { useEffect, useMemo } from "react";
import * as THREE from "three";
import { useFrame, useThree } from "@react-three/fiber";
import { tokens } from "@/design/tokens";
import { ENTITY_ORDER } from "../data";
import { BEAM_SOURCE } from "../engine/config";
import { state } from "../engine/store";
import { GRID, type Atlas } from "./atlas";
import type { FormData } from "./forms";

const SIDE = 256; // texture side: 256 × 256 = 65,536 particles

const vertex = /* glsl */ `
precision highp float;
precision highp int;
precision highp sampler2DArray;

uniform sampler2DArray uPos;
uniform sampler2DArray uMeta;
uniform sampler2DArray uAux;
uniform int uFormA;
uniform int uFormB;
uniform float uMix;
uniform float uTime;
uniform float uTurb;
uniform float uChroma;
uniform float uGateOn;
uniform float uGateX;
uniform float uExposure;
uniform float uPxScale;
uniform float uFocus;
uniform float uAperture;
uniform float uFlowSpeed;
uniform vec3 uSrc;
uniform vec3 uPrism;
uniform vec3 uOut[6];
uniform float uWidth[6];
uniform vec3 uSingle;
uniform vec3 uPal[16];

in float aSeed;
in float aClass;

out vec3 vCol;
out float vAlpha;
out float vGlyph;
out float vBlur;

const float PI = 3.14159265;

vec3 field(vec3 p, float t) {
  return vec3(
    sin(p.y * 1.31 + t) + sin(p.z * 0.93 - t * 0.71),
    sin(p.z * 1.12 + t * 0.83) + sin(p.x * 0.71 + t * 0.53),
    sin(p.x * 1.23 - t * 0.61) + sin(p.y * 0.87 + t * 0.92)
  ) * 0.5;
}

// position along the beam: in from the source to the prism, out along this class's ray
vec3 flowPos(vec4 A, int flags, float seed, out float fade) {
  float s = fract(A.z + uTime * uFlowSpeed * (0.75 + 0.5 * seed));
  fade = smoothstep(0.0, 0.035, s) * (1.0 - smoothstep(0.94, 1.0, s));
  float L = 0.46;
  vec2 lat = A.xy;
  if (s < L) {
    float u = s / L;
    vec3 dirIn = normalize(uPrism - uSrc);
    vec3 side = normalize(cross(dirIn, vec3(0.0, 0.0, 1.0)));
    vec3 up = cross(side, dirIn);
    float w = 0.28 * (1.0 - 0.55 * u);
    return mix(uSrc, uPrism, u) + (side * lat.x + up * lat.y) * w;
  }
  float u = (s - L) / (1.0 - L);
  int c = int(aClass + 0.5);
  bool single = (flags & 4) != 0;
  vec3 dir = single ? uSingle : uOut[c];
  vec3 side = normalize(cross(dir, vec3(0.0, 0.0, 1.0)));
  vec3 up = cross(side, dir);
  float w = single ? 0.16 + 0.1 * u : (0.1 + 0.55 * u) * uWidth[c];
  return uPrism + dir * (0.25 + u * 11.0) + (side * lat.x + up * lat.y) * w;
}

void main() {
  int id = gl_VertexID;
  ivec2 tc = ivec2(id & 255, id >> 8);
  vec4 A = texelFetch(uPos, ivec3(tc, uFormA), 0);
  vec4 B = texelFetch(uPos, ivec3(tc, uFormB), 0);
  vec4 MA = texelFetch(uMeta, ivec3(tc, uFormA), 0) * 255.0;
  vec4 MB = texelFetch(uMeta, ivec3(tc, uFormB), 0) * 255.0;
  float dB = texelFetch(uAux, ivec3(tc, uFormB), 0).x * 255.0;
  float dA = texelFetch(uAux, ivec3(tc, uFormA), 0).x * 255.0;
  float seed = aSeed;
  int fA = int(MA.w + 0.5);
  int fB = int(MB.w + 0.5);

  // choreography: a particle's own delay in the form it is heading to
  float d = dB > 0.5 ? (dB - 1.0) / 254.0 : (dA > 0.5 ? (dA - 1.0) / 254.0 : seed);
  d = clamp(d * 0.85 + seed * 0.15, 0.0, 1.0);
  float st = clamp((uMix - 0.42 * d) / 0.58, 0.0, 1.0);
  st = st * st * st * (st * (st * 6.0 - 15.0) + 10.0);

  float fadeA = 1.0, fadeB = 1.0;
  vec3 pA = (fA & 1) != 0 ? flowPos(A, fA, seed, fadeA) : A.xyz;
  vec3 pB = (fB & 1) != 0 ? flowPos(B, fB, seed, fadeB) : B.xyz;
  vec3 p = mix(pA, pB, st);
  float env = sin(PI * st);
  p += field(p * 0.32 + seed * 6.0, uTime * 0.55) * env * uTurb * 1.15;
  p += field(p * 0.9 + 3.0, uTime * 0.22) * 0.018;

  // colour: neutral until refracted (past the prism, or everywhere when chroma is up)
  float side = smoothstep(-0.25, 0.45, p.x - uGateX) * uGateOn;
  float refr = max(uChroma, side);
  vec3 neutral = uPal[6];
  float iA = (fA & 2) != 0 ? 1.0 : refr;
  float iB = (fB & 2) != 0 ? 1.0 : refr;
  vec3 cA = mix(neutral, uPal[int(MA.x + 0.5)], iA);
  vec3 cB = mix(neutral, uPal[int(MB.x + 0.5)], iB);
  float bright = mix(MA.z, MB.z, st) / 100.0;
  vCol = mix(cA, cB, st) * bright * uExposure;

  float g = st < 0.5 ? MA.y : MB.y;
  vGlyph = g;

  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  float dist = max(0.05, -mv.z);
  float coc = clamp(abs(dist - uFocus) * uAperture, 0.0, 2.5);
  vBlur = coc;
  float size = mix(A.w, B.w, st);
  float px = size * uPxScale / dist * (1.0 + coc * 1.6);
  float a = 1.0 / ((1.0 + coc) * (1.0 + coc));
  if (px < 1.6) {
    a *= (px * px) / (1.6 * 1.6);
    px = 1.6;
  }
  px = min(px, 220.0);
  a *= mix((fA & 1) != 0 ? fadeA : 1.0, (fB & 1) != 0 ? fadeB : 1.0, st);
  a *= smoothstep(0.35, 1.4, dist);
  vAlpha = a;
  gl_PointSize = px;
  gl_Position = projectionMatrix * mv;
}
`;

const fragment = /* glsl */ `
precision highp float;
uniform sampler2D uAtlas;
in vec3 vCol;
in float vAlpha;
in float vGlyph;
in float vBlur;
out vec4 fragColor;

void main() {
  vec2 pc = gl_PointCoord;
  float r = length(pc - 0.5) * 2.0;
  float disc = pow(clamp(1.0 - r, 0.0, 1.0), 1.6);
  float a = disc;
  if (vGlyph > 0.5) {
    float gi = floor(vGlyph + 0.5);
    float cx = mod(gi, ${GRID}.0);
    float cy = floor(gi / ${GRID}.0);
    vec2 uv = vec2((cx + pc.x) / ${GRID}.0, 1.0 - (cy + pc.y) / ${GRID}.0);
    float glyph = texture(uAtlas, uv).a;
    a = mix(glyph, disc * 0.6, clamp(vBlur, 0.0, 1.0));
  }
  a *= vAlpha;
  if (a < 0.003) discard;
  fragColor = vec4(vCol * a, 1.0);
}
`;

function hex(c: string) {
  return new THREE.Color(c);
}

/** Palette slots: six entity hues (ENTITY_ORDER), paper, vermilion, grey, gain, then a six-step ramp. */
function palette() {
  const ent = ENTITY_ORDER.map((l) => hex(tokens.entity[l].base).multiplyScalar(1.25));
  return [
    ...ent,
    hex(tokens.paper[100]),
    hex(tokens.signal[500]).multiplyScalar(1.15),
    hex("#8A8780"),
    hex(tokens.hue.teal.text),
    ...tokens.sequential.map((c) => hex(c).multiplyScalar(1.3)),
  ];
}

export default function Particles({ data, atlas }: { data: FormData; atlas: Atlas }) {
  const gl = useThree((s) => s.gl);
  const { geometry, material, textures } = useMemo(() => {
    const n = data.n;
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(n * 3), 3));
    const seed = new Float32Array(n);
    let a = 9301;
    for (let i = 0; i < n; i++) {
      a = (a * 49297 + 233280) % 233280;
      seed[i] = a / 233280;
    }
    geo.setAttribute("aSeed", new THREE.BufferAttribute(seed, 1));
    geo.setAttribute("aClass", new THREE.BufferAttribute(Float32Array.from(data.classes), 1));
    geo.setDrawRange(0, state.count || n);

    const pos = new THREE.DataArrayTexture(data.pos as Float32Array<ArrayBuffer>, SIDE, SIDE, data.forms);
    pos.format = THREE.RGBAFormat;
    pos.type = THREE.FloatType;
    const meta = new THREE.DataArrayTexture(data.meta as Uint8Array<ArrayBuffer>, SIDE, SIDE, data.forms);
    meta.format = THREE.RGBAFormat;
    meta.type = THREE.UnsignedByteType;
    const aux = new THREE.DataArrayTexture(data.aux as Uint8Array<ArrayBuffer>, SIDE, SIDE, data.forms);
    aux.format = THREE.RGBAFormat;
    aux.type = THREE.UnsignedByteType;
    for (const t of [pos, meta, aux]) {
      t.minFilter = t.magFilter = THREE.NearestFilter;
      t.generateMipmaps = false;
      t.needsUpdate = true;
    }
    const at = new THREE.CanvasTexture(atlas.canvas);
    at.generateMipmaps = true;
    at.minFilter = THREE.LinearMipmapLinearFilter;
    at.magFilter = THREE.LinearFilter;
    at.anisotropy = 4;
    at.needsUpdate = true;

    const mat = new THREE.ShaderMaterial({
      glslVersion: THREE.GLSL3,
      vertexShader: vertex,
      fragmentShader: fragment,
      transparent: true,
      depthWrite: false,
      depthTest: true,
      blending: THREE.CustomBlending,
      blendSrc: THREE.OneFactor,
      blendDst: THREE.OneFactor,
      blendEquation: THREE.AddEquation,
      uniforms: {
        uPos: { value: pos },
        uMeta: { value: meta },
        uAux: { value: aux },
        uAtlas: { value: at },
        uFormA: { value: 0 },
        uFormB: { value: 0 },
        uMix: { value: 0 },
        uTime: { value: 0 },
        uTurb: { value: 1 },
        uChroma: { value: 0 },
        uGateOn: { value: 1 },
        uGateX: { value: 0 },
        uExposure: { value: 1 },
        uPxScale: { value: 800 },
        uFocus: { value: 10 },
        uAperture: { value: 0 },
        uFlowSpeed: { value: 0.045 },
        uSrc: { value: new THREE.Vector3(...BEAM_SOURCE) },
        uPrism: { value: new THREE.Vector3() },
        uOut: { value: data.beams.map((b) => new THREE.Vector3(...b.dir)) },
        uWidth: { value: data.beams.map((b) => b.width) },
        uSingle: { value: new THREE.Vector3(1, -0.04, 0).normalize() },
        uPal: { value: palette() },
      },
    });
    return { geometry: geo, material: mat, textures: [pos, meta, aux, at] };
  }, [data, atlas]);

  useEffect(
    () => () => {
      geometry.dispose();
      material.dispose();
      textures.forEach((t) => t.dispose());
    },
    [geometry, material, textures]
  );

  const size = useThree((s) => s.size);
  const camera = useThree((s) => s.camera) as THREE.PerspectiveCamera;
  useFrame(() => {
    const d = state.director;
    const u = material.uniforms;
    const f = Math.max(0, Math.min(data.forms - 1, d.form));
    const a = Math.min(data.forms - 2, Math.floor(f));
    u.uFormA.value = a;
    u.uFormB.value = a + 1;
    u.uMix.value = f - a;
    u.uTime.value = state.time;
    u.uTurb.value = d.turb;
    u.uChroma.value = d.chroma;
    u.uGateOn.value = d.gate;
    u.uExposure.value = d.exposure;
    u.uAperture.value = d.aperture;
    u.uPrism.value.set(d.prismX, d.prismY, d.prismZ);
    u.uGateX.value = d.prismX;
    u.uFocus.value = state.focusDist;
    u.uPxScale.value = (size.height * gl.getPixelRatio()) / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2));
  }, -1);

  return <points geometry={geometry} material={material} frustumCulled={false} renderOrder={2} />;
}
