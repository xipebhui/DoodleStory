export const TEMPLATE_ID = "narrated-panel-v1" as const;
export const FPS = 30;
export const WIDTH = 1080;
export const HEIGHT = 1920;

export const MOTION_PRESETS = [
  "static",
  "zoom_in",
  "zoom_out",
  "pan_left",
  "pan_right",
  "pan_up",
  "pan_down",
] as const;

export type MotionPreset = (typeof MOTION_PRESETS)[number];

export type NarratedScene = {
  id: string;
  image: string;
  audio: string;
  subtitle: string;
  durationMs: number;
  motion: MotionPreset;
};

export type NarratedPanelsProps = {
  scenes: NarratedScene[];
  bgm: string | null;
};

export const sceneDurationInFrames = (durationMs: number) =>
  Math.max(1, Math.ceil((durationMs / 1000) * FPS));

export const compositionDurationInFrames = (props: NarratedPanelsProps) =>
  props.scenes.reduce(
    (total, scene) => total + sceneDurationInFrames(scene.durationMs),
    0,
  );
