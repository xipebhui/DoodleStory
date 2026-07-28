import React from "react";
import {
  AbsoluteFill,
  Html5Audio,
  Img,
  interpolate,
  Series,
  staticFile,
  useCurrentFrame,
} from "remotion";

import {
  compositionDurationInFrames,
  FPS,
  type MotionPreset,
  type NarratedPanelsProps,
  type NarratedScene,
  sceneDurationInFrames,
} from "./types";

const FADE_FRAMES = 8;
const BGM_VOLUME = 0.12;

const motionTransform = (
  motion: MotionPreset,
  progress: number,
): string => {
  switch (motion) {
    case "zoom_in":
      return `scale(${interpolate(progress, [0, 1], [1, 1.08])})`;
    case "zoom_out":
      return `scale(${interpolate(progress, [0, 1], [1.08, 1])})`;
    case "pan_left":
      return `scale(1.08) translateX(${interpolate(progress, [0, 1], [3, -3])}%)`;
    case "pan_right":
      return `scale(1.08) translateX(${interpolate(progress, [0, 1], [-3, 3])}%)`;
    case "pan_up":
      return `scale(1.08) translateY(${interpolate(progress, [0, 1], [3, -3])}%)`;
    case "pan_down":
      return `scale(1.08) translateY(${interpolate(progress, [0, 1], [-3, 3])}%)`;
    case "static":
      return "scale(1)";
  }
};

const Scene: React.FC<{scene: NarratedScene}> = ({scene}) => {
  const frame = useCurrentFrame();
  const durationInFrames = sceneDurationInFrames(scene.durationMs);
  const progress = interpolate(
    frame,
    [0, Math.max(1, durationInFrames - 1)],
    [0, 1],
    {extrapolateLeft: "clamp", extrapolateRight: "clamp"},
  );
  const opacity = Math.min(
    interpolate(frame, [0, FADE_FRAMES], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }),
    interpolate(
      frame,
      [Math.max(0, durationInFrames - FADE_FRAMES - 1), durationInFrames - 1],
      [1, 0],
      {extrapolateLeft: "clamp", extrapolateRight: "clamp"},
    ),
  );
  const currentMs = (frame / FPS) * 1000;
  const caption = scene.captions.find(
    (cue) => currentMs >= cue.startMs && currentMs < cue.endMs,
  );
  const visibleSubtitle = caption?.text ?? scene.subtitle;

  return (
    <AbsoluteFill style={{backgroundColor: "#080808", overflow: "hidden"}}>
      <AbsoluteFill style={{opacity}}>
        <Img
          src={staticFile(scene.image)}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            transform: motionTransform(scene.motion, progress),
            transformOrigin: "center center",
          }}
        />
      </AbsoluteFill>
      <Html5Audio src={staticFile(scene.audio)} volume={1} />
      {visibleSubtitle ? <AbsoluteFill
        style={{
          justifyContent: "flex-end",
          alignItems: "center",
          padding: "0 72px 150px",
          pointerEvents: "none",
        }}
      >
        <div
          style={{
            maxWidth: 936,
            color: "#fff",
            fontFamily:
              '"PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif',
            fontSize: 58,
            fontWeight: 700,
            lineHeight: 1.42,
            letterSpacing: 1,
            textAlign: "center",
            whiteSpace: "pre-wrap",
            overflowWrap: "anywhere",
            textShadow:
              "0 3px 5px rgba(0,0,0,.95), 0 0 12px rgba(0,0,0,.9), 2px 2px 0 rgba(0,0,0,.8)",
          }}
        >
          {visibleSubtitle}
        </div>
      </AbsoluteFill> : null}
    </AbsoluteFill>
  );
};

export const NarratedPanels: React.FC<NarratedPanelsProps> = (props) => {
  const frame = useCurrentFrame();
  const totalFrames = compositionDurationInFrames(props);
  const bgmVolume = Math.min(
    BGM_VOLUME,
    interpolate(frame, [0, 30], [0, BGM_VOLUME], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }),
    interpolate(
      frame,
      [Math.max(0, totalFrames - 45), Math.max(1, totalFrames - 1)],
      [BGM_VOLUME, 0],
      {extrapolateLeft: "clamp", extrapolateRight: "clamp"},
    ),
  );

  return (
    <AbsoluteFill style={{backgroundColor: "#080808"}}>
      <Series>
        {props.scenes.map((scene) => (
          <Series.Sequence
            key={scene.id}
            durationInFrames={sceneDurationInFrames(scene.durationMs)}
          >
            <Scene scene={scene} />
          </Series.Sequence>
        ))}
      </Series>
      {props.bgm ? (
        <Html5Audio
          src={staticFile(props.bgm)}
          loop
          volume={bgmVolume}
        />
      ) : null}
    </AbsoluteFill>
  );
};
