/**
 * The story's sound, synthesised in the browser (no audio files): a slow
 * drone whose chord follows the act, a filtered noise bed, a whoosh that
 * follows scroll speed, and a soft chime when a new beat of the story enters.
 * Created only from a click on the sound toggle; suspended while the tab is
 * hidden.
 */

/* A minor pentatonic world that resolves to A major at the end. */
const CHORDS: number[][] = [
  [110, 164.81, 220], // hero
  [87.31, 130.81, 220], // why
  [98, 146.83, 246.94], // read
  [130.81, 196, 329.63], // run
  [146.83, 220, 349.23], // case
  [82.41, 123.47, 207.65], // verdict
  [73.42, 110, 174.61], // faults
  [110, 164.81, 261.63], // limits
  [110, 164.81, 277.18], // end
];
const BELLS = [659.25, 587.33, 523.25, 440, 392, 329.63];

export interface Sound {
  update: (act: number, exposure: number, velocity: number) => void;
  chime: (k: number) => void;
  setOn: (on: boolean) => void;
  dispose: () => void;
}

function impulse(ctx: AudioContext, seconds: number) {
  const len = Math.floor(ctx.sampleRate * seconds);
  const buf = ctx.createBuffer(2, len, ctx.sampleRate);
  for (let ch = 0; ch < 2; ch++) {
    const d = buf.getChannelData(ch);
    for (let i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, 2.6);
  }
  return buf;
}

function pinkNoise(ctx: AudioContext, seconds: number) {
  const len = Math.floor(ctx.sampleRate * seconds);
  const buf = ctx.createBuffer(1, len, ctx.sampleRate);
  const d = buf.getChannelData(0);
  let b0 = 0,
    b1 = 0,
    b2 = 0;
  for (let i = 0; i < len; i++) {
    const w = Math.random() * 2 - 1;
    b0 = 0.99765 * b0 + w * 0.099046;
    b1 = 0.963 * b1 + w * 0.2965164;
    b2 = 0.57 * b2 + w * 1.0526913;
    d[i] = (b0 + b1 + b2 + w * 0.1848) * 0.12;
  }
  return buf;
}

export function createSound(): Sound {
  const AC = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
  const ctx = new AC();
  const master = ctx.createGain();
  master.gain.value = 0;
  const comp = ctx.createDynamicsCompressor();
  comp.threshold.value = -20;
  master.connect(comp).connect(ctx.destination);
  const verb = ctx.createConvolver();
  verb.buffer = impulse(ctx, 3.2);
  const wet = ctx.createGain();
  wet.gain.value = 0.55;
  verb.connect(wet).connect(master);

  const filter = ctx.createBiquadFilter();
  filter.type = "lowpass";
  filter.frequency.value = 900;
  filter.Q.value = 0.6;
  const droneGain = ctx.createGain();
  droneGain.gain.value = 0.16;
  filter.connect(droneGain);
  droneGain.connect(master);
  droneGain.connect(verb);

  const voices = CHORDS[0].map((f) => {
    const g = ctx.createGain();
    g.gain.value = 0.22;
    g.connect(filter);
    const a = ctx.createOscillator();
    a.type = "sine";
    a.frequency.value = f;
    a.detune.value = -5;
    const b = ctx.createOscillator();
    b.type = "triangle";
    b.frequency.value = f;
    b.detune.value = 6;
    const bg = ctx.createGain();
    bg.gain.value = 0.35;
    a.connect(g);
    b.connect(bg).connect(g);
    a.start();
    b.start();
    return { a, b };
  });
  const lfo = ctx.createOscillator();
  lfo.frequency.value = 0.05;
  const lfoGain = ctx.createGain();
  lfoGain.gain.value = 220;
  lfo.connect(lfoGain).connect(filter.frequency);
  lfo.start();

  const noise = ctx.createBufferSource();
  noise.buffer = pinkNoise(ctx, 4);
  noise.loop = true;
  const bed = ctx.createBiquadFilter();
  bed.type = "bandpass";
  bed.frequency.value = 600;
  bed.Q.value = 0.7;
  const bedGain = ctx.createGain();
  bedGain.gain.value = 0.05;
  const whoosh = ctx.createBiquadFilter();
  whoosh.type = "bandpass";
  whoosh.frequency.value = 1200;
  whoosh.Q.value = 1.2;
  const whooshGain = ctx.createGain();
  whooshGain.gain.value = 0;
  noise.connect(bed).connect(bedGain).connect(master);
  noise.connect(whoosh).connect(whooshGain).connect(master);
  noise.start();

  let act = -1;
  let on = false;
  const vis = () => {
    if (document.hidden) void ctx.suspend();
    else if (on) void ctx.resume();
  };
  document.addEventListener("visibilitychange", vis);

  return {
    update(a, exposure, velocity) {
      if (!on) return;
      const t = ctx.currentTime;
      if (a !== act && CHORDS[a]) {
        act = a;
        CHORDS[a].forEach((f, i) => {
          voices[i].a.frequency.setTargetAtTime(f, t, 0.9);
          voices[i].b.frequency.setTargetAtTime(f, t, 0.9);
        });
      }
      filter.frequency.setTargetAtTime(380 + 1500 * Math.min(1.2, exposure), t, 0.4);
      const v = Math.min(1, Math.abs(velocity) / 3);
      whooshGain.gain.setTargetAtTime(v * 0.22, t, 0.12);
      whoosh.frequency.setTargetAtTime(700 + v * 1800, t, 0.12);
    },
    chime(k) {
      if (!on) return;
      const t = ctx.currentTime;
      const f = BELLS[((k % BELLS.length) + BELLS.length) % BELLS.length];
      const car = ctx.createOscillator();
      const mod = ctx.createOscillator();
      const modGain = ctx.createGain();
      const g = ctx.createGain();
      car.frequency.value = f;
      mod.frequency.value = f * 2.01;
      modGain.gain.setValueAtTime(f * 1.2, t);
      modGain.gain.exponentialRampToValueAtTime(1, t + 1.6);
      g.gain.setValueAtTime(0.0001, t);
      g.gain.exponentialRampToValueAtTime(0.05, t + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, t + 2.4);
      mod.connect(modGain).connect(car.frequency);
      car.connect(g);
      g.connect(master);
      g.connect(verb);
      car.start(t);
      mod.start(t);
      car.stop(t + 2.5);
      mod.stop(t + 2.5);
    },
    setOn(next) {
      on = next;
      const t = ctx.currentTime;
      if (next) {
        void ctx.resume();
        master.gain.cancelScheduledValues(t);
        master.gain.setTargetAtTime(0.9, t, 0.8);
      } else {
        master.gain.cancelScheduledValues(t);
        master.gain.setTargetAtTime(0, t, 0.25);
        setTimeout(() => {
          if (!on) void ctx.suspend();
        }, 1200);
      }
    },
    dispose() {
      document.removeEventListener("visibilitychange", vis);
      void ctx.close();
    },
  };
}
