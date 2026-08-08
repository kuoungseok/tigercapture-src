const clamp = (value: number, low: number, high: number) =>
  Math.max(low, Math.min(high, value));

export const useCurrentFrame = (): number =>
  Number((globalThis as any).__TIGER_FRAME__ || 0);

export const useVideoConfig = () => ({
  width: Number((globalThis as any).__TIGER_WIDTH__ || 1920),
  height: Number((globalThis as any).__TIGER_HEIGHT__ || 1080),
  fps: Number((globalThis as any).__TIGER_FPS__ || 30),
  durationInFrames: Number((globalThis as any).__TIGER_DURATION_FRAMES__ || 150),
});

export const interpolate = (
  input: number,
  inputRange: number[],
  outputRange: number[],
  options: Record<string, unknown> = {},
): number => {
  if (inputRange.length < 2 || inputRange.length !== outputRange.length) {
    return Number(outputRange[0] || 0);
  }
  let segment = inputRange.length - 2;
  for (let index = 0; index < inputRange.length - 1; index += 1) {
    if (input <= inputRange[index + 1]) {
      segment = index;
      break;
    }
  }
  const start = inputRange[segment];
  const end = inputRange[segment + 1];
  let progress = end === start ? 0 : (input - start) / (end - start);
  if (options.extrapolateLeft === "clamp" && input < inputRange[0]) progress = 0;
  if (options.extrapolateRight === "clamp" && input > inputRange[inputRange.length - 1]) progress = 1;
  return outputRange[segment] +
    (outputRange[segment + 1] - outputRange[segment]) * progress;
};

export const spring = ({
  frame = 0,
  fps = 30,
  from = 0,
  to = 1,
  durationInFrames,
  delay = 0,
  config = {},
}: {
  frame?: number;
  fps?: number;
  from?: number;
  to?: number;
  durationInFrames?: number;
  delay?: number;
  config?: { damping?: number; stiffness?: number; mass?: number };
}): number => {
  const localFrame = Math.max(0, frame - delay);
  const mass = Math.max(0.001, Number(config.mass ?? 1));
  const stiffness = Math.max(0.001, Number(config.stiffness ?? 100));
  const damping = Math.max(0, Number(config.damping ?? 10));
  const time = localFrame / Math.max(1, fps);
  const omega0 = Math.sqrt(stiffness / mass);
  const zeta = damping / (2 * Math.sqrt(stiffness * mass));
  let progress: number;
  if (zeta < 1) {
    const omegaD = omega0 * Math.sqrt(1 - zeta * zeta);
    progress = 1 - Math.exp(-zeta * omega0 * time) *
      (Math.cos(omegaD * time) + (zeta * omega0 / omegaD) * Math.sin(omegaD * time));
  } else {
    progress = 1 - Math.exp(-omega0 * time);
  }
  if (durationInFrames && localFrame >= durationInFrames) progress = 1;
  return from + (to - from) * progress;
};

const hash = (value: string): number => {
  let result = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    result ^= value.charCodeAt(index);
    result = Math.imul(result, 16777619);
  }
  return result >>> 0;
};

export const random = (seed: string | number): number =>
  hash(String(seed)) / 4294967296;
