import assert from "node:assert/strict";
import test from "node:test";

import {
  PAYNES_CREEK_GROK_SHORT_SCENE_IDS,
  PAYNES_CREEK_GROK_SHORT_TEMPLATE_ID,
  validatePaynesCreekGrokShortManifest,
} from "../paynes-creek-grok-short-manifest.mjs";

const validManifest = {
  templateId: PAYNES_CREEK_GROK_SHORT_TEMPLATE_ID,
  title: "测试短片",
  locale: "zh-CN",
  editMode: "classic",
  timingMode: "weighted",
  presentationMode: "review",
  artifactSlug: "paynes-creek-grok-ai-short-v1",
  maxPlaybackRate: 1.35,
  footer: "PAYNES CREEK · AI VISUAL PILOT",
  width: 1920,
  height: 1080,
  fps: 30,
  publicationAuthorized: false,
  bgm: false,
  narrationAudioPath: "C:/media/narration.mp3",
  narrationSha256: "a".repeat(64),
  audioDurationMs: 45000,
  totalFrames: 1350,
  scenes: PAYNES_CREEK_GROK_SHORT_SCENE_IDS.map((id, index) => ({
    id,
    title: `Scene ${index + 1}`,
    narration: `旁白 ${index + 1}`,
    evidence: index === 1 ? "重建" : "解释",
    videoPath: `C:/media/${id}.mp4`,
    videoSha256: String(index + 1).repeat(64),
    videoDurationMs: 9000,
    durationInFrames: 270,
    playbackRate: 1,
    captions: [{text: `旁白 ${index + 1}`, startFrame: 0, endFrame: 270}],
    motion: "none",
    visualTreatment: "none",
    hook: null,
  })),
};

test("accepts the exact five-scene Grok short manifest", () => {
  assert.doesNotThrow(() => validatePaynesCreekGrokShortManifest(validManifest));
});

test("rejects publication, scene drift and audio/frame mismatch", () => {
  assert.throws(
    () => validatePaynesCreekGrokShortManifest({...validManifest, publicationAuthorized: true}),
    /publicationAuthorized/,
  );
  assert.throws(
    () => validatePaynesCreekGrokShortManifest({...validManifest, scenes: validManifest.scenes.slice(0, 4)}),
    /5 个 Scene/,
  );
  assert.throws(
    () => validatePaynesCreekGrokShortManifest({...validManifest, totalFrames: 1349}),
    /帧数之和/,
  );
});

test("rejects unsafe or inconsistent playback rates", () => {
  const unsafe = validManifest.scenes.map((scene, index) =>
    index === 2 ? {...scene, playbackRate: 0.4} : scene,
  );
  assert.throws(
    () => validatePaynesCreekGrokShortManifest({...validManifest, scenes: unsafe}),
    /安全范围/,
  );
  const inconsistent = validManifest.scenes.map((scene, index) =>
    index === 2 ? {...scene, playbackRate: 1.1} : scene,
  );
  assert.throws(
    () => validatePaynesCreekGrokShortManifest({...validManifest, scenes: inconsistent}),
    /时长不一致/,
  );
});

test("accepts English localization and rejects mixed evidence labels", () => {
  const scenes = validManifest.scenes.map((scene, index) => ({
    ...scene,
    evidence: index === 1 ? "Reconstruction" : "Interpretation",
  }));
  const english = {
    ...validManifest,
    locale: "en-US",
    footer: "PAYNES CREEK · EVIDENCE-LED AI SHORT",
    scenes,
  };
  assert.doesNotThrow(() => validatePaynesCreekGrokShortManifest(english));
  assert.throws(
    () => validatePaynesCreekGrokShortManifest({
      ...english,
      scenes: scenes.map((scene, index) =>
        index === 0 ? {...scene, evidence: "解释"} : scene,
      ),
    }),
    /证据标签无效/,
  );
});

test("accepts retention edit and rejects broken phrase captions", () => {
  const treatments = [
    "coast_to_inland",
    "process_filter",
    "process_boil",
    "transport_clue",
    "evidence_chain",
  ];
  const scenes = validManifest.scenes.map((scene, index) => ({
    ...scene,
    narration: `Clue ${index + 1} survives here today.`,
    evidence: index === 3 ? "Direct evidence" : "Interpretation",
    captions: [
      {text: `Clue ${index + 1}`, startFrame: 0, endFrame: 120},
      {text: "survives here today.", startFrame: 120, endFrame: 270},
    ],
    motion: index % 2 === 0 ? "push_in" : "drift_left",
    visualTreatment: treatments[index],
    hook: index === 0 ? {
      eyebrow: "A LOST SUPPLY CHAIN",
      headline: "NO RECORDS SURVIVE.",
      question: "SO HOW DID IT MOVE?",
    } : null,
  }));
  const retention = {
    ...validManifest,
    locale: "en-US",
    editMode: "retention",
    timingMode: "weighted",
    maxPlaybackRate: 1.35,
    scenes,
  };
  assert.doesNotThrow(() => validatePaynesCreekGrokShortManifest(retention));
  assert.throws(
    () => validatePaynesCreekGrokShortManifest({
      ...retention,
      scenes: scenes.map((scene, index) =>
        index === 2
          ? {...scene, captions: [{...scene.captions[0], endFrame: 119}, scene.captions[1]]}
          : scene,
      ),
    }),
    /短语字幕时间轴无效/,
  );
});

test("accepts source-aligned retention timing up to the explicit rate ceiling", () => {
  const treatments = [
    "coast_to_inland",
    "process_filter",
    "process_boil",
    "transport_clue",
    "evidence_chain",
  ];
  const scenes = validManifest.scenes.map((scene, index) => ({
    ...scene,
    narration: `Clue ${index + 1} survives here today.`,
    evidence: "Interpretation",
    captions: [
      {text: `Clue ${index + 1}`, startFrame: 0, endFrame: 120},
      {text: "survives here today.", startFrame: 120, endFrame: 270},
    ],
    motion: "push_in",
    visualTreatment: treatments[index],
    hook: index === 0 ? {
      eyebrow: "A LOST SUPPLY CHAIN",
      headline: "NO RECORDS SURVIVE.",
      question: "SO HOW DID IT MOVE?",
    } : null,
    videoDurationMs: index === 2 ? 12600 : 9000,
    playbackRate: index === 2 ? 1.4 : 1,
  }));
  const sourceAligned = {
    ...validManifest,
    locale: "en-US",
    editMode: "retention",
    timingMode: "source_aligned",
    maxPlaybackRate: 1.45,
    scenes,
  };
  assert.doesNotThrow(() => validatePaynesCreekGrokShortManifest(sourceAligned));
  assert.throws(
    () => validatePaynesCreekGrokShortManifest({...sourceAligned, maxPlaybackRate: 1.35}),
    /播放速率上限无效/,
  );
});

test("accepts a clean manual-publish surface and rejects production labels", () => {
  const treatments = [
    "coast_to_inland",
    "process_filter",
    "process_boil",
    "transport_clue",
    "evidence_chain",
  ];
  const scenes = validManifest.scenes.map((scene, index) => ({
    ...scene,
    narration: `Clue ${index + 1} survives here today.`,
    evidence: "Interpretation",
    captions: [
      {text: `Clue ${index + 1}`, startFrame: 0, endFrame: 120},
      {text: "survives here today.", startFrame: 120, endFrame: 270},
    ],
    motion: "push_in",
    visualTreatment: treatments[index],
    hook: index === 0 ? {
      eyebrow: "A LOST SUPPLY CHAIN",
      headline: "NO RECORDS SURVIVE.",
      question: "SO HOW DID IT MOVE?",
    } : null,
  }));
  const publish = {
    ...validManifest,
    title: "How Did Maya Salt Travel Inland?",
    locale: "en-US",
    editMode: "retention",
    presentationMode: "manual_publish",
    artifactSlug: "paynes-creek-maya-salt-publish-en-v1",
    footer: "PAYNES CREEK · ARCHAEOLOGY SHORT",
    scenes,
  };
  assert.doesNotThrow(() => validatePaynesCreekGrokShortManifest(publish));
  assert.throws(
    () => validatePaynesCreekGrokShortManifest({...publish, footer: "AI SHORT"}),
    /可见文案/,
  );
  assert.throws(
    () => validatePaynesCreekGrokShortManifest({...publish, artifactSlug: "maya-ai-short"}),
    /artifactSlug/,
  );
});
