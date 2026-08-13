import React from "react";
import {
  AbsoluteFill,
  Html5Audio,
  interpolate,
  OffthreadVideo,
  Series,
  staticFile,
  useCurrentFrame,
} from "remotion";

export const PAYNES_CREEK_GROK_SHORT_TEMPLATE_ID =
  "paynes-creek-grok-ai-short-v1" as const;

export type GrokShortEvidenceLevel =
  | "直接证据"
  | "解释"
  | "重建"
  | "未知边界";

export type PaynesCreekGrokShortScene = {
  id: string;
  title: string;
  narration: string;
  evidence: GrokShortEvidenceLevel;
  video: string;
  durationInFrames: number;
  playbackRate: number;
};

export type PaynesCreekGrokShortProps = {
  title: string;
  scenes: PaynesCreekGrokShortScene[];
  narrationAudio: string;
  width: number;
  height: number;
};

const COLORS = {
  deep: "#061922",
  ink: "#102A33",
  salt: "#F4F6F1",
  muted: "#C8D8D9",
  teal: "#46D8CF",
  amber: "#F1B766",
  reconstruction: "#C98234",
  unknown: "#E37A6A",
};

const evidenceColor: Record<GrokShortEvidenceLevel, string> = {
  "直接证据": COLORS.teal,
  "解释": COLORS.amber,
  "重建": COLORS.reconstruction,
  "未知边界": COLORS.unknown,
};

const GrokShortScene: React.FC<{
  scene: PaynesCreekGrokShortScene;
  index: number;
  count: number;
}> = ({scene, index, count}) => {
  const frame = useCurrentFrame();
  const end = Math.max(1, scene.durationInFrames - 1);
  const opacity = interpolate(
    frame,
    [0, 8, Math.max(9, end - 8), end],
    [0, 1, 1, 0],
    {extrapolateLeft: "clamp", extrapolateRight: "clamp"},
  );
  const progress = interpolate(frame, [0, end], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const color = evidenceColor[scene.evidence];

  return (
    <AbsoluteFill
      style={{
        backgroundColor: COLORS.deep,
        color: COLORS.salt,
        fontFamily: '"Microsoft YaHei", "Noto Sans CJK SC", sans-serif',
        opacity,
      }}
    >
      <OffthreadVideo
        src={staticFile(scene.video)}
        playbackRate={scene.playbackRate}
        volume={0}
        style={{width: "100%", height: "100%", objectFit: "cover"}}
      />
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(180deg, rgba(6,25,34,.72) 0%, rgba(6,25,34,0) 26%, rgba(6,25,34,0) 58%, rgba(6,25,34,.96) 88%, #061922 100%)",
        }}
      />
      <AbsoluteFill
        style={{
          boxShadow: "inset 0 0 160px rgba(6,25,34,.58)",
          border: "1px solid rgba(244,246,241,.08)",
        }}
      />

      <div
        style={{
          position: "absolute",
          top: 54,
          left: 70,
          right: 70,
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 36,
          textShadow: "0 3px 14px rgba(0,0,0,.88)",
        }}
      >
        <div style={{display: "flex", alignItems: "center", gap: 22}}>
          <span
            style={{
              color: COLORS.amber,
              fontSize: 28,
              fontWeight: 900,
              letterSpacing: 4,
            }}
          >
            {String(index + 1).padStart(2, "0")}
          </span>
          <span style={{fontSize: 44, lineHeight: 1.2, fontWeight: 900}}>
            {scene.title}
          </span>
        </div>
        <span
          style={{
            flex: "none",
            border: `3px solid ${color}`,
            borderRadius: 999,
            color,
            fontSize: 27,
            fontWeight: 900,
            padding: "10px 22px",
            backgroundColor: "rgba(6,25,34,.72)",
          }}
        >
          {scene.evidence}
        </span>
      </div>

      <div
        style={{
          position: "absolute",
          left: 130,
          right: 130,
          bottom: 54,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 22,
          textAlign: "center",
          textShadow: "0 4px 16px rgba(0,0,0,.96)",
        }}
      >
        <div
          style={{
            maxWidth: 1580,
            fontSize: 45,
            fontWeight: 800,
            lineHeight: 1.48,
            letterSpacing: 1.1,
          }}
        >
          {scene.narration}
        </div>
        <div
          style={{
            color: COLORS.muted,
            fontSize: 22,
            fontWeight: 700,
            letterSpacing: 3,
          }}
        >
          PAYNES CREEK · AI VISUAL PILOT · {index + 1}/{count}
        </div>
      </div>

      <div
        style={{
          position: "absolute",
          left: 0,
          bottom: 0,
          height: 7,
          width: `${progress * 100}%`,
          backgroundColor: color,
          boxShadow: `0 0 18px ${color}`,
        }}
      />
    </AbsoluteFill>
  );
};

export const paynesCreekGrokShortDurationInFrames = (
  props: PaynesCreekGrokShortProps,
) => props.scenes.reduce((sum, scene) => sum + scene.durationInFrames, 0);

export const PaynesCreekGrokShort: React.FC<PaynesCreekGrokShortProps> = (
  props,
) => (
  <AbsoluteFill style={{backgroundColor: COLORS.deep}}>
    <Series>
      {props.scenes.map((scene, index) => (
        <Series.Sequence key={scene.id} durationInFrames={scene.durationInFrames}>
          <GrokShortScene
            scene={scene}
            index={index}
            count={props.scenes.length}
          />
        </Series.Sequence>
      ))}
    </Series>
    <Html5Audio src={staticFile(props.narrationAudio)} volume={1} />
  </AbsoluteFill>
);

