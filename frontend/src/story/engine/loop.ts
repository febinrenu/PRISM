import type * as THREE from "three";

/**
 * Hooks the story's single ticker calls each frame, in order: the scene
 * renders (`render`), then the DOM overlay projects its labels with the
 * camera that just rendered (`overlay`).
 */
export const loop: {
  render: ((t: number) => void) | null;
  overlay: (() => void) | null;
  camera: THREE.PerspectiveCamera | null;
  gl: THREE.WebGLRenderer | null;
  scene: THREE.Scene | null;
} = { render: null, overlay: null, camera: null, gl: null, scene: null };
