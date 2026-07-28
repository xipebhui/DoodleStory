import {copyFile} from "node:fs/promises";
import {extname, join, resolve} from "node:path";

const MOTIONS = new Set([
  "static",
  "zoom_in",
  "zoom_out",
  "pan_left",
  "pan_right",
  "pan_up",
  "pan_down",
]);
const TEMPLATE_ID = "narrated-panel-v1";
const validateDimension = (value, label) => {
  if (
    !Number.isInteger(value)
    || value < 64
    || value > 4096
    || value % 2 !== 0
  ) {
    throw new Error(`${label} 必须是 64–4096 之间的偶数整数`);
  }
};

export const validateManifest = (manifest) => {
  if (manifest?.templateId !== TEMPLATE_ID) {
    throw new Error(`不支持的 Remotion 模板：${manifest?.templateId ?? ""}`);
  }
  if (!Array.isArray(manifest.scenes) || manifest.scenes.length < 1) {
    throw new Error("Remotion manifest 至少需要一个 Scene");
  }
  if (manifest.scenes.length > 30) {
    throw new Error("Remotion manifest 最多支持 30 个 Scene");
  }
  validateDimension(manifest.width, "Remotion width");
  validateDimension(manifest.height, "Remotion height");
  for (const [index, scene] of manifest.scenes.entries()) {
    if (!scene?.id || !scene.imagePath || !scene.audioPath) {
      throw new Error(`第 ${index + 1} 个 Scene 缺少资产路径`);
    }
    if (!String(scene.subtitle ?? "").trim()) {
      throw new Error(`第 ${index + 1} 个 Scene 字幕不能为空`);
    }
    if (!Number.isFinite(scene.durationMs) || scene.durationMs <= 0) {
      throw new Error(`第 ${index + 1} 个 Scene 音频时长无效`);
    }
    if (!MOTIONS.has(scene.motion)) {
      throw new Error(`第 ${index + 1} 个 Scene Motion 不受支持`);
    }
  }
};

const stageAsset = async (source, publicDir, name) => {
  const extension = extname(source);
  const targetName = `${name}${extension}`;
  await copyFile(source, join(publicDir, targetName));
  return targetName;
};

export const stageManifest = async (manifest, publicDir) => {
  const scenes = [];
  for (const [index, scene] of manifest.scenes.entries()) {
    scenes.push({
      id: String(scene.id),
      image: await stageAsset(
        resolve(scene.imagePath),
        publicDir,
        `scene-${index + 1}-image`,
      ),
      audio: await stageAsset(
        resolve(scene.audioPath),
        publicDir,
        `scene-${index + 1}-audio`,
      ),
      subtitle: String(scene.subtitle).trim(),
      durationMs: Number(scene.durationMs),
      motion: scene.motion,
    });
  }
  const bgm = manifest.bgmPath
    ? await stageAsset(resolve(manifest.bgmPath), publicDir, "bgm")
    : null;
  return {
    scenes,
    bgm,
    width: manifest.width,
    height: manifest.height,
  };
};
