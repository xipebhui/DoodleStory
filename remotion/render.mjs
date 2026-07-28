import {bundle} from "@remotion/bundler";
import {renderMedia, selectComposition} from "@remotion/renderer";
import {mkdir, mkdtemp, readFile, rm} from "node:fs/promises";
import {tmpdir} from "node:os";
import {basename, dirname, join, resolve} from "node:path";
import {fileURLToPath} from "node:url";

import {stageManifest, validateManifest} from "./manifest.mjs";

const TEMPLATE_ID = "narrated-panel-v1";

const argument = (name) => {
  const index = process.argv.indexOf(name);
  if (index === -1 || !process.argv[index + 1]) {
    throw new Error(`缺少参数 ${name}`);
  }
  return process.argv[index + 1];
};

const main = async () => {
  const inputPath = resolve(argument("--input"));
  const outputPath = resolve(argument("--output"));
  const projectRoot = dirname(fileURLToPath(import.meta.url));
  const temporaryRoot = await mkdtemp(join(tmpdir(), "doodlestory-remotion-"));
  const publicDir = join(temporaryRoot, "public");
  await mkdir(publicDir, {recursive: true});
  try {
    const manifest = JSON.parse(await readFile(inputPath, "utf8"));
    validateManifest(manifest);
    const inputProps = await stageManifest(manifest, publicDir);
    const serveUrl = await bundle({
      entryPoint: join(projectRoot, "src", "index.ts"),
      publicDir,
      onProgress: () => undefined,
    });
    const composition = await selectComposition({
      serveUrl,
      id: TEMPLATE_ID,
      inputProps,
      logLevel: "error",
    });
    await renderMedia({
      composition,
      serveUrl,
      codec: "h264",
      audioCodec: "aac",
      pixelFormat: "yuv420p",
      imageFormat: "jpeg",
      outputLocation: outputPath,
      inputProps,
      logLevel: "error",
      overwrite: true,
    });
    const packageJson = JSON.parse(
      await readFile(join(projectRoot, "node_modules", "remotion", "package.json")),
    );
    process.stdout.write(
      `${JSON.stringify({
        status: "succeeded",
        templateId: TEMPLATE_ID,
        rendererVersion: packageJson.version,
        durationInFrames: composition.durationInFrames,
        fps: composition.fps,
        width: composition.width,
        height: composition.height,
        output: outputPath,
      })}\n`,
    );
  } finally {
    await rm(temporaryRoot, {recursive: true, force: true});
  }
};

if (basename(process.argv[1] ?? "") === "render.mjs") {
  main().catch((error) => {
    process.stderr.write(`${error instanceof Error ? error.stack : String(error)}\n`);
    process.exitCode = 1;
  });
}
