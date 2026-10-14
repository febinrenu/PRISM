"use client";

import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { useFrame, useThree } from "@react-three/fiber";
import { MeshTransmissionMaterial } from "@react-three/drei";
import { tokens } from "@/design/tokens";
import { ENTITY_ORDER } from "../data";
import { BEAM_SOURCE } from "../engine/config";
import { state } from "../engine/store";
import type { FormData } from "./forms";

const SRC = new THREE.Vector3(...BEAM_SOURCE);

/** The PRISM mark as a solid: an equilateral triangle, bevelled, extruded. */
function prismGeometry() {
  const s = 1.25;
  const shape = new THREE.Shape();
  shape.moveTo(0, s);
  shape.lineTo(-s * 0.866, -s * 0.5);
  shape.lineTo(s * 0.866, -s * 0.5);
  shape.closePath();
  const geo = new THREE.ExtrudeGeometry(shape, {
    depth: 1.5,
    bevelEnabled: true,
    bevelThickness: 0.06,
    bevelSize: 0.06,
    bevelSegments: 4,
    curveSegments: 1,
  });
  geo.center();
  geo.computeVertexNormals();
  return geo;
}

/** A cheap glass for modest GPUs: fresnel rim and a thin-film spectral band. */
const cheapGlass = () =>
  new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: true,
    blending: THREE.AdditiveBlending,
    uniforms: { uTime: { value: 0 }, uOpacity: { value: 1 } },
    vertexShader: /* glsl */ `
      varying vec3 vN; varying vec3 vV; varying vec3 vP;
      void main(){ vec4 mv = modelViewMatrix*vec4(position,1.); vN = normalize(normalMatrix*normal); vV = normalize(-mv.xyz); vP = position; gl_Position = projectionMatrix*mv; }`,
    fragmentShader: /* glsl */ `
      uniform float uTime; uniform float uOpacity;
      varying vec3 vN; varying vec3 vV; varying vec3 vP;
      vec3 spectral(float x){ return clamp(vec3(abs(x*6.-3.)-1., 2.-abs(x*6.-2.), 2.-abs(x*6.-4.)),0.,1.); }
      void main(){
        float f = pow(1.0 - abs(dot(vN, vV)), 2.6);
        vec3 film = spectral(fract(f*1.4 + vP.y*0.25 + uTime*0.03));
        vec3 c = mix(vec3(0.95,0.93,0.89), film, 0.55) * (0.05 + f*1.6);
        gl_FragColor = vec4(c*uOpacity, 1.0);
      }`,
  });

/** Light as a soft cylinder: bright where the view crosses its axis, fading to its edges. */
const beamMaterial = (color: THREE.Color, hot: number) =>
  new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    side: THREE.DoubleSide,
    uniforms: { uColor: { value: color }, uI: { value: 0 }, uTime: { value: 0 }, uHot: { value: hot } },
    vertexShader: /* glsl */ `
      varying vec3 vN; varying vec3 vV; varying vec2 vUv;
      void main(){ vec4 mv = modelViewMatrix*vec4(position,1.); vN = normalize(normalMatrix*normal); vV = normalize(-mv.xyz); vUv = uv; gl_Position = projectionMatrix*mv; }`,
    fragmentShader: /* glsl */ `
      uniform vec3 uColor; uniform float uI; uniform float uTime; uniform float uHot;
      varying vec3 vN; varying vec3 vV; varying vec2 vUv;
      float h(float x){ return fract(sin(x*127.1)*43758.5453); }
      float n1(float x){ float i=floor(x); float f=fract(x); return mix(h(i),h(i+1.),f*f*(3.-2.*f)); }
      void main(){
        float core = pow(abs(dot(vN, vV)), 3.0);
        float along = vUv.y;
        float ends = smoothstep(0.0, 0.08, along) * smoothstep(1.0, 0.55, along);
        float dust = 0.75 + 0.25 * n1(along*40.0 - uTime*2.2) * n1(vUv.x*20.0 + uTime*0.4);
        float a = core * ends * dust * uI;
        gl_FragColor = vec4(uColor * a * (0.35 + core * uHot), 1.0);
      }`,
  });

function Beam({ from, dir, length, r0, r1, material }: { from: THREE.Vector3; dir: THREE.Vector3; length: number; r0: number; r1: number; material: THREE.ShaderMaterial }) {
  const geo = useMemo(() => {
    const g = new THREE.CylinderGeometry(r1, r0, length, 32, 1, true);
    g.translate(0, length / 2, 0);
    return g;
  }, [length, r0, r1]);
  const quat = useMemo(() => new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.clone().normalize()), [dir]);
  useEffect(() => () => geo.dispose(), [geo]);
  return <mesh geometry={geo} material={material} position={from} quaternion={quat} frustumCulled={false} renderOrder={1} />;
}

export default function Prism({ data, tier }: { data: FormData; tier: number }) {
  const group = useRef<THREE.Group>(null);
  const mesh = useRef<THREE.Mesh>(null);
  const geo = useMemo(prismGeometry, []);
  const { gl, scene, camera, size } = useThree();
  const rt = useMemo(
    () =>
      new THREE.WebGLRenderTarget(4, 4, {
        type: THREE.HalfFloatType,
        minFilter: THREE.LinearFilter,
        magFilter: THREE.LinearFilter,
      }),
    []
  );
  useEffect(() => {
    const k = tier >= 3 ? 0.5 : 0.35;
    rt.setSize(Math.max(4, Math.round(size.width * k)), Math.max(4, Math.round(size.height * k)));
  }, [rt, size, tier]);
  const cheap = useMemo(cheapGlass, []);
  useEffect(
    () => () => {
      rt.dispose();
      cheap.dispose();
      geo.dispose();
    },
    [rt, cheap, geo]
  );

  const inMat = useMemo(() => beamMaterial(new THREE.Color(tokens.paper[100]), 2.2), []);
  const outMats = useMemo(
    () => ENTITY_ORDER.map((l) => beamMaterial(new THREE.Color(tokens.entity[l].base).multiplyScalar(1.2), 1.8)),
    []
  );
  const exitMat = useMemo(() => beamMaterial(new THREE.Color(tokens.paper[100]), 2.0), []);
  useEffect(() => () => [inMat, exitMat, ...outMats].forEach((m) => m.dispose()), [inMat, exitMat, outMats]);
  const dirs = useMemo(() => data.beams.map((b) => new THREE.Vector3(...b.dir)), [data]);
  const zero = useMemo(() => new THREE.Vector3(), []);
  const incoming = useMemo(() => new THREE.Vector3().subVectors(zero, SRC), [zero]);
  const exitDir = useMemo(() => new THREE.Vector3(1, -0.04, 0).normalize(), []);
  const useGlass = tier >= 2;

  // our own refraction buffer: the scene behind the glass, only while the glass is on screen
  useFrame(() => {
    const d = state.director;
    const g = group.current;
    const m = mesh.current;
    if (!g || !m) return;
    const vis = d.prism > 0.01;
    g.position.set(d.prismX, d.prismY, d.prismZ);
    const s = 0.001 + d.prism;
    m.scale.setScalar(s);
    m.rotation.set(0.18 * Math.sin(state.time * 0.21), d.prismSpin + Math.sin(state.time * 0.13) * 0.12, 0);
    m.visible = vis;
    cheap.uniforms.uTime.value = state.time;
    cheap.uniforms.uOpacity.value = d.prism;
    const beamI = d.beam * Math.min(1, d.prism * 1.5);
    const gather = Math.max(0, Math.min(1, (d.form - 15) * 1)); // 15 gather → 16 exit
    inMat.uniforms.uI.value = beamI;
    for (const om of outMats) om.uniforms.uI.value = beamI * (1 - gather);
    exitMat.uniforms.uI.value = beamI * gather;
    for (const bm of [inMat, exitMat, ...outMats]) bm.uniforms.uTime.value = state.time;
    if (useGlass && vis) {
      m.visible = false;
      const prevTarget = gl.getRenderTarget();
      gl.setRenderTarget(rt);
      gl.clear();
      gl.render(scene, camera);
      gl.setRenderTarget(prevTarget);
      m.visible = true;
    }
  }, 0);

  return (
    <group ref={group}>
      <mesh ref={mesh} geometry={geo} renderOrder={3} material={useGlass ? undefined : cheap}>
        {useGlass && (
          <MeshTransmissionMaterial
            buffer={rt.texture}
            samples={tier >= 3 ? 8 : 4}
            resolution={256}
            thickness={1.4}
            ior={1.45}
            chromaticAberration={0.9}
            anisotropicBlur={0.15}
            distortion={0.12}
            distortionScale={0.4}
            temporalDistortion={0.05}
            roughness={0.04}
            clearcoat={1}
            attenuationDistance={4}
            attenuationColor="#ffffff"
            color="#f4f1ea"
            backside={false}
          />
        )}
      </mesh>
      <Beam from={SRC.clone()} dir={incoming} length={incoming.length() - 0.6} r0={0.34} r1={0.2} material={inMat} />
      {dirs.map((dir, c) => (
        <Beam key={c} from={zero} dir={dir} length={12} r0={0.08} r1={0.1 + 0.55 * data.beams[c].width} material={outMats[c]} />
      ))}
      <Beam from={zero} dir={exitDir} length={13} r0={0.12} r1={0.26} material={exitMat} />
    </group>
  );
}
