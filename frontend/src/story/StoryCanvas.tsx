"use client";

import { Suspense, useEffect, useMemo, useRef, useSyncExternalStore } from "react";
import * as THREE from "three";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { PerformanceMonitor } from "@react-three/drei";
import { Bloom, ChromaticAberration, EffectComposer, Vignette } from "@react-three/postprocessing";
import { BlendFunction } from "postprocessing";
import { gsap } from "gsap";
import { tokens } from "@/design/tokens";
import { ACTS, actIndex, getActive, state, subscribe } from "./engine/store";
import HeroField from "./scenes/HeroField";
import StatuteStack from "./scenes/StatuteStack";
import TaxRibbon from "./scenes/TaxRibbon";
import Society from "./scenes/Society";
import VerdictBoard from "./scenes/VerdictBoard";
import FaultField from "./scenes/FaultField";
import Constellation from "./scenes/Constellation";
import Convergence from "./scenes/Convergence";

/** R3F renders only when the GSAP ticker says so: one loop for scroll, tweens and WebGL. */
function TickerDriver() {
  const advance = useThree((s) => s.advance);
  useEffect(() => {
    const tick = (time: number) => {
      state.time = time;
      advance(time * 1000);
    };
    gsap.ticker.add(tick);
    return () => gsap.ticker.remove(tick);
  }, [advance]);
  return null;
}

/** Eases the real camera toward the pose the active scene asks for. */
function CameraRig() {
  const camera = useThree((s) => s.camera) as THREE.PerspectiveCamera;
  const size = useThree((s) => s.size);
  // Narrow screens: the copy fills the lower part, so lift every scene into
  // the top of the frame by shifting the projection window.
  useEffect(() => {
    if (size.width / size.height < 0.9) camera.setViewOffset(size.width, size.height, 0, size.height * 0.24, size.width, size.height);
    else camera.clearViewOffset();
    camera.updateProjectionMatrix();
  }, [camera, size]);
  const target = useMemo(() => new THREE.Vector3(), []);
  const want = useMemo(() => new THREE.Vector3(), []);
  const wantTarget = useMemo(() => new THREE.Vector3(), []);
  const first = useRef(true);
  useFrame((_, dt) => {
    const c = state.camera;
    want.set(...c.position);
    wantTarget.set(...c.target);
    // Pointer parallax, a few centimetres.
    want.x += state.pointer.x * 0.25;
    want.y += state.pointer.y * 0.15;
    const k = first.current ? 1 : 1 - Math.exp(-dt * 3.2);
    first.current = false;
    camera.position.lerp(want, k);
    target.lerp(wantTarget, k);
    camera.lookAt(target);
    if (Math.abs(camera.fov - c.fov) > 0.01) {
      camera.fov += (c.fov - camera.fov) * k;
      camera.updateProjectionMatrix();
    }
  });
  return null;
}

const SCENES: { id: string; acts: number[]; el: (acts: number[]) => JSX.Element }[] = [
  { id: "hero", acts: [actIndex("prologue")], el: (a) => <HeroField act={a[0]} /> },
  { id: "stack", acts: [actIndex("text"), actIndex("reading")], el: (a) => <StatuteStack acts={[a[0], a[1]]} /> },
  { id: "ribbon", acts: [actIndex("curve")], el: (a) => <TaxRibbon act={a[0]} /> },
  { id: "society", acts: [actIndex("society")], el: (a) => <Society act={a[0]} /> },
  { id: "verdict", acts: [actIndex("verdict")], el: (a) => <VerdictBoard act={a[0]} /> },
  { id: "faults", acts: [actIndex("faults")], el: (a) => <FaultField act={a[0]} /> },
  { id: "constellation", acts: [actIndex("provenance")], el: (a) => <Constellation act={a[0]} /> },
  { id: "finale", acts: [actIndex("finale")], el: (a) => <Convergence act={a[0]} /> },
];

/** Mounts only the scenes of the active act and its neighbours. */
function Director() {
  const active = useSyncExternalStore(subscribe, getActive, () => 0);
  const mounted = SCENES.filter((s) => s.acts.some((a) => Math.abs(a - active) <= 1));
  return (
    <>
      {mounted.map((s) => (
        <Suspense key={s.id} fallback={null}>
          {s.el(s.acts)}
        </Suspense>
      ))}
    </>
  );
}

/** Chromatic aberration follows scroll speed, so it only shows in transitions. */
function Post({ tier }: { tier: number }) {
  const ca = useRef<{ offset: THREE.Vector2 } | null>(null);
  const offset = useMemo(() => new THREE.Vector2(0, 0), []);
  useFrame(() => {
    const v = Math.min(1, Math.abs(state.velocity) / 60);
    offset.set(0.0022 * v, 0.0012 * v);
    if (ca.current) ca.current.offset = offset;
  });
  return (
    <EffectComposer multisampling={0} enableNormalPass={false}>
      <Bloom mipmapBlur intensity={tier >= 3 ? 1.15 : 0.85} luminanceThreshold={1} luminanceSmoothing={0.25} radius={0.72} />
      <ChromaticAberration
        ref={ca as never}
        blendFunction={BlendFunction.NORMAL}
        offset={offset}
        radialModulation={false}
        modulationOffset={0}
      />
      <Vignette eskil={false} offset={0.28} darkness={0.72} />
    </EffectComposer>
  );
}

export default function StoryCanvas({ onDecline }: { onDecline: () => void }) {
  const tier = state.tier;
  return (
    <Canvas
      frameloop="never"
      dpr={tier >= 3 ? [1, 2] : tier === 2 ? [1, 1.5] : 1}
      gl={{ antialias: tier <= 1, powerPreference: "high-performance", alpha: false, stencil: false }}
      camera={{ fov: 38, near: 0.1, far: 200, position: [0, 2.3, 9.5] }}
      onCreated={({ gl, scene }) => {
        gl.setClearColor(tokens.ink[900]);
        scene.background = new THREE.Color(tokens.ink[900]);
        scene.fog = new THREE.Fog(tokens.ink[900], 18, 60);
      }}
      aria-hidden
    >
      <TickerDriver />
      <CameraRig />
      <PerformanceMonitor onDecline={onDecline} flipflops={2} />
      <Director />
      {tier >= 2 && <Post tier={tier} />}
    </Canvas>
  );
}

export { ACTS };
