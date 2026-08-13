import {copyFile, stat} from "node:fs/promises";
import {extname, join, resolve} from "node:path";

export const PAYNES_CREEK_GROK_SHORT_TEMPLATE_ID =
  "paynes-creek-grok-ai-short-v1";
export const PAYNES_CREEK_GROK_SHORT_SCENE_IDS = [
  "S01",
  "S03",
  "S04",
  "S09",
  "S12",
];
const EVIDENCE_LEVELS_BY_LOCALE = {
  "zh-CN": new Set(["直接证据", "解释", "重建", "未知边界"]),
  "en-US": new Set([
    "Direct evidence",
    "Interpretation",
    "Reconstruction",
    "Evidence limit",
  ]),
};
const EDIT_MODES = new Set(["classic", "retention"]);
const TIMING_MODES = new Set(["weighted", "source_aligned"]);
const RETENTION_MOTIONS = new Set(["push_in", "drift_left", "drift_right"]);
const RETENTION_VISUAL_TREATMENTS = [
  "coast_to_inland",
  "process_filter",
  "process_boil",
  "transport_clue",
  "evidence_chain",
];

export const validatePaynesCreekGrokShortManifest = (manifest) => {
  if (manifest?.templateId !== PAYNES_CREEK_GROK_SHORT_TEMPLATE_ID) {
    throw new Error(
      `不支持的 Paynes Creek Grok 模板：${manifest?.templateId ?? ""}`,
    );
  }
  if (manifest.width !== 1920 || manifest.height !== 1080 || manifest.fps !== 30) {
    throw new Error("Paynes Creek Grok 样片必须固定为 1920×1080、30fps");
  }
  if (!EDIT_MODES.has(manifest.editMode)) {
    throw new Error("Paynes Creek Grok 样片 editMode 无效");
  }
  if (!TIMING_MODES.has(manifest.timingMode)) {
    throw new Error("Paynes Creek Grok 样片 timingMode 无效");
  }
  const expectedMaximumPlaybackRate = manifest.timingMode === "source_aligned"
    ? 1.45
    : 1.35;
  if (
    manifest.maxPlaybackRate !== expectedMaximumPlaybackRate ||
    (manifest.timingMode === "source_aligned" && manifest.editMode !== "retention")
  ) {
    throw new Error("Paynes Creek Grok 样片 timingMode 与播放速率上限无效");
  }
  if (manifest.editMode === "retention" && manifest.locale !== "en-US") {
    throw new Error("Paynes Creek Grok retention edit 当前只支持 en-US");
  }
  if (manifest.publicationAuthorized !== false || manifest.bgm !== false) {
    throw new Error(
      "Paynes Creek Grok 样片必须保持 publicationAuthorized=false 且 bgm=false",
    );
  }
  if (
    !String(manifest.title ?? "").trim() ||
    !String(manifest.footer ?? "").trim() ||
    !EVIDENCE_LEVELS_BY_LOCALE[manifest.locale] ||
    !manifest.narrationAudioPath ||
    !/^[a-f0-9]{64}$/.test(String(manifest.narrationSha256 ?? "")) ||
    !Number.isFinite(manifest.audioDurationMs)
  ) {
    throw new Error("Paynes Creek Grok 样片缺少标题、旁白、hash 或真实时长");
  }
  if (!Array.isArray(manifest.scenes) || manifest.scenes.length !== 5) {
    throw new Error("Paynes Creek Grok 样片必须正好包含 5 个 Scene");
  }
  const ids = manifest.scenes.map((scene) => scene?.id);
  if (JSON.stringify(ids) !== JSON.stringify(PAYNES_CREEK_GROK_SHORT_SCENE_IDS)) {
    throw new Error("Paynes Creek Grok Scene 顺序必须固定为 S01/S03/S04/S09/S12");
  }

  let totalFrames = 0;
  for (const [index, scene] of manifest.scenes.entries()) {
    if (
      !String(scene.title ?? "").trim() ||
      !String(scene.narration ?? "").trim() ||
      !scene.videoPath ||
      !/^[a-f0-9]{64}$/.test(String(scene.videoSha256 ?? ""))
    ) {
      throw new Error(`第 ${index + 1} 个 Grok Scene 缺少文案、视频或 hash`);
    }
    if (!EVIDENCE_LEVELS_BY_LOCALE[manifest.locale].has(scene.evidence)) {
      throw new Error(`第 ${index + 1} 个 Grok Scene 证据标签无效`);
    }
    if (!Array.isArray(scene.captions) || scene.captions.length < 1 || scene.captions.length > 4) {
      throw new Error(`第 ${index + 1} 个 Grok Scene 短语字幕数量无效`);
    }
    if (manifest.editMode === "retention" && scene.captions.length < 2) {
      throw new Error(`第 ${index + 1} 个 retention Scene 至少需要两条短语字幕`);
    }
    let captionFrame = 0;
    for (const caption of scene.captions) {
      if (
        !String(caption?.text ?? "").trim() ||
        !Number.isInteger(caption.startFrame) ||
        !Number.isInteger(caption.endFrame) ||
        caption.startFrame !== captionFrame ||
        caption.endFrame <= caption.startFrame
      ) {
        throw new Error(`第 ${index + 1} 个 Grok Scene 短语字幕时间轴无效`);
      }
      captionFrame = caption.endFrame;
    }
    if (
      captionFrame !== scene.durationInFrames ||
      scene.captions.map((caption) => caption.text).join(" ") !== scene.narration
    ) {
      throw new Error(`第 ${index + 1} 个 Grok Scene 短语字幕未覆盖完整旁白`);
    }
    if (manifest.editMode === "retention") {
      if (!RETENTION_MOTIONS.has(scene.motion)) {
        throw new Error(`第 ${index + 1} 个 retention Scene motion 无效`);
      }
      if (scene.visualTreatment !== RETENTION_VISUAL_TREATMENTS[index]) {
        throw new Error(`第 ${index + 1} 个 retention Scene visualTreatment 无效`);
      }
    } else if (scene.motion !== "none" || scene.visualTreatment !== "none") {
      throw new Error(`第 ${index + 1} 个 classic Scene 不得启用 retention 视觉处理`);
    }
    if (!Number.isFinite(scene.videoDurationMs) || scene.videoDurationMs <= 0) {
      throw new Error(`第 ${index + 1} 个 Grok Scene 视频时长无效`);
    }
    if (!Number.isInteger(scene.durationInFrames) || scene.durationInFrames < 120) {
      throw new Error(`第 ${index + 1} 个 Grok Scene 分配帧数无效`);
    }
    if (
      !Number.isFinite(scene.playbackRate) ||
      scene.playbackRate < 0.65 ||
      scene.playbackRate > manifest.maxPlaybackRate
    ) {
      throw new Error(`第 ${index + 1} 个 Grok Scene playback rate 超出安全范围`);
    }
    const expectedRate =
      scene.videoDurationMs / ((scene.durationInFrames / manifest.fps) * 1000);
    if (Math.abs(scene.playbackRate - expectedRate) > 0.0001) {
      throw new Error(`第 ${index + 1} 个 Grok Scene playback rate 与时长不一致`);
    }
    totalFrames += scene.durationInFrames;
  }
  if (totalFrames !== manifest.totalFrames) {
    throw new Error("Paynes Creek Grok Scene 帧数之和与 totalFrames 不一致");
  }
  if (manifest.editMode === "retention") {
    const hook = manifest.scenes[0]?.hook;
    if (
      !String(hook?.eyebrow ?? "").trim() ||
      !String(hook?.headline ?? "").trim() ||
      !String(hook?.question ?? "").trim()
    ) {
      throw new Error("Paynes Creek Grok retention edit 缺少前三秒钩子");
    }
  }
  const expectedFrames = Math.ceil(
    (manifest.audioDurationMs / 1000) * manifest.fps,
  );
  if (Math.abs(totalFrames - expectedFrames) > 1) {
    throw new Error("Paynes Creek Grok 视频帧数与真实旁白时长误差超过一帧");
  }
};

export const stagePaynesCreekGrokShortManifest = async (
  manifest,
  publicDir,
) => {
  validatePaynesCreekGrokShortManifest(manifest);
  const audioSource = resolve(manifest.narrationAudioPath);
  const audioStats = await stat(audioSource);
  if (!audioStats.isFile() || audioStats.size <= 0) {
    throw new Error("Paynes Creek Grok 旁白音频不存在或为空");
  }
  const audioName = `paynes-creek-grok-narration${extname(audioSource) || ".mp3"}`;
  await copyFile(audioSource, join(publicDir, audioName));

  const scenes = [];
  for (const [index, scene] of manifest.scenes.entries()) {
    const videoSource = resolve(scene.videoPath);
    const videoStats = await stat(videoSource);
    if (!videoStats.isFile() || videoStats.size <= 0) {
      throw new Error(`第 ${index + 1} 个 Grok Scene 视频不存在或为空`);
    }
    const videoName = `paynes-creek-grok-${scene.id.toLowerCase()}${
      extname(videoSource) || ".mp4"
    }`;
    await copyFile(videoSource, join(publicDir, videoName));
    scenes.push({...scene, video: videoName});
  }
  return {
    title: manifest.title,
    locale: manifest.locale,
    editMode: manifest.editMode,
    footer: manifest.footer,
    scenes,
    narrationAudio: audioName,
    width: manifest.width,
    height: manifest.height,
  };
};
