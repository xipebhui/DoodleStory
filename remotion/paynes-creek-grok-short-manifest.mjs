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
const EVIDENCE_LEVELS = new Set([
  "直接证据",
  "解释",
  "重建",
  "未知边界",
]);

export const validatePaynesCreekGrokShortManifest = (manifest) => {
  if (manifest?.templateId !== PAYNES_CREEK_GROK_SHORT_TEMPLATE_ID) {
    throw new Error(
      `不支持的 Paynes Creek Grok 模板：${manifest?.templateId ?? ""}`,
    );
  }
  if (manifest.width !== 1920 || manifest.height !== 1080 || manifest.fps !== 30) {
    throw new Error("Paynes Creek Grok 样片必须固定为 1920×1080、30fps");
  }
  if (manifest.publicationAuthorized !== false || manifest.bgm !== false) {
    throw new Error(
      "Paynes Creek Grok 样片必须保持 publicationAuthorized=false 且 bgm=false",
    );
  }
  if (
    !String(manifest.title ?? "").trim() ||
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
    if (!EVIDENCE_LEVELS.has(scene.evidence)) {
      throw new Error(`第 ${index + 1} 个 Grok Scene 证据标签无效`);
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
      scene.playbackRate > 1.35
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
    scenes,
    narrationAudio: audioName,
    width: manifest.width,
    height: manifest.height,
  };
};

