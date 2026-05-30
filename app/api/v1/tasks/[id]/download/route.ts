import JSZip from "jszip";
import { DownloadStatus, FileAssetPurpose } from "@/generated/prisma/client";
import { apiData, apiError, apiRouteError } from "@/lib/api-response";
import { requireApiProfile } from "@/lib/current-user";
import { assertCanReadTask } from "@/lib/permissions";
import { prisma } from "@/lib/prisma";
import { readLocalFile, saveLocalFile } from "@/lib/storage/local-storage";

export async function POST(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const profile = await requireApiProfile();
    const { id } = await params;
    const task = await prisma.generationTask.findUnique({
      where: { id },
      include: {
        generatedImages: {
          include: { asset: true, panel: true },
          orderBy: { createdAt: "asc" },
        },
      },
    });

    if (!task) {
      return apiError("not_found", "任务不存在", 404);
    }

    assertCanReadTask(profile, task);
    const images = task.generatedImages.filter((image) => image.status === "succeeded" && image.asset);

    if (images.length === 0) {
      return apiError("conflict", "任务没有可下载的生成图片", 409);
    }

    const zip = new JSZip();

    for (const image of images) {
      if (!image.asset) {
        continue;
      }

      const file = await readLocalFile(image.asset.storageKey);
      const extension = image.asset.contentType === "image/png" ? "png" : image.asset.contentType === "image/webp" ? "webp" : "jpg";
      zip.file(`panel-${String(image.panel.panelOrder + 1).padStart(2, "0")}.${extension}`, file.bytes);
    }

    const bytes = await zip.generateAsync({ type: "nodebuffer" });
    const filename = `${task.id}.zip`;
    const stored = await saveLocalFile({
      purpose: "download_archive",
      bytes,
      filename,
    });
    const asset = await prisma.fileAsset.create({
      data: {
        purpose: FileAssetPurpose.download_archive,
        storageKey: stored.storageKey,
        originalFilename: filename,
        contentType: "application/zip",
        byteSize: stored.byteSize,
        checksumSha256: stored.checksumSha256,
      },
    });
    const download = await prisma.taskDownload.create({
      data: {
        taskId: task.id,
        status: DownloadStatus.ready,
        imageCount: images.length,
        assetId: asset.id,
        filename,
      },
      include: { asset: true },
    });

    return apiData(download, { status: 201 });
  } catch (error) {
    return apiRouteError(error);
  }
}
