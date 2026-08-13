import {copyFile, stat} from "node:fs/promises";
import {extname, join, resolve} from "node:path";

export const PAYNES_CREEK_TEMPLATE_ID = "paynes-creek-vector-v1";
export const PAYNES_CREEK_SCENE_IDS = Array.from({length: 12}, (_, index) => `S${String(index + 1).padStart(2, "0")}`);
const EVIDENCE_LEVELS = new Set(["直接证据", "解释", "重建", "未知边界"]);

export const validatePaynesCreekManifest = (manifest) => {
  if (manifest?.templateId !== PAYNES_CREEK_TEMPLATE_ID) {
    throw new Error(`不支持的 Paynes Creek 模板：${manifest?.templateId ?? ""}`);
  }
  if (manifest.width !== 1920 || manifest.height !== 1080 || manifest.fps !== 30) {
    throw new Error("Paynes Creek 样片必须固定为 1920×1080、30fps");
  }
  if (manifest.publicationAuthorized !== false || manifest.bgm !== false) {
    throw new Error("Paynes Creek 本地样片必须保持 publicationAuthorized=false 且 bgm=false");
  }
  if (!manifest.narrationAudioPath || !manifest.narrationSha256 || !Number.isFinite(manifest.audioDurationMs)) {
    throw new Error("Paynes Creek 样片缺少旁白资产、hash 或真实时长");
  }
  if (!Array.isArray(manifest.scenes) || manifest.scenes.length !== 12) {
    throw new Error("Paynes Creek 样片必须正好包含 12 个 Scene");
  }
  const ids = manifest.scenes.map((scene) => scene?.id);
  if (JSON.stringify(ids) !== JSON.stringify(PAYNES_CREEK_SCENE_IDS)) {
    throw new Error("Paynes Creek Scene 顺序必须固定为 S01–S12");
  }
  let totalFrames = 0;
  for (const [index, scene] of manifest.scenes.entries()) {
    if (!String(scene.title ?? "").trim() || !String(scene.narration ?? "").trim()) {
      throw new Error(`第 ${index + 1} 个 Scene 缺少标题或旁白`);
    }
    if (!EVIDENCE_LEVELS.has(scene.evidence)) {
      throw new Error(`第 ${index + 1} 个 Scene 证据标签无效`);
    }
    if (!Number.isInteger(scene.durationInFrames) || scene.durationInFrames < 30) {
      throw new Error(`第 ${index + 1} 个 Scene 时长帧数无效`);
    }
    totalFrames += scene.durationInFrames;
  }
  if (totalFrames !== manifest.totalFrames) {
    throw new Error("Paynes Creek Scene 帧数之和与 totalFrames 不一致");
  }
  const expectedFrames = Math.ceil((manifest.audioDurationMs / 1000) * manifest.fps);
  if (Math.abs(totalFrames - expectedFrames) > 1) {
    throw new Error("Paynes Creek 视频帧数与真实旁白时长误差超过一帧");
  }
};

export const stagePaynesCreekManifest = async (manifest, publicDir) => {
  validatePaynesCreekManifest(manifest);
  const source = resolve(manifest.narrationAudioPath);
  const sourceStats = await stat(source);
  if (!sourceStats.isFile() || sourceStats.size <= 0) {
    throw new Error("Paynes Creek 旁白音频不存在或为空");
  }
  const audioName = `paynes-creek-narration${extname(source) || ".mp3"}`;
  await copyFile(source, join(publicDir, audioName));
  return {
    scenes: manifest.scenes,
    narrationAudio: audioName,
    width: manifest.width,
    height: manifest.height,
  };
};
