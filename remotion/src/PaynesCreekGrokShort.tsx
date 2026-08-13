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
  | "未知边界"
  | "Direct evidence"
  | "Interpretation"
  | "Reconstruction"
  | "Evidence limit";

export type PaynesCreekGrokShortScene = {
  id: string;
  title: string;
  narration: string;
  evidence: GrokShortEvidenceLevel;
  video: string;
  durationInFrames: number;
  playbackRate: number;
  captions: Array<{
    text: string;
    startFrame: number;
    endFrame: number;
  }>;
  motion: "none" | "push_in" | "drift_left" | "drift_right";
  visualTreatment:
    | "none"
    | "coast_to_inland"
    | "process_filter"
    | "process_boil"
    | "transport_clue"
    | "evidence_chain";
  hook: null | {
    eyebrow: string;
    headline: string;
    question: string;
  };
};

export type PaynesCreekGrokShortProps = {
  title: string;
  locale: "zh-CN" | "en-US";
  editMode: "classic" | "retention";
  footer: string;
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
  "Direct evidence": COLORS.teal,
  "Interpretation": COLORS.amber,
  "Reconstruction": COLORS.reconstruction,
  "Evidence limit": COLORS.unknown,
};

const RetentionGraphic: React.FC<{
  treatment: PaynesCreekGrokShortScene["visualTreatment"];
  frame: number;
  hasHook: boolean;
}> = ({treatment, frame, hasHook}) => {
  if (treatment === "none") {
    return null;
  }
  const delay = hasHook ? 72 : 18;
  const opacity = interpolate(frame, [delay, delay + 10], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const translateY = interpolate(frame, [delay, delay + 12], [18, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const shell: React.CSSProperties = {
    position: "absolute",
    top: 158,
    right: 72,
    display: "flex",
    alignItems: "center",
    gap: 18,
    border: "1px solid rgba(244,246,241,.28)",
    borderRadius: 18,
    padding: "17px 22px",
    background: "rgba(6,25,34,.82)",
    boxShadow: "0 16px 50px rgba(0,0,0,.35)",
    opacity,
    transform: `translateY(${translateY}px)`,
    textShadow: "0 2px 10px rgba(0,0,0,.8)",
  };
  const label: React.CSSProperties = {
    color: COLORS.amber,
    fontSize: 18,
    fontWeight: 900,
    letterSpacing: 3,
  };
  const value: React.CSSProperties = {
    color: COLORS.salt,
    fontSize: 28,
    fontWeight: 900,
    letterSpacing: 0.3,
  };

  if (treatment === "coast_to_inland") {
    return <div style={{...shell, width: 520, justifyContent: "space-between"}}>
      <div><div style={label}>SOURCE</div><div style={value}>COAST</div></div>
      <div style={{display: "flex", alignItems: "center", flex: 1, gap: 8}}>
        <div style={{height: 2, flex: 1, borderTop: `3px dashed ${COLORS.teal}`}} />
        <div style={{color: COLORS.teal, fontSize: 32}}>→</div>
      </div>
      <div style={{textAlign: "right"}}><div style={label}>DESTINATION?</div><div style={value}>INLAND</div></div>
    </div>;
  }

  if (treatment === "process_filter" || treatment === "process_boil") {
    const isFilter = treatment === "process_filter";
    return <div style={shell}>
      <div style={{
        width: 52,
        height: 52,
        borderRadius: 999,
        display: "grid",
        placeItems: "center",
        color: COLORS.deep,
        backgroundColor: isFilter ? COLORS.teal : COLORS.amber,
        fontSize: 24,
        fontWeight: 1000,
      }}>{isFilter ? "01" : "02"}</div>
      <div>
        <div style={label}>PROCESS STEP</div>
        <div style={value}>{isFilter ? "FILTER → CONCENTRATE" : "HEAT → CRYSTALLIZE"}</div>
      </div>
    </div>;
  }

  if (treatment === "transport_clue") {
    return <div style={{...shell, borderColor: "rgba(70,216,207,.72)"}}>
      <div style={{color: COLORS.teal, fontSize: 34}}>◆</div>
      <div><div style={label}>TRANSPORT CLUE</div><div style={value}>FULL-SIZE WOODEN PADDLE</div></div>
    </div>;
  }

  return <div style={{...shell, left: 190, right: 190, justifyContent: "center"}}>
    {["CONCENTRATE", "BOIL", "CRYSTALLIZE", "MOVE BY WATER", "ROUTE ?"].map((item, index) => <React.Fragment key={item}>
      {index > 0 ? <span style={{color: index === 4 ? COLORS.unknown : COLORS.teal, fontSize: 25}}>→</span> : null}
      <span style={{
        color: index === 4 ? COLORS.unknown : COLORS.salt,
        fontSize: 21,
        fontWeight: 900,
        letterSpacing: 1.4,
      }}>{item}</span>
    </React.Fragment>)}
  </div>;
};

const HookOverlay: React.FC<{
  hook: NonNullable<PaynesCreekGrokShortScene["hook"]>;
  frame: number;
}> = ({hook, frame}) => {
  const opacity = interpolate(frame, [0, 5, 66, 82], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const scale = interpolate(frame, [0, 82], [0.96, 1.02], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return <AbsoluteFill style={{
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "radial-gradient(circle at center, rgba(6,25,34,.42), rgba(6,25,34,.86))",
    opacity,
  }}>
    <div style={{textAlign: "center", transform: `scale(${scale})`, marginTop: -40}}>
      <div style={{color: COLORS.teal, fontSize: 24, fontWeight: 900, letterSpacing: 7, marginBottom: 22}}>{hook.eyebrow}</div>
      <div style={{color: COLORS.salt, fontSize: 86, lineHeight: 1.04, fontWeight: 1000, letterSpacing: -2, textShadow: "0 5px 28px rgba(0,0,0,.9)"}}>{hook.headline}</div>
      <div style={{color: COLORS.amber, fontSize: 40, fontWeight: 900, letterSpacing: 2.2, marginTop: 25}}>{hook.question}</div>
    </div>
  </AbsoluteFill>;
};

const GrokShortScene: React.FC<{
  scene: PaynesCreekGrokShortScene;
  index: number;
  count: number;
  locale: "zh-CN" | "en-US";
  editMode: "classic" | "retention";
  footer: string;
}> = ({scene, index, count, locale, editMode, footer}) => {
  const frame = useCurrentFrame();
  const end = Math.max(1, scene.durationInFrames - 1);
  const classicOpacity = interpolate(
    frame,
    [0, 8, Math.max(9, end - 8), end],
    [0, 1, 1, 0],
    {extrapolateLeft: "clamp", extrapolateRight: "clamp"},
  );
  const retentionIn = index === 0
    ? interpolate(frame, [0, 4], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp"})
    : 1;
  const retentionOut = index === count - 1
    ? interpolate(frame, [Math.max(1, end - 6), end], [1, 0], {extrapolateLeft: "clamp", extrapolateRight: "clamp"})
    : 1;
  const opacity = editMode === "classic" ? classicOpacity : retentionIn * retentionOut;
  const progress = interpolate(frame, [0, end], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const color = evidenceColor[scene.evidence];
  const isEnglish = locale === "en-US";
  const isRetention = editMode === "retention";
  const activeCaptionIndex = scene.captions.findIndex(
    (caption) => frame >= caption.startFrame && frame < caption.endFrame,
  );
  const resolvedCaptionIndex = activeCaptionIndex === -1
    ? scene.captions.length - 1
    : activeCaptionIndex;
  const activeCaption = scene.captions[resolvedCaptionIndex];
  const captionOpacity = isRetention
    ? interpolate(
      frame,
      [activeCaption.startFrame, activeCaption.startFrame + 3, Math.max(activeCaption.startFrame + 4, activeCaption.endFrame - 3), activeCaption.endFrame],
      [0, 1, 1, 0],
      {extrapolateLeft: "clamp", extrapolateRight: "clamp"},
    )
    : 1;
  const motionScale = isRetention
    ? interpolate(frame, [0, end], [1.02, 1.075], {extrapolateLeft: "clamp", extrapolateRight: "clamp"})
    : 1;
  const motionX = scene.motion === "drift_left"
    ? interpolate(frame, [0, end], [18, -18])
    : scene.motion === "drift_right"
      ? interpolate(frame, [0, end], [-18, 18])
      : 0;
  const titleOpacity = isRetention && scene.hook
    ? interpolate(frame, [66, 82], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp"})
    : 1;

  return (
    <AbsoluteFill
      style={{
        backgroundColor: COLORS.deep,
        color: COLORS.salt,
        fontFamily: isEnglish
          ? 'Inter, "Segoe UI", Arial, sans-serif'
          : '"Microsoft YaHei", "Noto Sans CJK SC", sans-serif',
        opacity,
      }}
    >
      <OffthreadVideo
        src={staticFile(scene.video)}
        playbackRate={scene.playbackRate}
        volume={0}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: `translateX(${motionX}px) scale(${motionScale})`,
        }}
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
          opacity: titleOpacity,
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
          <span
            style={{
              maxWidth: isEnglish ? 1320 : 1480,
              fontSize: isEnglish ? 39 : 44,
              lineHeight: 1.18,
              fontWeight: 900,
              letterSpacing: isEnglish ? -0.5 : 0,
            }}
          >
            {scene.title}
          </span>
        </div>
        <span
          style={{
            flex: "none",
            border: `3px solid ${color}`,
            borderRadius: 999,
            color,
            fontSize: isEnglish ? 23 : 27,
            fontWeight: 900,
            padding: "10px 22px",
            backgroundColor: "rgba(6,25,34,.72)",
          }}
        >
          {scene.evidence}
        </span>
      </div>

      {isRetention ? <RetentionGraphic
        treatment={scene.visualTreatment}
        frame={frame}
        hasHook={Boolean(scene.hook)}
      /> : null}

      <div
        style={{
          position: "absolute",
          left: 130,
          right: 130,
          bottom: 54,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: isRetention ? 10 : 22,
          textAlign: "center",
          textShadow: "0 4px 16px rgba(0,0,0,.96)",
        }}
      >
        {isRetention ? <div style={{
          color,
          fontSize: 17,
          fontWeight: 900,
          letterSpacing: 3,
          opacity: captionOpacity,
        }}>PHRASE {resolvedCaptionIndex + 1}/{scene.captions.length}</div> : null}
        <div
          style={{
            maxWidth: isRetention ? 1500 : 1580,
            minHeight: isRetention ? 74 : undefined,
            display: "flex",
            alignItems: "center",
            fontSize: isRetention ? 54 : isEnglish ? 42 : 45,
            fontWeight: isRetention ? 900 : isEnglish ? 750 : 800,
            lineHeight: isRetention ? 1.18 : isEnglish ? 1.4 : 1.48,
            letterSpacing: isRetention ? -0.4 : isEnglish ? 0.1 : 1.1,
            padding: isRetention ? "10px 24px" : 0,
            borderRadius: isRetention ? 15 : 0,
            backgroundColor: isRetention ? "rgba(6,25,34,.68)" : "transparent",
            opacity: captionOpacity,
          }}
        >
          {isRetention ? activeCaption.text : scene.narration}
        </div>
        <div
          style={{
            color: COLORS.muted,
            fontSize: 22,
            fontWeight: 700,
            letterSpacing: 3,
          }}
        >
          {footer} · {index + 1}/{count}
        </div>
      </div>

      {isRetention && scene.hook ? <HookOverlay hook={scene.hook} frame={frame} /> : null}

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
            locale={props.locale}
            editMode={props.editMode}
            footer={props.footer}
          />
        </Series.Sequence>
      ))}
    </Series>
    <Html5Audio src={staticFile(props.narrationAudio)} volume={1} />
  </AbsoluteFill>
);
