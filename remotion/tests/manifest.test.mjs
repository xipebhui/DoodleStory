import assert from "node:assert/strict";
import test from "node:test";

import {validateManifest} from "../manifest.mjs";

const validManifest = {
  templateId: "narrated-panel-v1",
  width: 948,
  height: 1660,
  scenes: [
    {
      id: "scene-1",
      imagePath: "/tmp/image.png",
      audioPath: "/tmp/audio.mp3",
      subtitle: "第一段字幕",
      durationMs: 1200,
      motion: "zoom_in",
    },
  ],
  bgmPath: null,
};

test("accepts the fixed template and motion enum", () => {
  assert.doesNotThrow(() => validateManifest(validManifest));
});

test("rejects unsupported motion", () => {
  assert.throws(
    () =>
      validateManifest({
        ...validManifest,
        scenes: [{...validManifest.scenes[0], motion: "spin"}],
      }),
    /Motion 不受支持/,
  );
});

test("rejects empty subtitle and invalid duration", () => {
  assert.throws(
    () =>
      validateManifest({
        ...validManifest,
        scenes: [{...validManifest.scenes[0], subtitle: " "}],
      }),
    /字幕不能为空/,
  );
  assert.throws(
    () =>
      validateManifest({
        ...validManifest,
        scenes: [{...validManifest.scenes[0], durationMs: 0}],
      }),
    /音频时长无效/,
  );
});

test("rejects invalid dynamic dimensions", () => {
  assert.throws(
    () => validateManifest({...validManifest, height: 1659}),
    /偶数整数/,
  );
  assert.throws(
    () => validateManifest({...validManifest, width: 5000}),
    /偶数整数/,
  );
});
