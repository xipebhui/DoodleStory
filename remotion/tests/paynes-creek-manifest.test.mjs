import assert from "node:assert/strict";
import test from "node:test";

import {
  PAYNES_CREEK_SCENE_IDS,
  PAYNES_CREEK_TEMPLATE_ID,
  validatePaynesCreekManifest,
} from "../paynes-creek-manifest.mjs";

const validManifest = {
  templateId: PAYNES_CREEK_TEMPLATE_ID,
  width: 1920,
  height: 1080,
  fps: 30,
  publicationAuthorized: false,
  bgm: false,
  narrationAudioPath: "C:/media/narration.mp3",
  narrationSha256: "a".repeat(64),
  audioDurationMs: 12000,
  totalFrames: 360,
  scenes: PAYNES_CREEK_SCENE_IDS.map((id, index) => ({
    id,
    title: `Scene ${index + 1}`,
    narration: `旁白 ${index + 1}`,
    evidence: index === 2 ? "重建" : "直接证据",
    durationInFrames: 30,
  })),
};

test("accepts the exact 12-scene local vector manifest", () => {
  assert.doesNotThrow(() => validatePaynesCreekManifest(validManifest));
});

test("rejects publication, scene drift and audio/frame mismatch", () => {
  assert.throws(() => validatePaynesCreekManifest({...validManifest, publicationAuthorized: true}), /publicationAuthorized/);
  assert.throws(() => validatePaynesCreekManifest({...validManifest, scenes: validManifest.scenes.slice(0, 11)}), /12 个 Scene/);
  assert.throws(() => validatePaynesCreekManifest({...validManifest, totalFrames: 359}), /帧数之和/);
});

test("rejects an invalid evidence label", () => {
  const scenes = validManifest.scenes.map((scene, index) => index === 4 ? {...scene, evidence: "猜测"} : scene);
  assert.throws(() => validatePaynesCreekManifest({...validManifest, scenes}), /证据标签无效/);
});
