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

