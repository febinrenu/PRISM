"use client";

import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Environment, Lightformer } from "@react-three/drei";
import { Bloom, ChromaticAberration, EffectComposer, Noise, SMAA, ToneMapping, Vignette } from "@react-three/postprocessing";
import { BlendFunction, ToneMappingMode, type BloomEffect, type ChromaticAberrationEffect, type VignetteEffect } from "postprocessing";
import { tokens } from "@/design/tokens";
import { F } from "../engine/config";
import { loop } from "../engine/loop";
import { state, type Tier } from "../engine/store";
import { MAX_DPR } from "../engine/tier";
import type { Atlas } from "./atlas";
import type { FormData } from "./forms";
import Particles from "./Particles";
import Prism from "./Prism";
import { railAt } from "./rail";

/** The story's single clock drives R3F: the DOM updates, then the frame renders. */
function Driver() {
  const { advance, gl, scene } = useThree();
  useEffect(() => {
    // R3F's clock runs in seconds
    loop.render = (t: number) => advance(t);
    loop.gl = gl;
    loop.scene = scene;
    return () => {
      loop.render = null;
      loop.gl = null;
      loop.scene = null;
    };
  }, [advance, gl, scene]);
  return null;
}

/** The camera rides the rail; the pointer adds a few centimetres of parallax. */
function Rail() {
  const camera = useThree((s) => s.camera) as THREE.PerspectiveCamera;
  const size = useThree((s) => s.size);
  const pos = useMemo(() => new THREE.Vector3(), []);
  const tgt = useMemo(() => new THREE.Vector3(), []);
  const par = useMemo(() => new THREE.Vector2(), []);
  useEffect(() => {
    loop.camera = camera;
    return () => {
      loop.camera = null;
    };
  }, [camera]);
  useFrame((_, dt) => {
    const d = state.director;
    const fov = railAt(d.cam, pos, tgt);
    const k = 1 - Math.exp(-Math.min(dt, 0.05) * 4);
    par.x += (state.pointer.x * 0.22 - par.x) * k;
    par.y += (state.pointer.y * 0.14 - par.y) * k;
    // narrow screens: step back so wide subjects (pages, boards) fit above the copy
    const aspect = size.width / size.height;
    const narrow = aspect < 0.9;
    const back = aspect < 0.7 ? 1.6 : narrow ? 1.5 : 1;
    camera.position.set(tgt.x + (pos.x - tgt.x) * back + par.x, tgt.y + (pos.y - tgt.y) * back + par.y, tgt.z + (pos.z - tgt.z) * back);
    camera.lookAt(tgt);
    state.focusDist = camera.position.distanceTo(tgt);
    camera.fov = narrow ? fov * 1.15 : fov;
    // compose the subject away from the copy: sideways on wide screens, upwards on narrow ones
    const ox = narrow ? 0 : d.shiftX * size.width;
    // portrait: the copy owns the lower half, so lift the subject into the upper part
    const oy = aspect < 0.7 ? size.height * 0.2 : narrow ? size.height * 0.27 : 0;
    camera.setViewOffset(size.width, size.height, ox, oy, size.width, size.height);
    camera.updateProjectionMatrix();
  }, -2);
  return null;
}

const FX = typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("fx") : null;
const fx = (k: string) => !FX || FX.split(",").includes(k);

function Post({ tier }: { tier: Tier }) {
  const bloom = useRef<BloomEffect>(null);
  const ca = useRef<ChromaticAberrationEffect>(null);
  const vig = useRef<VignetteEffect>(null);
  const offset = useMemo(() => new THREE.Vector2(), []);
  useFrame(() => {
    const d = state.director;
    if (bloom.current) bloom.current.intensity = (tier >= 3 ? 1.25 : 1.0) * d.bloom;
    const v = Math.min(1, Math.abs(state.velocity) / 3);
    offset.set(0.0016 * v, 0.0009 * v);
    if (ca.current) ca.current.offset = offset;
    if (vig.current) vig.current.darkness = d.vignette;
  });
  return (
    <EffectComposer multisampling={0} enableNormalPass={false} frameBufferType={THREE.HalfFloatType}>
      {fx("bloom") ? <Bloom ref={bloom as never} mipmapBlur intensity={1.1} luminanceThreshold={0.95} luminanceSmoothing={0.25} radius={0.78} resolutionScale={tier >= 3 ? 1 : 0.5} /> : <></>}
      {fx("ca") ? <ChromaticAberration ref={ca as never} blendFunction={BlendFunction.NORMAL} offset={offset} radialModulation={false} modulationOffset={0} /> : <></>}
      {fx("vig") ? <Vignette ref={vig as never} eskil={false} offset={0.3} darkness={0.7} /> : <></>}
      {fx("tone") ? <ToneMapping mode={ToneMappingMode.AGX} /> : <></>}
      {fx("noise") ? <Noise premultiply blendFunction={BlendFunction.ADD} opacity={0.035} /> : <></>}
      {fx("smaa") ? <SMAA /> : <></>}
    </EffectComposer>
  );
}

/**
 * Compile every program and upload every texture before the curtain lifts:
 * render each form once, then hand control to the scroll.
 */
function Preflight({ onReady }: { onReady: () => void }) {
  const { gl, scene, camera, advance } = useThree();
  const done = useRef(false);
  useEffect(() => {
    if (done.current) return;
    done.current = true;
    let live = true;
    (async () => {
      const d = state.director;
      const saved = { ...d };
      try {
        await (gl as THREE.WebGLRenderer & { compileAsync?: (s: THREE.Object3D, c: THREE.Camera) => Promise<void> }).compileAsync?.(scene, camera);
      } catch {
        /* compile on first render instead */
      }
      const stops = [F.flow, F.page, F.entities, F.graph, F.population, F.verdict, F.gather, F.exit];
      for (const f of stops) {
        if (!live) return;
        Object.assign(d, { form: f, prism: 1, beam: 1, aperture: 0.05 });
        advance(performance.now() / 1000);
        await new Promise((r) => requestAnimationFrame(() => r(null)));
      }
      Object.assign(d, saved);
      advance(performance.now() / 1000);
      if (live) onReady();
    })();
    return () => {
      live = false;
    };
  }, [gl, scene, camera, advance, onReady]);
  return null;
}

/** Lowers the pixel ratio (never below 1) when frames run long; never remounts anything. */
function Governor({ tier }: { tier: Tier }) {
  const setDpr = useThree((s) => s.setDpr);
  const samples = useRef<number[]>([]);
  const since = useRef(0);
  const dpr = useRef(Math.min(window.devicePixelRatio || 1, MAX_DPR[tier]));
  useFrame((_, dt) => {
    if (state.time < 3 || document.hidden) return;
    samples.current.push(dt * 1000);
    if (samples.current.length < 90) return;
    const sorted = [...samples.current].sort((a, b) => a - b);
    samples.current = [];
    const median = sorted[45];
    if (median > 21 && dpr.current > 1 && state.time - since.current > 2) {
      dpr.current = Math.max(1, dpr.current - 0.25);
      since.current = state.time;
      setDpr(dpr.current);
    }
  });
  return null;
}

export default function StoryCanvas({ data, atlas, tier, onReady }: { data: FormData; atlas: Atlas; tier: Tier; onReady: () => void }) {
  const dpr = Math.min(typeof window === "undefined" ? 1 : window.devicePixelRatio || 1, MAX_DPR[tier]);
  return (
    <Canvas
      frameloop="never"
      flat
      dpr={dpr}
      gl={{ antialias: false, powerPreference: "high-performance", alpha: false, stencil: false, depth: true, toneMapping: THREE.NoToneMapping }}
      camera={{ fov: 34, near: 0.1, far: 120, position: [0, 0.2, 12.5] }}
      onCreated={({ gl, scene }) => {
        gl.setClearColor(tokens.ink[900]);
        scene.background = new THREE.Color(tokens.ink[900]);
      }}
      aria-hidden
    >
      <Driver />
      <Rail />
      {tier >= 2 && (
        <Environment resolution={256} frames={1}>
          <Lightformer form="rect" intensity={3} position={[0, 4, -4]} scale={[10, 2, 1]} />
          <Lightformer form="rect" intensity={2} color={tokens.signal[300]} position={[-6, 0, 2]} rotation-y={Math.PI / 2} scale={[6, 2, 1]} />
          <Lightformer form="rect" intensity={2} color={tokens.hue.blue.text} position={[6, 1, 2]} rotation-y={-Math.PI / 2} scale={[6, 2, 1]} />
          <Lightformer form="ring" intensity={1.5} position={[0, -3, 5]} scale={4} />
        </Environment>
      )}
      <Particles data={data} atlas={atlas} />
      <Prism data={data} tier={tier} />
      {!(typeof window !== "undefined" && window.location.search.includes("nopost=1")) && <Post tier={tier} />}
      <Governor tier={tier} />
      <Preflight onReady={onReady} />
    </Canvas>
  );
}
